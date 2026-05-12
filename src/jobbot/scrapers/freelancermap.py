"""freelancermap.de — HTML scrape (RSS was deprecated in 2024-25).

Project URLs use the pattern /projekt/<slug>. Listing pages render server-side.
Confirmed 2026-05.
"""
from __future__ import annotations

import random
import time
from urllib.parse import urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BASE = "https://www.freelancermap.de"


class FreelancermapScraper(BaseScraper):
    source = "freelancermap"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"keywords": ["product", "owner"], "remote": True}"""
        kw = " ".join(query.get("keywords", [])) or query.get("q", "")
        params: dict = {"query": kw}
        if query.get("remote"):
            params["remoteInPercent"] = "100"
        url = f"{BASE}/projektboerse.html?{urlencode(params)}"

        try:
            r = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                log.warning("freelancermap_http_error", status=r.status_code, url=url)
                return []
        except Exception as exc:
            log.warning("freelancermap_fetch_failed", error=str(exc))
            return []

        tree = HTMLParser(r.text)
        out: list[JobPosting] = []
        seen: set[str] = set()
        # Only "/projekt/<slug>" (singular) is a project. "/projekte/<category>" is taxonomy.
        for a in tree.css("a[href^='/projekt/']"):
            href = a.attributes.get("href", "") or ""
            if href in seen:
                continue
            seen.add(href)
            full = f"{BASE}{href}"
            title = a.text(strip=True)
            if len(title) < 6:  # filter empty/icon links
                continue
            out.append(JobPosting(
                id=stable_id(self.source, full),
                source=self.source,
                title=title,
                # freelancermap hides the employer behind their login wall, so neither
                # the listing nor the public detail page exposes the real company name.
                # The placeholder is on the state.py _COMPANY_PLACEHOLDERS list so it
                # never overwrites a real name elsewhere.
                company="freelancermap (Auftraggeber anonym)",
                url=full,
                apply_url=full,
                description=title,  # full description requires a detail-page fetch
                tags=["freelance"],
            ))
        time.sleep(random.uniform(1.5, 3.0))
        return out

    def fetch_detail(self, job: "JobPosting"):
        """Fetch the detail page and return a JobPosting with description populated.

        PRD §7.3 FR-ENR-01.

        Returns None on failure or if the body is too short to be useful
        (< 100 words). The pipeline's enrichment runner treats None as
        "no body available, do not score this posting".

        Implementation note: prefer the same httpx + selectolax stack as
        ``fetch``; reuse _HEADERS and respect a per-call rate limit (≥1s sleep
        after the request). On 429/999, log and return None — do not retry.
        """
        try:
            r = httpx.get(str(job.url), headers=_HEADERS, timeout=20, follow_redirects=True)
        except Exception as exc:
            log.warning("freelancermap_detail_fetch_failed", error=str(exc), url=str(job.url))
            return None
        finally:
            time.sleep(random.uniform(1.0, 1.8))

        if r.status_code in (429, 999):
            log.warning("freelancermap_detail_rate_limited", status=r.status_code, url=str(job.url))
            return None
        if r.status_code != 200:
            log.warning("freelancermap_detail_http_error", status=r.status_code, url=str(job.url))
            return None

        tree = HTMLParser(r.text)
        body_el = (
            tree.css_first("section[class*='description']")
            or tree.css_first("div[class*='project-description']")
            or tree.css_first("div[class*='projektbeschreibung']")
            or tree.css_first("article")
            or tree.css_first("main")
        )
        description = body_el.text(separator="\n", strip=True) if body_el else ""
        if len(description.split()) < 100:
            return None
        return job.model_copy(update={"description": description[:12000]})
