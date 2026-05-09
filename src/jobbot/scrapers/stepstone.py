"""StepStone (DACH) — Playwright-driven HTML scrape. Throttle aggressively."""
from __future__ import annotations

import random
import time
from urllib.parse import quote_plus

import structlog

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class StepstoneScraper(BaseScraper):
    source = "stepstone"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "python", "l": "Deutschland"}"""
        q = query.get("q", "")
        loc = query.get("l", "Deutschland")
        url = f"https://www.stepstone.de/jobs/{quote_plus(q)}/in-{quote_plus(loc)}"

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("stepstone_playwright_missing")
            return []

        out: list[JobPosting] = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=_UA,
                    viewport={"width": 1280, "height": 900},
                    locale="de-DE",
                )
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                # Accept cookie banner if present
                try:
                    page.click(
                        "[id*='acceptAllButton'], button:has-text('Alle akzeptieren')",
                        timeout=4_000,
                    )
                except Exception:
                    pass
                # Wait for job cards
                page.wait_for_selector("article[data-at='job-item']", timeout=15_000)
                cards = page.query_selector_all("article[data-at='job-item']")
                for card in cards:
                    title_el = card.query_selector("[data-at='job-item-title']")
                    company_el = card.query_selector("[data-at='job-item-company-name']")
                    location_el = card.query_selector("[data-at='job-item-location']")
                    link_el = card.query_selector("a[data-at='job-item-title']")
                    if not (title_el and link_el):
                        continue
                    title = title_el.inner_text().strip()
                    company = company_el.inner_text().strip() if company_el else "Unknown"
                    location = location_el.inner_text().strip() if location_el else None
                    href = link_el.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = f"https://www.stepstone.de{href}"
                    out.append(JobPosting(
                        id=stable_id(self.source, href),
                        source=self.source,
                        title=title,
                        company=company,
                        location=location,
                        url=href,
                        apply_url=href,
                        description=card.inner_text()[:2000],
                    ))
                ctx.close()
                browser.close()
        except Exception as exc:
            log.warning("stepstone_fetch_failed", error=str(exc))
        # Polite inter-query delay
        time.sleep(random.uniform(2.0, 4.0))
        return out
