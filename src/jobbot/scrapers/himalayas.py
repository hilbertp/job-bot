"""himalayas.app, public JSON API at /jobs/api (limit/offset paging)."""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://himalayas.app/jobs/api"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_PAGE_SIZE = 20   # the API ignores larger limits and returns 20 per page
_PAGES = 5        # newest 100 postings per fetch (offset paging)


def _strip_html(s: str) -> str:
    return HTMLParser(s).text(separator="\n", strip=True) if s else ""


def _parse_epoch(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v))
    except (TypeError, ValueError, OSError):
        return None


class HimalayasScraper(BaseScraper):
    source = "himalayas"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product owner"}; the API has no search param,
        # so page through the newest _PAGES * _PAGE_SIZE postings and filter
        # title/categories substring (case-insensitive) client-side.
        needle = (query.get("q") or "").strip().lower()
        entries: list[dict] = []
        for page in range(_PAGES):
            try:
                r = httpx.get(
                    _API_URL,
                    params={"limit": _PAGE_SIZE, "offset": page * _PAGE_SIZE},
                    headers={"User-Agent": _UA},
                    timeout=20.0,
                )
                r.raise_for_status()
                batch = r.json().get("jobs", [])
            except Exception as exc:
                log.warning("himalayas_fetch_failed", page=page, error=str(exc))
                break
            if not batch:
                break
            entries.extend(batch)

        out: list[JobPosting] = []
        for entry in entries:
            title = entry.get("title") or ""
            url = entry.get("guid") or entry.get("applicationLink") or ""
            if not url or not title:
                continue
            categories = [c for c in (entry.get("categories") or []) if isinstance(c, str)]
            if needle:
                haystack = " ".join([title] + categories).lower()
                if needle not in haystack:
                    continue
            description = _strip_html(entry.get("description") or entry.get("excerpt") or "")
            locations = entry.get("locationRestrictions") or []
            location = ", ".join(locations) if locations else "Worldwide"
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title.strip(),
                company=(entry.get("companyName") or "Unknown").strip(),
                location=location,
                url=url,
                apply_url=entry.get("applicationLink") or url,
                posted_at=_parse_epoch(entry.get("pubDate")),
                description=description[:12000],
                tags=["remote"] + categories,
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
