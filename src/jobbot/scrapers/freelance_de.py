"""freelance.de — HTML scrape (no public RSS). Use httpx + selectolax. Be polite."""
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

        # NOTE: selectors below are a placeholder — verify against real markup
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
