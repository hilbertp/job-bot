"""jobgether.com, a remote-jobs aggregator with server-rendered offer pages.

List page: https://jobgether.com/remote-jobs/product-manager
Offer page: https://jobgether.com/offer/<24-hex-id>-<slug>

Measured 2026-09-17:

- The list page answers HTTP 410, yet its 930 KB body still carries about
  163 links of the form href="/offer/<24-hex-id>-<slug>". So `fetch` accepts
  200 or 410 and parses the body. raise_for_status() would throw it away.
- Rate limiting is real. After about five requests within a minute the site
  answers a bare 9-byte HTTP 403 ("Forbidden", served by a Cloudflare
  Worker). Once tripped, the list route stayed 403 for at least 20 minutes,
  for a real browser on the same IP as well, while offer pages kept
  answering 200. Every request here is followed by a 3 second sleep, `fetch`
  makes exactly one request per query and never fetches details, and the
  enrichment stage fetches one offer page per row on later runs. A 403 stops
  the current call and is never treated as a gone listing.
- The offer page answers HTTP 200 with one JSON-LD "@type": "JobPosting"
  block. Its description is HTML (about 1,200 words), hiringOrganization.name
  is the employer, datePosted is a JavaScript Date.toString() such as
  "Tue Sep 15 2026 04:31:19 GMT+0000 (Coordinated Universal Time)" rather
  than ISO, and jobLocation only names the country ("US"). The "Key facts"
  block carries the real states: `<span>Remote from: </span>` followed by
  one `<a>` per state, e.g. "California (USA), Delaware (USA)". The APPLY
  link goes to the employer's ATS with utm_source=Jobgether; stripped of the
  utm parameters it becomes `apply_url`, the offer URL stays as `url`.
- The company is not readable on the list page, so `fetch` writes the
  placeholder "Jobgether (see detail)" and `fetch_detail` overwrites it.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, ListingGone, SearchQuery, parse_posted_at, stable_id

log = structlog.get_logger()

_BASE = "https://jobgether.com"
# Only the product-manager list is known to exist; every query reads it and
# the title filter in `fetch` narrows client-side.
_LIST_URL = f"{_BASE}/remote-jobs/product-manager"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_SLEEP_S = 3.0  # about five requests per minute trip the 403 wall
_COMPANY_UNKNOWN = "Jobgether (see detail)"
_OFFER_RE = re.compile(r"^(?:https?://(?:www\.)?jobgether\.com)?(/offer/([0-9a-f]{24})-([^/?#]+))")
_JS_DATE_RE = re.compile(r"^[A-Za-z]{3} ([A-Za-z]{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2}) GMT([+-]\d{4})")
_BLOCK_TAG_RE = re.compile(r"</?(?:br|p|div|li|ul|ol|h[1-6]|tr)\b[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _get(url: str) -> httpx.Response:
    """One polite GET. The sleep runs even when the request raises."""
    try:
        return httpx.get(url, headers=_HEADERS, timeout=20.0, follow_redirects=True)
    finally:
        time.sleep(_SLEEP_S)


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _title_from_slug(slug: str) -> str:
    """"principal-product-manager---personal-loans" -> "Principal Product Manager - Personal Loans"."""
    parts = [" ".join(p.replace("-", " ").split()) for p in slug.split("---")]
    return " - ".join(p for p in parts if p).title()


def _title_from_anchor(a, slug: str) -> str:
    """A heading inside the anchor wins. Bare anchor text is trusted only when
    it spells the slug, so an anchor that wraps a whole card never yields a
    mashed "TitleCompanyLocation" string. Otherwise the slug is the title."""
    heading = a.css_first("h1, h2, h3, h4, h5")
    if heading is not None and heading.text(strip=True):
        return " ".join(heading.text(strip=True).split())
    text = " ".join(a.text(separator=" ", strip=True).split())
    return text if text and _norm(text) == _norm(slug) else _title_from_slug(slug)


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", _BLOCK_TAG_RE.sub("\n", html.unescape(raw or "")))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _parse_posted(value) -> datetime | None:
    m = _JS_DATE_RE.match(str(value or "").strip())
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %d %Y %H:%M:%S %z")
        except ValueError:
            return None
    return parse_posted_at(value)


def _strip_utm(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _jobposting_from_jsonld(tree: HTMLParser) -> dict | None:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def _location_from_jsonld(item: dict) -> str | None:
    locs = item.get("jobLocation")
    parts: list[str] = []
    for loc in (locs if isinstance(locs, list) else [locs]):
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address") if isinstance(loc.get("address"), dict) else loc
        bits = []
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            val = addr.get(key)
            val = val.get("name") if isinstance(val, dict) else val
            if val and str(val).strip():
                bits.append(str(val).strip())
        if bits:
            parts.append(", ".join(bits))
    return "; ".join(dict.fromkeys(parts)) or None


def _location_from_key_facts(tree: HTMLParser) -> str | None:
    """"Remote from:" names the states; JSON-LD only says "US"."""
    for span in tree.css("span"):
        if span.text(strip=True).lower().startswith("remote from") and span.parent is not None:
            value = span.parent.text(separator=" ", strip=True)
            value = re.sub(r"^\s*remote from:?\s*", "", value, flags=re.IGNORECASE)
            return " ".join(value.replace(" ,", ",").split())[:200] or None
    return None


def _apply_url(tree: HTMLParser) -> str | None:
    """The employer's ATS link, recognised by utm_source=Jobgether (sometimes
    written utm%5Fsource)."""
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if href.startswith("http") and "utm_source=jobgether" in unquote(href).lower():
            return _strip_utm(href)
    return None


class JobgetherScraper(BaseScraper):
    source = "jobgether"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product manager"}. One request, no details."""
        keywords = (query.get("q") or "product manager").strip()
        needles = keywords.lower().split()
        try:
            r = _get(_LIST_URL)
        except Exception as exc:
            log.warning("jobgether_fetch_failed", error=str(exc), url=_LIST_URL)
            return []
        if r.status_code == 403:
            log.warning("jobgether_rate_limited", status=403, url=_LIST_URL)
            return []
        if r.status_code not in (200, 410):
            log.warning("jobgether_fetch_failed", status=r.status_code, url=_LIST_URL)
            return []

        out: list[JobPosting] = []
        seen: set[str] = set()
        for a in HTMLParser(r.text).css("a[href]"):
            m = _OFFER_RE.match((a.attributes.get("href") or "").strip())
            if m is None or m.group(2) in seen:
                continue
            title = _title_from_anchor(a, m.group(3))
            if needles and not all(n in title.lower() for n in needles):
                continue
            seen.add(m.group(2))
            url = _BASE + m.group(1)
            out.append(JobPosting(
                id=stable_id(self.source, url), source=self.source, title=title,
                company=_COMPANY_UNKNOWN, location="Remote", url=url, apply_url=url,
                posted_at=None, description="", tags=["remote"],
            ))
        log.info("jobgether_fetched", n=len(out), q=keywords, status=r.status_code)
        return out

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        """Read the offer page's JSON-LD JobPosting. None means "retry later"."""
        url = str(job.url)
        try:
            r = _get(url)
        except Exception as exc:
            log.warning("jobgether_detail_fetch_failed", error=str(exc), url=url)
            return None
        if r.status_code == 403:
            log.warning("jobgether_rate_limited", status=403, url=url)
            return None
        if r.status_code in (404, 410):
            raise ListingGone(f"jobgether returned HTTP {r.status_code}")
        final = str(getattr(r, "url", "") or "")
        if final and "/offer/" not in final:
            raise ListingGone(f"jobgether redirected to {final[:120]}")
        if r.status_code != 200:
            log.warning("jobgether_detail_http_error", status=r.status_code, url=url)
            return None

        tree = HTMLParser(r.text)
        item = _jobposting_from_jsonld(tree)
        if item is None:
            log.warning("jobgether_detail_no_jsonld", url=url)
            return None
        description = _strip_html(str(item.get("description") or ""))
        if len(description.split()) < 100:
            return None

        update: dict = {"description": description[:12000]}
        org = item.get("hiringOrganization")
        company = org.get("name") if isinstance(org, dict) else org
        if isinstance(company, str) and company.strip():
            update["company"] = company.strip()
        if (posted_at := _parse_posted(item.get("datePosted"))) is not None:
            update["posted_at"] = posted_at
        if location := (_location_from_key_facts(tree) or _location_from_jsonld(item)):
            update["location"] = location
        if apply_url := _apply_url(tree):
            update["apply_url"] = apply_url
        return job.model_copy(update=update)
