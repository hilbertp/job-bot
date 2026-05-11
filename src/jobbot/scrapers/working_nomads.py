"""workingnomads.com — public JSON API at /api/exposed_jobs/."""
from __future__ import annotations

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://www.workingnomads.com/api/exposed_jobs/"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _strip_html(s: str) -> str:
    return HTMLParser(s).text(separator="\n", strip=True) if s else ""


class WorkingNomadsScraper(BaseScraper):
    source = "working_nomads"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product manager"} — filters title/description/tags
        # substring (case-insensitive). Empty query returns every listing.
        needle = (query.get("q") or "").strip().lower()
        try:
            r = httpx.get(_API_URL, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("working_nomads_fetch_failed", error=str(exc))
            return []
        if not isinstance(data, list):
            return []

        out: list[JobPosting] = []
        for entry in data:
            url = entry.get("url") or ""
            title = entry.get("title") or ""
            if not url or not title:
                continue
            if needle:
                haystack = " ".join([
                    title,
                    entry.get("tags") or "",
                    entry.get("category_name") or "",
                ]).lower()
                if needle not in haystack:
                    continue
            description = _strip_html(entry.get("description") or "")
            tags_str = entry.get("tags") or ""
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title.strip(),
                company=(entry.get("company_name") or "Unknown").strip(),
                location=(entry.get("location") or None),
                url=url,
                apply_url=url,
                description=description[:12000],
                tags=["remote"] + tags,
            ))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Description is inlined in the fetch() response. Return the same job
        so the enrichment runner records description_scraped=True when the
        word count clears the 100-word floor; return None when it doesn't."""
        text = (job.description or "").strip()
        if len(text.split()) < 100:
            return None
        return job
