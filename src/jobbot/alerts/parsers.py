"""Turn alert emails into JobPosting rows.

Two problems make this more than "grep the links out".

1. Tracking redirects. Alert mails wrap every link in a click-tracker whose
   token is unique PER EMAIL, so the naive URL is a different string each
   time the same job is advertised, and dedup would fail: one job, five rows.
   `canonical_url` unwraps the real target out of the redirect's query
   string, and the dedup key falls back to job-id / title+company when the
   real target cannot be recovered. Unwrapping is pure string work: we never
   follow the redirect, because following it would be a request to the very
   board that asked us not to crawl.

2. Body length. The scorer refuses anything under 100 words rather than
   invent a fit score from a teaser. Alert mails vary wildly here, so the
   parser keeps every scrap of description it can find and the runner
   records honestly whether the row arrived scorable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import structlog
from selectolax.parser import HTMLParser

log = structlog.get_logger()

# Query parameters that carry the real destination inside a tracking link.
_REDIRECT_PARAMS = ("url", "u", "target", "redirect", "redirect_url", "link",
                    "dest", "destination", "r", "goto")
# Board-specific job-id shapes, used as the dedup key when the canonical URL
# cannot be recovered from the tracker.
_JOB_ID_PATTERNS = (
    re.compile(r"/job(?:s)?/(?:[\w-]*?-)?(\d{5,})", re.IGNORECASE),
    re.compile(r"[?&](?:jobId|job_id|projektId|projekt_id|id)=(\d{4,})", re.IGNORECASE),
    re.compile(r"/projekt/(\d{4,})", re.IGNORECASE),
)
_TRACKING_HOST_HINTS = ("click", "track", "link", "email", "mail", "cta", "r.")


@dataclass
class ParsedPosting:
    title: str
    url: str
    company: str | None = None
    location: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    dedup_key: str = ""


def canonical_url(raw: str) -> str:
    """Unwrap a tracking redirect to the destination it points at.

    Pure string work, no HTTP. Returns the input unchanged when there is
    nothing to unwrap.
    """
    if not raw:
        return raw
    url = raw.strip()
    for _ in range(3):  # trackers occasionally nest
        try:
            parts = urlparse(url)
        except ValueError:
            return url
        params = parse_qs(parts.query)
        target = None
        for key in _REDIRECT_PARAMS:
            for candidate in params.get(key, []):
                decoded = unquote(candidate)
                if decoded.startswith(("http://", "https://")):
                    target = decoded
                    break
            if target:
                break
        if not target:
            return url
        url = target
    return url


def looks_like_tracker(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(hint in host for hint in _TRACKING_HOST_HINTS)


def dedup_key_for(url: str, title: str, company: str | None) -> str:
    """Stable identity for a posting seen through an email alert.

    Prefers a job id embedded in the URL, then the canonical URL itself, and
    only then falls back to title+company, so the same job advertised in
    Monday's and Tuesday's alert collapses into one row.
    """
    canonical = canonical_url(url)
    for pattern in _JOB_ID_PATTERNS:
        m = pattern.search(canonical)
        if m:
            host = (urlparse(canonical).netloc or "").lower().replace("www.", "")
            return f"{host}#{m.group(1)}"
    if canonical and not looks_like_tracker(canonical):
        # Drop query noise (utm_*, session tokens) from the identity.
        p = urlparse(canonical)
        return f"{p.netloc.lower().replace('www.', '')}{p.path.rstrip('/')}"
    norm = re.sub(r"\s+", " ", f"{title} {company or ''}").strip().lower()
    return f"title:{norm}"


def _clean(text: str | None) -> str:
    return re.sub(r"[ \t ]+", " ", (text or "").replace("\r", "")).strip()


def _block_text(node) -> str:
    return _clean(node.text(separator="\n", strip=True)) if node is not None else ""


def parse_generic(html: str, text: str) -> list[ParsedPosting]:
    """Best-effort parse that works on most board alert layouts.

    Anchors whose href survives unwrapping into a job-detail-looking URL are
    treated as postings; the enclosing table cell / list item supplies the
    surrounding description text.
    """
    if not html:
        return _parse_plaintext(text)

    tree = HTMLParser(html)
    out: list[ParsedPosting] = []
    seen: set[str] = set()

    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "#")):
            continue
        title = _clean(anchor.text(strip=True))
        if len(title) < 6 or len(title) > 160:
            continue
        low = title.lower()
        # Chrome/footer links: unsubscribe, view in browser, social, etc.
        if any(w in low for w in ("unsubscribe", "abmelden", "view in browser",
                                  "im browser", "datenschutz", "privacy",
                                  "impressum", "settings", "einstellungen",
                                  "all jobs", "alle jobs", "log in", "anmelden")):
            continue
        canonical = canonical_url(href)
        if not _looks_like_job_link(canonical):
            continue
        key = dedup_key_for(href, title, None)
        if key in seen:
            continue
        seen.add(key)

        # Walk up for the card that holds company/location/teaser.
        block = anchor
        for _ in range(4):
            if block.parent is None:
                break
            block = block.parent
            if len(_block_text(block).split()) > len(title.split()) + 8:
                break
        body = _block_text(block)
        out.append(ParsedPosting(
            title=title,
            url=canonical,
            description=body,
            dedup_key=key,
        ))
    return out


def _looks_like_job_link(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if any(p.search(lowered) for p in _JOB_ID_PATTERNS):
        return True
    return any(seg in lowered for seg in ("/job/", "/jobs/", "/projekt/",
                                          "/projekte/", "/vacancy/", "/stelle/"))


_PLAIN_URL_RE = re.compile(r"https?://\S+")


def _parse_plaintext(text: str) -> list[ParsedPosting]:
    """Fallback for text-only alerts: a URL plus the line above it."""
    out: list[ParsedPosting] = []
    seen: set[str] = set()
    lines = [ln.strip() for ln in (text or "").splitlines()]
    for i, line in enumerate(lines):
        for raw_url in _PLAIN_URL_RE.findall(line):
            canonical = canonical_url(raw_url.rstrip(").,>"))
            if not _looks_like_job_link(canonical):
                continue
            title = ""
            for back in range(1, 4):
                if i - back >= 0 and len(lines[i - back]) > 5:
                    title = lines[i - back]
                    break
            if not title:
                continue
            key = dedup_key_for(canonical, title, None)
            if key in seen:
                continue
            seen.add(key)
            context = "\n".join(lines[max(0, i - 3):i + 6])
            out.append(ParsedPosting(title=_clean(title)[:160], url=canonical,
                                     description=_clean(context), dedup_key=key))
    return out


def parse_freelance_de(html: str, text: str) -> list[ParsedPosting]:
    """freelance.de project alerts: German project cards, often with a
    substantial teaser and a 'Projekt' link per entry."""
    postings = parse_generic(html, text)
    for p in postings:
        if p.company is None:
            # freelance.de hides the client behind the agency listing; the
            # placeholder is what update_enrichment knows how to replace.
            p.company = "(see posting)"
        loc = re.search(r"(?:Einsatzort|Standort|Ort)\s*:?\s*([A-Za-zÄÖÜäöüß .-]{2,40})",
                        p.description)
        if loc:
            p.location = _clean(loc.group(1))
    return postings


def parse_bayt(html: str, text: str) -> list[ParsedPosting]:
    """bayt.com job alerts: '<Title> - <Company> - <City>, <Country>' rows."""
    postings = parse_generic(html, text)
    for p in postings:
        m = re.match(r"^(?P<title>.+?)\s+-\s+(?P<company>.+?)\s+-\s+(?P<loc>.+)$",
                     p.title)
        if m:
            p.title = _clean(m.group("title"))
            p.company = _clean(m.group("company"))
            p.location = _clean(m.group("loc"))
        if not p.location:
            city = re.search(r"\b(Dubai|Abu Dhabi|Sharjah|Doha|Riyadh|Kuwait|"
                             r"Manama|Muscat|Jeddah|Cairo)\b", p.description)
            if city:
                p.location = city.group(1)
    return postings


# source name -> (parser, sender substrings that identify the board)
PROVIDERS: dict[str, tuple] = {
    "freelance_de_alert": (parse_freelance_de, ["freelance.de"]),
    "bayt_alert": (parse_bayt, ["bayt.com"]),
}


def parser_for(sender: str):
    """Pick the provider parser for a sender, else the generic one."""
    low = (sender or "").lower()
    for source, (fn, hints) in PROVIDERS.items():
        if any(h in low for h in hints):
            return source, fn
    return "job_alert", parse_generic
