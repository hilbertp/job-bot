"""nodesk.co, official RSS at /remote-jobs/index.xml plus HTML detail pages.

RSS items use the title format "Position Title at Company"; the description in
the feed is a one-line teaser, so fetch_detail pulls the full body from the
listing page.
"""
from __future__ import annotations

import time

import feedparser
import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_FEED_URL = "https://nodesk.co/remote-jobs/index.xml"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _split_title_company(raw: str) -> tuple[str, str]:
    """'Senior PM at Acme' → ('Senior PM', 'Acme'). Fallback returns
    ('<raw>', 'Unknown') when ' at ' is missing."""
    marker = " at "
    if marker in raw:
        title, _, company = raw.rpartition(marker)
        return title.strip(), company.strip()
    return raw.strip(), "Unknown"


class NoDeskScraper(BaseScraper):
    source = "nodesk"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product"}, case-insensitive substring filter on
        # the title. Empty query returns every feed item.
        needle = (query.get("q") or "").strip().lower()
        feed = feedparser.parse(_FEED_URL)
        out: list[JobPosting] = []
        for e in feed.entries:
            link = getattr(e, "link", "") or ""
            raw_title = getattr(e, "title", "") or ""
            if not link or not raw_title:
                continue
            title, company = _split_title_company(raw_title)
            if needle and needle not in title.lower():
                continue
            out.append(JobPosting(
                id=stable_id(self.source, link),
                source=self.source,
                title=title,
                company=company,
                url=link,
                apply_url=link,
                description=getattr(e, "summary", "") or "",
                tags=["remote"],
            ))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        try:
            r = httpx.get(
                str(job.url),
                headers={"User-Agent": _UA},
                timeout=20.0,
                follow_redirects=True,
            )
        except Exception:
            return None
        time.sleep(1.0)
        if r.status_code in (429, 999) or r.status_code != 200:
            return None

        tree = HTMLParser(r.text)
        body_el = (
            tree.css_first("article")
            or tree.css_first("main")
            or tree.css_first("div.post-content")
        )
        description = body_el.text(separator="\n", strip=True) if body_el else ""
        if len(description.split()) < 100:
            return None
        return job.model_copy(update={"description": description[:12000]})
