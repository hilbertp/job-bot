"""Xing, DACH professional network. Plain HTML scrape via httpx (no Playwright).

The /jobs/search page renders enough server-side that httpx + selectolax works.
Confirmed 2026-05.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
from urllib.parse import urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BASE = "https://www.xing.com"


class XingScraper(BaseScraper):
    source = "xing"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product owner", "location": "Germany"}"""
        params: dict = {"keywords": query.get("q", query.get("keywords", ""))}
        if query.get("location"):
            params["location"] = query["location"]
        url = f"{BASE}/jobs/search?{urlencode(params)}"

        try:
            r = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                log.warning("xing_http_error", status=r.status_code, url=url)
                return []
        except Exception as exc:
            log.warning("xing_fetch_failed", error=str(exc))
            return []

        tree = HTMLParser(r.text)
        out: list[JobPosting] = []
        for card in tree.css("article"):
            link = card.css_first("a[href*='/jobs/']")
            if not link:
                continue
            href = link.attributes.get("href", "") or ""
            if href.startswith("/"):
                href = f"{BASE}{href}"
            elif not href.startswith("http"):
                continue

            # Title / company / location are stable inside Xing job cards.
            title_el = (
                card.css_first("[data-testid*='title']")
                or card.css_first("h2")
                or card.css_first("[class*='title']")
            )
            company_el = card.css_first("[class*='company'], [data-testid*='company']")
            loc_el = card.css_first("[class*='location'], [data-testid*='location']")

            title = title_el.text(strip=True) if title_el else ""
            if not title:
                # Skip non-job articles (sponsorship widgets, etc.)
                continue

            out.append(JobPosting(
                id=stable_id(self.source, href),
                source=self.source,
                title=title,
                company=company_el.text(strip=True) if company_el else "Unknown",
                location=loc_el.text(strip=True) if loc_el else None,
                url=href,
                apply_url=href,
                description=card.text(strip=True)[:2000],
            ))
        time.sleep(random.uniform(1.5, 3.0))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        """Fetch the detail page and return a JobPosting with description populated.

        PRD §7.3 FR-ENR-01.

        Returns None on failure or if the body is too short to be useful
        (< 100 words). The pipeline's enrichment runner treats None as
        "no body available, do not score this posting".

        Implementation note: prefer the same httpx + selectolax stack as
        ``fetch``; reuse _HEADERS and respect a per-call rate limit (≥1s sleep
        after the request). On 429/999, log and return None, do not retry.
        """
        try:
            r = httpx.get(str(job.url), headers=_HEADERS, timeout=20, follow_redirects=True)
        except Exception as exc:
            log.warning("xing_detail_fetch_failed", error=str(exc), url=str(job.url))
            return None
        finally:
            time.sleep(random.uniform(1.0, 1.8))

        if r.status_code in (429, 999):
            log.warning("xing_detail_rate_limited", status=r.status_code, url=str(job.url))
            return None
        if r.status_code != 200:
            log.warning("xing_detail_http_error", status=r.status_code, url=str(job.url))
            return None

        tree = HTMLParser(r.text)
        description = ""

        # Xing job pages include full body in schema.org JSON-LD.
        ld_json = tree.css_first("script[type='application/ld+json']")
        if ld_json is not None:
            try:
                payload = json.loads(ld_json.text())
                if isinstance(payload, dict):
                    raw = str(payload.get("description", ""))
                    description = re.sub(r"<[^>]+>", " ", html.unescape(raw))
                    description = " ".join(description.split())
            except Exception:
                description = ""

        body_el = (
            tree.css_first("section[class*='description']")
            or tree.css_first("div[data-testid*='description']")
            or tree.css_first("article")
            or tree.css_first("main")
        )
        if not description and body_el is not None:
            description = body_el.text(separator="\n", strip=True)

        if len(description.split()) < 100:
            return None
        return job.model_copy(update={"description": description[:12000]})
