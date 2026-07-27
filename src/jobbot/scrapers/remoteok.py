"""remoteok.com, public JSON API at /api (first element is a legal notice)."""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_API_URL = "https://remoteok.com/api"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _strip_html(s: str) -> str:
    return HTMLParser(s).text(separator="\n", strip=True) if s else ""


def _parse_epoch(v) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(v))
    except (TypeError, ValueError, OSError):
        return None


class RemoteOkScraper(BaseScraper):
    source = "remoteok"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product owner"}; filters position/tags
        # substring (case-insensitive) client-side, the API has no search param.
        needle = (query.get("q") or "").strip().lower()
        try:
            r = httpx.get(_API_URL, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("remoteok_fetch_failed", error=str(exc))
            return []
        if not isinstance(data, list):
            return []

        out: list[JobPosting] = []
        for entry in data:
            if not isinstance(entry, dict) or "legal" in entry:
                continue  # first element is the API terms notice
            url = entry.get("url") or ""
            title = entry.get("position") or ""
            if not url or not title:
                continue
            tags = [t for t in (entry.get("tags") or []) if isinstance(t, str)]
            if needle:
                haystack = " ".join([title] + tags).lower()
                if needle not in haystack:
                    continue
            description = _strip_html(entry.get("description") or "")
            smin, smax = entry.get("salary_min"), entry.get("salary_max")
            if smin or smax:
                description = f"Salary: {smin or '?'} - {smax or '?'} USD\n\n{description}"
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title.strip(),
                company=(entry.get("company") or "Unknown").strip(),
                location=(entry.get("location") or None),
                url=url,
                apply_url=entry.get("apply_url") or url,
                posted_at=_parse_epoch(entry.get("epoch")),
                description=description[:12000],
                tags=["remote"] + tags,
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
