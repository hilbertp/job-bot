"""remotive.com, public JSON API at /api/remote-jobs."""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://remotive.com/api/remote-jobs"
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


class RemotiveScraper(BaseScraper):
    source = "remotive"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product"}. The API's documented category/search
        # params are silently ignored these days (verified 2026-07-04: any
        # param combination returns the same newest ~38 postings), so filter
        # title/category/tags substring (case-insensitive) client-side like
        # the other API scrapers.
        needle = (query.get("q") or query.get("search") or query.get("category") or "").strip().lower()
        try:
            r = httpx.get(_API_URL, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("remotive_fetch_failed", error=str(exc))
            return []

        out: list[JobPosting] = []
        for entry in data.get("jobs", []):
            url = entry.get("url") or ""
            title = entry.get("title") or ""
            if not url or not title:
                continue
            if needle:
                haystack = " ".join([
                    title,
                    entry.get("category") or "",
                    " ".join(t for t in (entry.get("tags") or []) if isinstance(t, str)),
                ]).lower()
                if needle not in haystack:
                    continue
            salary = (entry.get("salary") or "").strip()
            location = (entry.get("candidate_required_location") or None)
            description = _strip_html(entry.get("description") or "")
            if salary:
                description = f"Salary: {salary}\n\n{description}"
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title.strip(),
                company=(entry.get("company_name") or "Unknown").strip(),
                location=location,
                url=url,
                apply_url=url,
                posted_at=_parse_dt(entry.get("publication_date")),
                description=description[:12000],
                tags=["remote"] + [t for t in (entry.get("tags") or []) if isinstance(t, str)],
            ))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Description is inlined in the fetch() response (same contract as
        working_nomads): return the job when the body clears the 100-word
        floor, None otherwise."""
        text = (job.description or "").strip()
        if len(text.split()) < 100:
            return None
        return job
