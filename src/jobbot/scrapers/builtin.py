"""builtin.com remote product jobs (Built In, the US tech-metro job network).

List page: https://builtin.com/jobs/remote/product?search=<kw>&page=<n>.
Measured 2026-09-17: HTTP 200, about 316 KB, server-rendered, 25 cards per
page as `div[data-id="job-card"]`, and `&page=2` returns 25 different cards
with no overlap, so three pages is 75 postings. Each card names the employer
in `a[data-id="company-title"]` and the role in `a[data-id="job-card-title"]`.
Product Owner has its own page at /jobs/remote/product/search/product-owner
(4 cards on the day, two of them Product Manager titles), so every query is
also filtered on the title client-side.

Detail page: https://builtin.com/job/<slug>/<id>, HTTP 200, about 81 KB,
server-rendered. It carries a schema.org JobPosting inside a JSON-LD
`@graph`. The script type is written as `application/ld&#x2B;json` in the
raw HTML, which is why a plain text search for the block misses it; the
parser decodes the entity. That block gives description, employer, datePosted
and applicantLocationRequirements. The visible "The Role" section is the
fallback when the block is missing. A dead job answers HTTP 404.

Built In's remote section is mostly US-remote, but the sampled posting listed
27 EU countries, so the location comes from the JSON-LD when it names any.
Applying runs through Built In's own account ("Sign up to apply"), so the
apply URL is the Built In job URL itself.
"""
from __future__ import annotations

import json
import re
import time

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, ListingGone, SearchQuery, parse_posted_at, stable_id

log = structlog.get_logger()

_BASE = "https://builtin.com"
_SEARCH_URL = f"{_BASE}/jobs/remote/product"
# Role pages Built In publishes next to the search. Titles are still filtered.
_ROLE_PAGES = {"product owner": f"{_SEARCH_URL}/search/product-owner"}
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}
_MAX_PAGES = 3
_PAUSE_S = 1.5
_MIN_WORDS = 100
_DEFAULT_LOCATION = "United States (Remote)"
_COUNTRY_NAMES = {
    "USA": "United States", "GBR": "United Kingdom", "DEU": "Germany",
    "CAN": "Canada", "CYP": "Cyprus", "AUT": "Austria", "CHE": "Switzerland",
}
_POSTED_RE = re.compile(r"Posted\s+\d+\s+\w+\s+Ago", re.IGNORECASE)
_READ_MORE = "Read Full Description"


def _jobposting_jsonld(tree: HTMLParser) -> dict:
    """The schema.org JobPosting dict, or {} when the page has none."""
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except (ValueError, TypeError):
            continue
        items = data.get("@graph", [data]) if isinstance(data, dict) else data
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _html_to_text(html: str | None) -> str:
    if not html:
        return ""
    return HTMLParser(html).text(separator="\n", strip=True)


def _role_section_text(tree: HTMLParser) -> str:
    """Visible fallback: the box right after the "The Role" banner.

    The banner is `div.bg-midnight` with that exact text; the body is the
    next element. The apply widget sits in a later column, so it never
    leaks in, but the "Read Full Description" toggle does and is stripped.
    """
    for banner in tree.css("div.bg-midnight"):
        if banner.text(strip=True) != "The Role":
            continue
        body = banner.next
        while body is not None and body.tag != "div":
            body = body.next
        if body is None:
            return ""
        text = body.text(separator="\n", strip=True)
        return text.replace(_READ_MORE, "").strip()
    return ""


def _company(posting: dict, tree: HTMLParser) -> str | None:
    org = posting.get("hiringOrganization")
    name = org.get("name") if isinstance(org, dict) else None
    if name and str(name).strip():
        return str(name).strip()
    for a in tree.css('a[href^="/company/"]'):
        text = a.text(strip=True)
        if text and not text.startswith("View"):
            return text
    return None


def _location(posting: dict) -> str | None:
    """Country list from applicantLocationRequirements, None when absent."""
    reqs = posting.get("applicantLocationRequirements") or []
    codes: list[str] = []
    for item in reqs if isinstance(reqs, list) else [reqs]:
        name = item.get("name") if isinstance(item, dict) else None
        if name and str(name).strip() not in codes:
            codes.append(str(name).strip())
    if not codes:
        return None
    if len(codes) == 1:
        return f"{_COUNTRY_NAMES.get(codes[0], codes[0])} (Remote)"
    shown = ", ".join(codes[:6])
    more = len(codes) - 6
    return f"Remote: {shown}" + (f" and {more} more" if more > 0 else "")


class BuiltInScraper(BaseScraper):
    source = "builtin"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product manager"}"""
        keywords = (query.get("q") or "product manager").strip()
        needles = [t for t in keywords.lower().split() if t]
        role_url = _ROLE_PAGES.get(keywords.lower())
        out: list[JobPosting] = []
        seen: set[str] = set()

        for page in range(1, _MAX_PAGES + 1):
            params: dict = {"page": page}
            if role_url is None:
                params["search"] = keywords
            if page > 1:
                time.sleep(_PAUSE_S)
            try:
                r = httpx.get(role_url or _SEARCH_URL, params=params, headers=_HEADERS,
                              timeout=20.0, follow_redirects=True)
                r.raise_for_status()
            except Exception as exc:
                log.warning("builtin_fetch_failed", error=str(exc), page=page, q=keywords)
                break

            cards = HTMLParser(r.text).css('div[data-id="job-card"]')
            if not cards:
                break
            page_new = 0
            for card in cards:
                link = card.css_first('a[data-id="job-card-title"]')
                if link is None:
                    continue
                href = (link.attributes.get("href") or "").strip()
                title = link.text(strip=True)
                if not href or not title:
                    continue
                url = href if href.startswith("http") else f"{_BASE}{href}"
                if url in seen or not all(n in title.lower() for n in needles):
                    continue
                seen.add(url)
                page_new += 1
                company_el = card.css_first('a[data-id="company-title"]')
                company = company_el.text(strip=True) if company_el else ""
                clock = card.css_first("i.fa-clock")
                ago = clock.parent.text(strip=True) if clock and clock.parent else None
                out.append(JobPosting(
                    id=stable_id(self.source, url),
                    source=self.source,
                    title=title,
                    company=company or "Built In (see detail)",
                    location=_DEFAULT_LOCATION,
                    url=url,
                    apply_url=url,
                    posted_at=parse_posted_at(ago),
                    tags=["remote", "us"],
                ))
            if page_new == 0:
                break

        log.info("builtin_fetched", n=len(out), q=keywords)
        return out

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        """JSON-LD first, visible "The Role" box second, 100-word floor.

        404 or 410, or a redirect off the /job/ path, means the posting is
        gone: raise ListingGone. 403, 5xx and short bodies return None so the
        runner retries later.
        """
        url = str(job.url)
        try:
            r = httpx.get(url, headers=_HEADERS, timeout=20.0, follow_redirects=True)
        except Exception as exc:
            log.warning("builtin_detail_failed", url=url, error=str(exc))
            return None
        if r.status_code in (404, 410):
            raise ListingGone(f"builtin returned HTTP {r.status_code}")
        if r.status_code != 200:
            log.warning("builtin_detail_failed", url=url, status=r.status_code)
            return None
        if "/job/" not in str(r.url):
            raise ListingGone(f"builtin redirected to {str(r.url)[:120]}")

        tree = HTMLParser(r.text)
        posting = _jobposting_jsonld(tree)
        text = _html_to_text(posting.get("description"))
        if len(text.split()) < _MIN_WORDS:
            text = _role_section_text(tree)
        if len(text.split()) < _MIN_WORDS:
            return None

        update: dict = {"description": text[:12000]}
        company = _company(posting, tree)
        if company:
            update["company"] = company
        location = _location(posting)
        if location:
            update["location"] = location
        posted_match = _POSTED_RE.search(r.text)
        posted = (parse_posted_at(posting.get("datePosted"))
                  or parse_posted_at(posted_match.group(0) if posted_match else None))
        if posted:
            update["posted_at"] = posted
        return job.model_copy(update=update)
