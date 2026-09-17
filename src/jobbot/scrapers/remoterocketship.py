"""remoterocketship.com, a remote-only board that links straight to employer ATS pages.

Listing URL: https://www.remoterocketship.com/jobs/<slug>/ where the slug is the
query with spaces turned into hyphens ("product-manager", "product-owner").
Both slugs are real category pages (measured 2026-09-17: 3045 and 372 jobs).
The page is Next.js. The list sits in the `<script id="__NEXT_DATA__">` JSON
at `props.pageProps.initialJobOpenings`, 20 items, newest first. Each item
carries the title, the company (name and slug), the employer's own apply link
(Ashby, Lever, Greenhouse, Workable, iCIMS, Workday), an ISO `created_at`,
the location, and a salary range with a human-readable text.

Paging, measured 2026-09-17: there is none without a login. `?page=N` is
ignored server-side (`initialFilters.page` stays 1 for N=2, 7 and 50). The
client-side pager POSTs to /api/fetch_job_openings/ and answers HTTP 401
"You must be logged in to access more results" from page 2 on, and for
itemsPerPage above 20. So one request per query, the 20 newest postings. We
still send `?page=1`: the bare URL comes from a CDN snapshot that was 28337
seconds old when measured, and any query string bypasses it, so the list we
get is the live one.

Description strategy: the list item has no full text, only a one-line
summary. The board has its own detail page per job at
/company/<company slug>/jobs/<job slug>/ and its `__NEXT_DATA__` holds
`pageProps.jobOpening` with English `roleDescription`, `roleRequirements`
and `benefits` (244 to 389 words combined on four samples). `fetch_detail`
fetches that page and joins the three sections. A dead slug answers HTTP 404
with no redirect, which is the ListingGone signal. 403 and 5xx are transient.
"""
from __future__ import annotations

import json
import re

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, ListingGone, SearchQuery, parse_posted_at, stable_id

log = structlog.get_logger()

_BASE = "https://www.remoterocketship.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_MIN_WORDS = 100


def _slugify(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", q.strip().lower()).strip("-")


def _next_data(html: str) -> dict:
    """Return the parsed `__NEXT_DATA__` JSON, or {} when it is absent."""
    node = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if node is None:
        return {}
    try:
        return json.loads(node.text())
    except ValueError:
        return {}


def _detail_url(item: dict) -> str | None:
    slug = item.get("slug")
    company_slug = (item.get("company") or {}).get("slug")
    if not slug or not company_slug:
        return None
    return f"{_BASE}/company/{company_slug}/jobs/{slug}/"


def _location(item: dict) -> str:
    countries = [c for c in (item.get("locationCountries") or []) if isinstance(c, str) and c]
    if countries:
        return ", ".join(countries)
    return (item.get("location") or "").strip() or "Worldwide"


class RemoteRocketshipScraper(BaseScraper):
    source = "remoterocketship"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product owner"}. The slug page already narrows
        # by job title; the substring filter on title + category is a safety
        # net in case the board widens what it serves under a slug.
        needle = (query.get("q") or "").strip().lower()
        slug = _slugify(needle) or "product-manager"
        list_url = f"{_BASE}/jobs/{slug}/"
        try:
            r = httpx.get(
                list_url,
                params={"page": 1},
                headers={"User-Agent": _UA},
                timeout=20.0,
                follow_redirects=True,
            )
            r.raise_for_status()
            props = _next_data(r.text).get("props", {}).get("pageProps", {})
            items = props.get("initialJobOpenings") or []
        except Exception as exc:
            log.warning("remoterocketship_fetch_failed", url=list_url, error=str(exc))
            return []

        out: list[JobPosting] = []
        seen: set[str] = set()
        for item in items:
            title = (item.get("roleTitle") or item.get("categorizedJobTitle") or "").strip()
            apply_url = item.get("url") or ""
            url = _detail_url(item) or apply_url
            if not title or not url:
                continue
            if needle:
                haystack = f"{title} {item.get('categorizedJobTitle') or ''}".lower()
                if needle not in haystack:
                    continue
            job_id = stable_id(self.source, url)
            if job_id in seen:
                continue
            seen.add(job_id)
            tags = ["remote"]
            salary = (item.get("salaryRange") or {}).get("salaryHumanReadableText")
            if salary:
                tags.append(f"salary: {salary}")
            summary = item.get("twoLineJobDescriptionSummary") or item.get("jobDescriptionSummary") or ""
            try:
                out.append(JobPosting(
                    id=job_id,
                    source=self.source,
                    title=title,
                    company=((item.get("company") or {}).get("name") or "Unknown").strip(),
                    location=_location(item),
                    url=url,
                    apply_url=apply_url or url,
                    posted_at=parse_posted_at(item.get("created_at")),
                    description=summary.strip(),
                    tags=tags,
                ))
            except Exception as exc:
                log.warning("remoterocketship_bad_item", url=url, error=str(exc))
        return out

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        """Fetch the board's own detail page and join its three text sections.

        404 or 410, or a redirect away from a /company/.../jobs/ page, is the
        board saying the posting is gone: raise ListingGone. Anything else
        that fails (403, 5xx, missing JSON, short body) returns None so the
        runner retries on a later run.
        """
        url = str(job.url)
        try:
            r = httpx.get(url, headers={"User-Agent": _UA}, timeout=20.0,
                          follow_redirects=True)
        except Exception as exc:
            log.warning("remoterocketship_detail_failed", url=url, error=str(exc))
            return None
        if r.status_code in (404, 410):
            raise ListingGone(f"http {r.status_code}")
        if r.status_code != 200:
            log.warning("remoterocketship_detail_failed", url=url, status=r.status_code)
            return None
        if "/company/" not in str(r.url) or "/jobs/" not in str(r.url):
            raise ListingGone(f"redirected to {r.url}")

        opening = _next_data(r.text).get("props", {}).get("pageProps", {}).get("jobOpening")
        if not isinstance(opening, dict):
            log.warning("remoterocketship_detail_failed", url=url, error="no jobOpening in page")
            return None
        if opening.get("dateDeleted"):
            raise ListingGone(f"dateDeleted {opening['dateDeleted']}")

        sections = []
        for label, key in (("Role", "roleDescription"),
                           ("Requirements", "roleRequirements"),
                           ("Benefits", "benefits")):
            text = (opening.get(key) or "").strip()
            if text:
                sections.append(f"{label}:\n{text}")
        description = "\n\n".join(sections)
        if len(description.split()) < _MIN_WORDS:
            return None
        return job.model_copy(update={"description": description[:12000]})
