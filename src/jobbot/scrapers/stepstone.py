"""StepStone (DACH), plain HTML scrape via httpx. No Playwright needed.

The /jobs/<query>/in-<location> pages render fully server-side with stable
data-at attributes. Confirmed working with httpx + selectolax 2026-05.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
from urllib.parse import quote_plus

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
BASE = "https://www.stepstone.de"
_JOB_ID_RE = re.compile(r"(\d{6,})")


class StepstoneScraper(BaseScraper):
    source = "stepstone"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "product owner", "l": "deutschland"}"""
        q = quote_plus(query.get("q", ""))
        loc = quote_plus(query.get("l", "deutschland")).lower()
        url = f"{BASE}/jobs/{q}/in-{loc}"

        try:
            r = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                log.warning("stepstone_http_error", status=r.status_code, url=url)
                return []
        except Exception as exc:
            log.warning("stepstone_fetch_failed", error=str(exc))
            return []

        tree = HTMLParser(r.text)
        out: list[JobPosting] = []
        for card in tree.css("article[data-at='job-item']"):
            title_el = card.css_first("[data-at='job-item-title']")
            company_el = card.css_first("[data-at='job-item-company-name']")
            loc_el = card.css_first("[data-at='job-item-location']")
            link_el = card.css_first("a[data-at='job-item-title']")
            if not (title_el and link_el):
                continue
            title = title_el.text(strip=True)
            # Skip the rare card whose title is leaked CSS (defensive)
            if title.startswith(".res-") or "{" in title[:5]:
                continue
            href = link_el.attributes.get("href", "")
            if href.startswith("/"):
                href = f"{BASE}{href}"
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
        match = _JOB_ID_RE.search(str(job.url))
        detail_url = f"{BASE}/job/{match.group(1)}" if match else str(job.url)

        try:
            r = httpx.get(detail_url, headers=_HEADERS, timeout=20, follow_redirects=True)
        except Exception as exc:
            log.warning("stepstone_detail_fetch_failed", error=str(exc), url=detail_url)
            return None
        finally:
            time.sleep(random.uniform(1.0, 1.8))

        if r.status_code in (429, 999):
            log.warning("stepstone_detail_rate_limited", status=r.status_code, url=detail_url)
            return None
        if r.status_code != 200:
            log.warning("stepstone_detail_http_error", status=r.status_code, url=detail_url)
            return None

        tree = HTMLParser(r.text)
        description = ""

        # StepStone's /job/<id> page reliably exposes full text in JSON-LD.
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
            tree.css_first("div[data-at='jobad-description']")
            or tree.css_first("section[data-testid='job-description']")
            or tree.css_first("div[class*='job-description']")
            or tree.css_first("main")
        )
        if not description and body_el is not None:
            description = body_el.text(separator="\n", strip=True)

        if len(description.split()) < 100:
            return None
        return job.model_copy(update={"description": description[:12000]})
