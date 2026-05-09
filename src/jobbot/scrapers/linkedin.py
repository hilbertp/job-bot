"""LinkedIn — public guest jobs endpoint (HTML).

Approach: httpx GET on the public /jobs/search page, which renders SSR HTML
containing structured job data. We parse the embedded JSON-LD and/or the
`<ul class="jobs-search__results-list">` cards.

Important limitations:
- LinkedIn rate-limits aggressively; keep queries sparse.
- NEVER enable auto_submit on this source — LinkedIn ToS explicitly forbids
  automated Easy Apply.
- If blocked, options: Official Jobs API (paid), Proxycurl, or manual review.
"""
from __future__ import annotations

import json
import random
import time
from urllib.parse import urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BASE = "https://www.linkedin.com"


class LinkedInScraper(BaseScraper):
    source = "linkedin"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"keywords": "python developer", "location": "Germany"}"""
        params = {
            "keywords": query.get("keywords", ""),
            "location": query.get("location", ""),
            "f_TPR": "r86400",  # last 24 h
            "position": 1,
            "pageNum": 0,
        }
        url = f"{BASE}/jobs/search/?{urlencode(params)}"

        try:
            with httpx.Client(headers=_HEADERS, timeout=20.0, follow_redirects=True) as c:
                r = c.get(url)
                if r.status_code != 200:
                    log.warning("linkedin_http_error", status=r.status_code)
                    return []
                html = r.text
        except Exception as exc:
            log.warning("linkedin_fetch_failed", error=str(exc))
            return []

        out: list[JobPosting] = []

        # 1) Try JSON-LD embedded in <script type="application/ld+json">
        tree = HTMLParser(html)
        for script in tree.css("script[type='application/ld+json']"):
            try:
                data = json.loads(script.text() or "{}")
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if item.get("@type") not in ("JobPosting", "ListItem"):
                        continue
                    posting = item if item.get("@type") == "JobPosting" else item.get("item", {})
                    job_url = posting.get("url") or posting.get("@id") or ""
                    if not job_url:
                        continue
                    title = posting.get("title") or posting.get("name") or ""
                    org = posting.get("hiringOrganization", {})
                    company = org.get("name") or "Unknown"
                    loc_obj = posting.get("jobLocation", {})
                    location = (
                        loc_obj.get("address", {}).get("addressLocality")
                        if isinstance(loc_obj, dict) else None
                    )
                    out.append(JobPosting(
                        id=stable_id(self.source, job_url),
                        source=self.source,
                        title=title,
                        company=company,
                        location=location,
                        url=job_url,
                        apply_url=job_url,
                        description=posting.get("description", "")[:3000],
                    ))
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        # 2) Fallback: parse SSR HTML cards
        if not out:
            for card in tree.css("li.result-card, li[class*='job-result-card']"):
                title_el = card.css_first(
                    "h3.base-search-card__title, "
                    "span[class*='title'], a[class*='title']"
                )
                company_el = card.css_first(
                    "h4.base-search-card__subtitle, [class*='company-name']"
                )
                location_el = card.css_first(
                    "span.job-search-card__location, [class*='location']"
                )
                link_el = card.css_first("a.base-card__full-link, a[class*='full-link']")
                if not (title_el and link_el):
                    continue
                href = link_el.attributes.get("href", "")
                if not href:
                    continue
                out.append(JobPosting(
                    id=stable_id(self.source, href),
                    source=self.source,
                    title=title_el.text(strip=True),
                    company=company_el.text(strip=True) if company_el else "Unknown",
                    location=location_el.text(strip=True) if location_el else None,
                    url=href,
                    apply_url=href,
                    description=card.text(strip=True)[:2000],
                ))

        time.sleep(random.uniform(3.0, 6.0))
        return out
