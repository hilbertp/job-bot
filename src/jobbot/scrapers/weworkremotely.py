"""weworkremotely.com — official RSS per category. Easiest source; start here."""
from __future__ import annotations

import feedparser
import httpx
from selectolax.parser import HTMLParser

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

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Fetch the detail page and return a JobPosting with description populated.

        PRD §7.3 FR-ENR-01.

        Returns None on failure or if the body is too short to be useful
        (< 100 words). The pipeline's enrichment runner treats None as
        "no body available, do not score this posting".

        Implementation note: prefer the same httpx + selectolax stack as
        ``fetch``; reuse _HEADERS and respect a per-call rate limit (≥1s sleep
        after the request). On 429/999, log and return None — do not retry.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            r = httpx.get(str(job.url), headers=headers, timeout=20, follow_redirects=True)
        except Exception:
            return None
        if r.status_code in (429, 999) or r.status_code != 200:
            return None

        tree = HTMLParser(r.text)
        # WWR's current page wraps the actual job body in
        # `<section class="lis-container__job">`. The old class-name
        # candidates (`listing-container`, `listing-show-container`,
        # `article`, `main`) match nothing on the live site — when they
        # miss, fetch_detail returns None and the RSS-feed `summary` is
        # left in place, which is the "Related Jobs" sidebar text. That
        # gave every WWR row a 215-word garbage body that scored badly
        # regardless of the actual posting.
        body_el = (
            tree.css_first("section.lis-container__job")
            or tree.css_first("div.lis-container__job")
            or tree.css_first("div.listing-container")
            or tree.css_first("div.listing-show-container")
            or tree.css_first("article")
            or tree.css_first("main")
        )
        description = body_el.text(separator="\n", strip=True) if body_el else ""
        if len(description.split()) < 100:
            return None
        return job.model_copy(update={"description": description[:12000]})
