"""brainville.com (largest Nordic freelance/consulting marketplace).

Server-rendered public HTML search; verified 2026-07-17. Anonymous view caps
each query at 5 sample cards plus a total count, so coverage comes from
running several keyword queries rather than paging (page= is ignored
anonymously). Detail pages (/PublicPage/Requisition?id=...) are public.
"""
from __future__ import annotations

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_SEARCH_URL = "https://www.brainville.com/HittaKonsultuppdrag"
_BASE = "https://www.brainville.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BrainvilleScraper(BaseScraper):
    source = "brainville"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product owner"}; anonymous search shows the
        # newest 5 matching cards per keyword.
        params = {"Text": (query.get("q") or "product").strip(), "lang": "en"}
        try:
            r = httpx.get(_SEARCH_URL, params=params, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
        except Exception as exc:
            log.warning("brainville_fetch_failed", error=str(exc))
            return []

        tree = HTMLParser(r.text)
        out: list[JobPosting] = []
        for link in tree.css('a[href^="/PublicPage/Requisition?id="]'):
            title = link.text(strip=True)
            href = link.attributes.get("href") or ""
            if not title or not href:
                continue
            url = _BASE + href
            # location: nearest card wrapper carries a div[title="City, Region, Country"]
            location = None
            remote = False
            parent = link.parent
            for _ in range(6):
                if parent is None:
                    break
                loc_el = parent.css_first("div[data-tooltip][title]")
                if loc_el and loc_el.attributes.get("title"):
                    location = loc_el.attributes["title"]
                for chip in parent.css("span.c_chip"):
                    if chip.text(strip=True).lower() in ("remote", "hybrid"):
                        remote = True
                if loc_el is not None:
                    break
                parent = parent.parent
            out.append(JobPosting(
                id=stable_id(self.source, url),
                source=self.source,
                title=title,
                company="Brainville (anonymous client)",
                location=location or "Nordics",
                url=url,
                apply_url=url,
                description="",
                tags=["freelance", "nordics"] + (["remote"] if remote else []),
            ))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Public detail page carries title, competence area, city, remote flag,
        deadline and skill tags; the full body is account-gated, so bodies stay
        short. Return the page text when it clears the 100-word floor."""
        try:
            r = httpx.get(str(job.url), params={"lang": "en"}, headers={"User-Agent": _UA}, timeout=20.0)
            r.raise_for_status()
        except Exception:
            return None
        tree = HTMLParser(r.text)
        main = tree.css_first("main") or tree.css_first("body")
        text = main.text(separator="\n", strip=True) if main else ""
        if len(text.split()) < 100:
            return None
        return job.model_copy(update={"description": text[:12000]})
