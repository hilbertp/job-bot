"""weworkremotely.com — official RSS per category. Easiest source; start here."""
from __future__ import annotations

import feedparser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id


class WeWorkRemotelyScraper(BaseScraper):
    source = "weworkremotely"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"category": "remote-programming-jobs"}
        category = query.get("category", "remote-programming-jobs")
        url = f"https://weworkremotely.com/categories/{category}.rss"
        feed = feedparser.parse(url)
        out: list[JobPosting] = []
        for e in feed.entries:
            link = e.link
            # WWR titles look like "Company: Senior X Developer"
            title_full = e.title
            company, _, title = title_full.partition(":")
            out.append(JobPosting(
                id=stable_id(self.source, link),
                source=self.source,
                title=(title or title_full).strip(),
                company=company.strip() or "Unknown",
                url=link,
                apply_url=link,
                description=getattr(e, "summary", "") or "",
                tags=["remote"],
            ))
        return out
