"""free-work.com (FR/EU IT freelance board, ex Freelance-Info).

Public API-Platform endpoint at /api/job_postings (hydra JSON-LD).
Verified 2026-07-17: searchKeywords + contracts=contractor filter server-side;
`order[...]` params return HTTP 400, so sort client-side on publishedAt.
"""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://www.free-work.com/api/job_postings"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _strip_html(s: str) -> str:
    return HTMLParser(s).text(separator="\n", strip=True) if s else ""


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class FreeWorkScraper(BaseScraper):
    source = "free_work"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product owner"}; always contractor missions.
        params = {
            "contracts": "contractor",
            "searchKeywords": (query.get("q") or "product").strip(),
            "itemsPerPage": "30",
            "page": "1",
        }
        try:
            r = httpx.get(_API_URL, params=params, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("free_work_fetch_failed", error=str(exc))
            return []

        out: list[JobPosting] = []
        for entry in data.get("hydra:member", []):
            title = entry.get("title") or ""
            slug = entry.get("slug") or ""
            if not title or not slug:
                continue
            company = ((entry.get("company") or {}).get("name")) or "Unknown"
            # canonical page URL (jobs live under the tech-it vertical)
            url = f"https://www.free-work.com/fr/tech-it/job-mission/{slug}"
            remote = entry.get("remoteMode") or "none"
            loc = ((entry.get("location") or {}).get("label")) or ""
            location = f"{loc} (remote: {remote})" if loc else f"remote: {remote}"
            desc = _strip_html(entry.get("description") or "")
            dmin, dmax = entry.get("minDailySalary"), entry.get("maxDailySalary")
            if dmin or dmax:
                cur = entry.get("currency") or "EUR"
                desc = f"Tagessatz: {dmin or '?'} - {dmax or '?'} {cur}\n\n{desc}"
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title.strip(),
                company=company.strip(),
                location=location,
                url=url,
                apply_url=entry.get("applicationUrl") or url,
                posted_at=_parse_dt(entry.get("publishedAt")),
                description=desc[:12000],
                tags=["freelance", f"remote:{remote}"]
                     + [s.get("name") for s in (entry.get("skills") or []) if isinstance(s, dict) and s.get("name")],
            ))
        # newest first (no server-side ordering available)
        out.sort(key=lambda j: j.posted_at or datetime.min, reverse=True)
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Description is inlined in the fetch() response (same contract as
        working_nomads): return the job when the body clears the 100-word
        floor, None otherwise."""
        text = (job.description or "").strip()
        if len(text.split()) < 100:
            return None
        return job
