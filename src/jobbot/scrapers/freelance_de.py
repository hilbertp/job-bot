"""freelance.de, HTML scrape (no public RSS). Use httpx + selectolax. Be polite."""
from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

UA = "jobbot/0.1 (+mailto:hilbertp@gmail.com)"


class FreelanceDeScraper(BaseScraper):
    source = "freelance_de"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"keywords": ["python", "backend"]}
        kw = " ".join(query.get("keywords", []))
        params = {"_searchString": kw}
        url = f"https://www.freelance.de/search/?{urlencode(params)}"
        try:
            with httpx.Client(headers={"User-Agent": UA}, timeout=20.0) as c:
                r = c.get(url)
                r.raise_for_status()
                time.sleep(1.0)  # politeness
        except Exception:
            return []  # log + return empty per BaseScraper contract

        # NOTE: selectors below are a placeholder, verify against real markup
        # before enabling in production. freelance.de may change layout.
        tree = HTMLParser(r.text)
        out: list[JobPosting] = []
        for card in tree.css("article.project, .project-list-entry"):
            title_el = card.css_first("a.project-title, h2 a")
            if not title_el:
                continue
            title = title_el.text(strip=True)
            href = title_el.attributes.get("href", "")
            if href.startswith("/"):
                href = f"https://www.freelance.de{href}"
            out.append(JobPosting(
                id=stable_id(self.source, href),
                source=self.source,
                title=title,
                company="(see posting)",
                url=href,
                apply_url=href,
                description=card.text(strip=True)[:2000],
                tags=["freelance"],
            ))
        return out

    def fetch_detail(self, job: "JobPosting"):
        """Fetch the detail page and return a JobPosting with description populated.

        PRD §7.3 FR-ENR-01.

        Returns None on failure or if the body is too short to be useful
        (< 100 words). The pipeline's enrichment runner treats None as
        "no body available, do not score this posting".

        Implementation note: prefer the same httpx + selectolax stack as
        ``fetch``; reuse _HEADERS and respect a per-call rate limit (≥1s sleep
        after the request). On 429/999, log and return None, do not retry.
        """
        raise NotImplementedError("Copilot to implement per PRD §7.3 FR-ENR-01")
