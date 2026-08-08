"""talentmate.com (UAE/Gulf job board, IT and tech heavy).

Server-rendered public HTML search; verified 2026-08-02. robots.txt is fully
permissive (`User-agent: * / Disallow:` plus a sitemap), the search page needs
no JavaScript, and `?search=<kw>&page=<n>` pages cleanly at 20 cards per page
with no overlap between pages.

Coverage note, corrected 2026-08-08: an unpinned `?search=product manager`
looks Gulf-heavy on page 1 and is not. Measured over 137 ingested rows it was
35 Bengaluru, 20 Mumbai, 15 Hyderabad, 12 Chennai and only 10 UAE, i.e. we
paid a detail fetch and a scoring call for ~127 postings in a country the
candidate will not move to. Queries therefore pin a country
(`/jobs/<country>?search=<kw>`), which returns 20 clean UAE cards, twice the
UAE yield of three unpinned pages at a sixth of the cost.

Paging is IGNORED on the country-scoped path: `&page=2` and `&page=3` return
the same 20 cards as page 1 (verified). Coverage therefore comes from running
several keyword variants, exactly as it does for brainville.

Company names are NOT on the cards: every card renders the portal itself
("Talentmate") as the poster, so we hand the pipeline the "(see posting)"
placeholder that `update_enrichment` knows how to overwrite once the detail
page reveals the real employer.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_SEARCH_URL = "https://www.talentmate.com/jobs"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
# 20 cards per page; three pages is plenty for a keyword query and keeps us
# well inside polite volume for a board this size.
_MAX_PAGES = 3
# "Posted on 07 Aug 2026"
_POSTED_RE = re.compile(r"Posted on\s+(\d{1,2}\s+\w{3}\s+\d{4})", re.IGNORECASE)
# The portal is its own "company" on every card, so it carries no signal.
_PORTAL_AS_COMPANY = "talentmate"
_COMPANY_UNKNOWN = "(see posting)"


def _parse_posted(text: str | None) -> datetime | None:
    if not text:
        return None
    m = _POSTED_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _employer_from_jsonld(tree: HTMLParser) -> str | None:
    """Real employer name from the detail page's schema.org JobPosting block.

    The cards only ever name the portal, so this is the one place the actual
    company surfaces ("ClearGrid", "Sarwa", ...). `update_enrichment`
    overwrites the "(see posting)" placeholder with whatever we return here.
    """
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            org = item.get("hiringOrganization")
            name = org.get("name") if isinstance(org, dict) else None
            if name and name.strip():
                return name.strip()
    return None


def _sibling_text(card, icon_selector: str) -> str | None:
    """Read the label that follows one of the card's glyph spans.

    The cards mark up company and location as `<span class="tm-building">`
    (an icon, no text) followed by a `<span>` holding the value.
    """
    icon = card.css_first(icon_selector)
    if icon is None or icon.parent is None:
        return None
    spans = [s.text(strip=True) for s in icon.parent.css("span")]
    values = [s for s in spans if s]
    return values[0] if values else None


class TalentmateScraper(BaseScraper):
    source = "talentmate"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product manager", "country": "uae"}

        `country` pins the search to one market. Omit it only when you
        genuinely want every country, and note that paging is available only
        on the unpinned path.
        """
        keywords = (query.get("q") or "product manager").strip()
        country = (query.get("country") or "").strip().lower()
        search_url = f"{_SEARCH_URL}/{country}" if country else _SEARCH_URL
        # Country-scoped search ignores &page; a single request is the whole
        # result set. Asking for more pages would just re-ingest page 1.
        max_pages = 1 if country else _MAX_PAGES
        out: list[JobPosting] = []
        seen: set[str] = set()

        for page in range(1, max_pages + 1):
            params = {"search": keywords}
            if not country:
                params["page"] = page
            try:
                r = httpx.get(
                    search_url, params=params,
                    headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
                    timeout=20.0, follow_redirects=True,
                )
                r.raise_for_status()
            except Exception as exc:
                log.warning("talentmate_fetch_failed", error=str(exc), page=page,
                            country=country or "all")
                break

            cards = HTMLParser(r.text).css("div.job-details")
            if not cards:
                break

            page_new = 0
            for card in cards:
                link = card.css_first("a.no-underline-onhover")
                title_el = card.css_first("h3")
                if link is None or title_el is None:
                    continue
                url = (link.attributes.get("href") or "").strip()
                title = title_el.text(strip=True)
                if not url or not title or url in seen:
                    continue
                seen.add(url)
                page_new += 1

                company = _sibling_text(card, "span.tm-building")
                if not company or company.strip().lower() == _PORTAL_AS_COMPANY:
                    company = _COMPANY_UNKNOWN
                teaser = card.css_first("div.description")
                footer = card.css_first("div.button-wrapper")

                out.append(JobPosting(
                    id=stable_id(self.source, url),
                    source=self.source,
                    title=title,
                    company=company,
                    location=_sibling_text(card, "span.tm-location") or "UAE",
                    url=url,
                    apply_url=url,
                    posted_at=_parse_posted(footer.text(strip=True) if footer else None),
                    description=teaser.text(strip=True)[:2000] if teaser else "",
                    tags=["gulf", "uae"],
                ))
            if page_new == 0:
                break

        log.info("talentmate_fetched", n=len(out), q=keywords,
                 country=country or "all")
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Detail pages are public; the body lives in `div.Job-profile-content`."""
        try:
            r = httpx.get(
                str(job.url),
                headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
                timeout=20.0, follow_redirects=True,
            )
            r.raise_for_status()
        except Exception:
            return None
        tree = HTMLParser(r.text)
        node = (tree.css_first("div.Job-profile-content")
                or tree.css_first("div.jobDescription-wrapper"))
        if node is None:
            return None
        text = node.text(separator="\n", strip=True)
        if len(text.split()) < 100:
            return None
        update: dict = {"description": text[:12000]}
        employer = _employer_from_jsonld(tree)
        if employer:
            update["company"] = employer
        return job.model_copy(update=update)
