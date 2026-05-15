"""LinkedIn, public guest jobs endpoint (HTML).

The /jobs-guest/jobs/api/seeMoreJobPostings/search endpoint returns ~10 clean
SSR job cards per page without authentication. We page through it to collect
more results. Optional LINKEDIN_LI_AT cookie unlocks the richer authenticated
search page.

Card descriptions are tiny (~150 chars). For meaningful match scoring we also
expose `fetch_detail(job)`, which hits /jobs-guest/jobs/api/jobPosting/<id> and
returns the full description plus criteria (seniority, employment type), also
unauthenticated.

Limits:
- LinkedIn rate-limits aggressively. Keep queries sparse (≥3s between calls).
- NEVER enable auto_submit on this source, Easy Apply automation is forbidden
  by LinkedIn's User Agreement.
"""
from __future__ import annotations

import os
import random
import re
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

# How many guest-API pages to fetch per query (each returns ~10 cards).
# Keep this conservative, LinkedIn issues 429/999 above ~5 pages/min.
_PAGES_PER_QUERY = 3


class LinkedInScraper(BaseScraper):
    source = "linkedin"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"keywords": "product owner", "location": "Germany"}"""
        cookie = os.getenv("LINKEDIN_LI_AT") or os.getenv("LINKEDIN_SESSION_COOKIE")
        headers = _HEADERS.copy()
        if cookie:
            headers["Cookie"] = f"li_at={cookie}"

        out: list[JobPosting] = []
        seen_ids: set[str] = set()

        for page in range(_PAGES_PER_QUERY):
            params = {
                "keywords": query.get("keywords", ""),
                "location": query.get("location", ""),
                "f_TPR": query.get("time_range", "r604800"),  # default: last 7 days
                "start": page * 10,
            }
            url = f"{BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search?{urlencode(params)}"

            try:
                r = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
            except Exception as exc:
                log.warning("linkedin_fetch_failed", error=str(exc), page=page)
                break

            if r.status_code == 429 or r.status_code == 999:
                log.warning("linkedin_rate_limited", status=r.status_code, page=page)
                break
            if r.status_code != 200:
                log.warning("linkedin_http_error", status=r.status_code, page=page)
                break

            tree = HTMLParser(r.text)
            cards = tree.css("div.base-card")
            if not cards:
                # No more results, stop paging.
                break

            for card in cards:
                title_el = card.css_first("h3.base-search-card__title")
                company_el = (
                    card.css_first("h4.base-search-card__subtitle a")
                    or card.css_first("h4.base-search-card__subtitle")
                )
                loc_el = card.css_first("span.job-search-card__location")
                link_el = card.css_first("a.base-card__full-link")
                if not (title_el and link_el):
                    continue
                href = link_el.attributes.get("href", "") or ""
                if not href:
                    continue
                # Strip tracking query params for stable dedup.
                href = href.split("?")[0]
                jid = stable_id(self.source, href)
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)
                out.append(JobPosting(
                    id=jid,
                    source=self.source,
                    title=title_el.text(strip=True),
                    company=company_el.text(strip=True) if company_el else "Unknown",
                    location=loc_el.text(strip=True) if loc_el else None,
                    url=href,
                    apply_url=href,
                    description=card.text(strip=True)[:2000],
                ))

            time.sleep(random.uniform(3.0, 5.0))

        return out

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        """Fetch the full job posting and return a JobPosting with enriched description.

        Uses /jobs-guest/jobs/api/jobPosting/<id>, same unauth endpoint as the
        card listing. Returns None if the detail page can't be parsed.
        """
        m = re.search(r"/jobs/view/[^/]*?(\d{6,})", str(job.url)) or re.search(
            r"-(\d{6,})(?:[/?].*)?$", str(job.url)
        )
        if not m:
            return None
        job_id = m.group(1)
        cookie = os.getenv("LINKEDIN_LI_AT") or os.getenv("LINKEDIN_SESSION_COOKIE")
        headers = _HEADERS.copy()
        if cookie:
            headers["Cookie"] = f"li_at={cookie}"
        url = f"{BASE}/jobs-guest/jobs/api/jobPosting/{job_id}"
        try:
            r = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
        except Exception as exc:
            log.warning("linkedin_detail_fetch_failed", error=str(exc), job_id=job_id)
            return None
        if r.status_code in (429, 999):
            log.warning("linkedin_detail_rate_limited", status=r.status_code, job_id=job_id)
            return None
        if r.status_code != 200:
            log.warning("linkedin_detail_http_error", status=r.status_code, job_id=job_id)
            return None
        tree = HTMLParser(r.text)
        body = tree.css_first("div.show-more-less-html__markup") or tree.css_first(
            "div.description__text"
        )
        description = body.text(strip=True) if body else ""

        # Append the criteria block (Seniority level, Employment type, etc.) so
        # the LLM can use it for seniority/role-fit scoring.
        crit_lines = []
        for k_el, v_el in zip(
            tree.css("h3.description__job-criteria-subheader"),
            tree.css("span.description__job-criteria-text"),
        ):
            crit_lines.append(f"{k_el.text(strip=True)}: {v_el.text(strip=True)}")
        if crit_lines:
            description = (description + "\n\nCriteria:\n" + "\n".join(crit_lines)).strip()

        if not description:
            return None
        return job.model_copy(update={"description": description[:8000]})
