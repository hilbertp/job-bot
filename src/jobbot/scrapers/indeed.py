"""Indeed — try RSS first; fall back to Playwright. Indeed blocks naive `requests`."""
from __future__ import annotations

from urllib.parse import urlencode

import feedparser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id


class IndeedScraper(BaseScraper):
    source = "indeed"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "python developer", "l": "Berlin", "country": "de"}
        country = query.get("country", "de")
        host = "de.indeed.com" if country == "de" else "www.indeed.com"
        params = {k: query[k] for k in ("q", "l") if k in query}
        rss_url = f"https://{host}/rss?{urlencode(params)}"
        feed = feedparser.parse(rss_url)
        out: list[JobPosting] = []
        for e in feed.entries:
            # Indeed RSS title: "Senior Python Developer - Acme - Berlin"
            parts = [p.strip() for p in e.title.split(" - ")]
            title = parts[0] if parts else e.title
            company = parts[1] if len(parts) > 1 else "Unknown"
            location = parts[2] if len(parts) > 2 else None
            out.append(JobPosting(
                id=stable_id(self.source, e.link),
                source=self.source,
                title=title,
                company=company,
                location=location,
                url=e.link,
                apply_url=e.link,
                description=getattr(e, "summary", "") or "",
            ))
        # TODO: if RSS returns 0 results despite a known-good query,
        # fall back to a Playwright scrape of /jobs?q=...&l=...
        return out
