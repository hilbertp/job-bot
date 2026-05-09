"""freelancermap.de — official RSS for searches via /job_rss.php."""
from __future__ import annotations

from urllib.parse import urlencode

import feedparser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id


class FreelancermapScraper(BaseScraper):
    source = "freelancermap"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"keywords": ["python", "data"], "remote": true}
        keywords = " ".join(query.get("keywords", []))
        params = {"query": keywords}
        if query.get("remote"):
            params["remoteInPercent"] = "100"
        url = f"https://www.freelancermap.de/projektboerse.html?{urlencode(params)}&output=rss"
        feed = feedparser.parse(url)
        out: list[JobPosting] = []
        for e in feed.entries:
            out.append(JobPosting(
                id=stable_id(self.source, e.link),
                source=self.source,
                title=e.title,
                company=getattr(e, "author", "Unknown"),
                url=e.link,
                apply_url=e.link,
                description=getattr(e, "summary", "") or "",
                tags=["freelance"],
            ))
        return out
