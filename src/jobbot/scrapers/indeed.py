"""Indeed scraper via Playwright search scraping.

Indeed RSS is unreliable/unavailable for our target queries and regions, so we
use the search page directly.
"""
from __future__ import annotations

from urllib.parse import urlencode, urljoin

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()


class IndeedScraper(BaseScraper):
    source = "indeed"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "python developer", "l": "Berlin", "country": "de"}
        country = query.get("country", "de")
        host = "de.indeed.com" if country == "de" else "www.indeed.com"
        params = {k: query[k] for k in ("q", "l") if k in query}
        return self._fetch_playwright(host, params)

    def _fetch_playwright(self, host: str, params: dict[str, str]) -> list[JobPosting]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            log.warning("indeed_playwright_import_failed", error=str(exc))
            return []

        search_url = f"https://{host}/jobs?{urlencode(params)}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="de-DE",
                )
                page = context.new_page()
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1800)
                    html = page.content()
                finally:
                    context.close()
                    browser.close()
        except PlaywrightTimeoutError:
            log.warning("indeed_playwright_timeout", url=search_url)
            return []
        except Exception as exc:
            log.warning("indeed_playwright_fetch_failed", error=str(exc), url=search_url)
            return []

        tree = HTMLParser(html)
        page_text = tree.body.text(separator=" ", strip=True).lower() if tree.body else ""
        if "additional verification required" in page_text or "security check" in page_text:
            log.warning("indeed_blocked_by_challenge", url=search_url)
            return []

        jobs: list[JobPosting] = []
        seen: set[str] = set()
        card_selectors = [
            "div.job_seen_beacon",
            "div.cardOutline",
            "li[data-testid='result']",
        ]
        cards = []
        for selector in card_selectors:
            cards = tree.css(selector)
            if cards:
                break

        for card in cards:
            link_el = card.css_first("a.jcs-JobTitle") or card.css_first("h2 a")
            if not link_el:
                continue
            href = (link_el.attributes.get("href") or "").strip()
            if not href:
                continue
            url = urljoin(f"https://{host}", href)
            jid = stable_id(self.source, url)
            if jid in seen:
                continue
            seen.add(jid)

            title = (link_el.attributes.get("aria-label") or link_el.text(strip=True) or "").strip()
            company_el = card.css_first("span[data-testid='company-name']") or card.css_first(
                "[data-testid='company-name']"
            )
            location_el = card.css_first("div[data-testid='text-location']") or card.css_first(
                "[data-testid='text-location']"
            )
            desc_el = card.css_first("div[data-testid='job-snippet']")
            if not title:
                continue

            jobs.append(JobPosting(
                id=jid,
                source=self.source,
                title=title,
                company=company_el.text(strip=True) if company_el else "Unknown",
                location=location_el.text(strip=True) if location_el else None,
                url=url,
                apply_url=url,
                description=desc_el.text(separator=" ", strip=True) if desc_el else "",
            ))

        log.info("indeed_playwright_results", fetched=len(jobs), url=search_url)
        return jobs

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            r = httpx.get(str(job.url), headers=headers, timeout=20, follow_redirects=True)
        except Exception as exc:
            log.warning("indeed_detail_fetch_failed", error=str(exc), url=str(job.url))
            return job

        if r.status_code in (429, 999, 403):
            log.warning("indeed_detail_blocked", status=r.status_code, url=str(job.url))
            return job
        if r.status_code != 200:
            log.warning("indeed_detail_http_error", status=r.status_code, url=str(job.url))
            return job

        tree = HTMLParser(r.text)
        body_el = (
            tree.css_first("#jobDescriptionText")
            or tree.css_first("div[data-testid='jobsearch-JobComponent-description']")
            or tree.css_first("main")
        )
        description = body_el.text(separator="\n", strip=True) if body_el else ""
        if not description:
            return job
        return job.model_copy(update={"description": description[:12000]})