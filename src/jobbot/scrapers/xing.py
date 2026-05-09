"""Xing — DACH professional network. Playwright-driven, parses SSR HTML."""
from __future__ import annotations

import random
import time
from urllib.parse import urlencode

import structlog

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BASE = "https://www.xing.com"


class XingScraper(BaseScraper):
    source = "xing"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """query example: {"q": "python developer", "location": "Germany"}"""
        params: dict = {"keywords": query.get("q", "")}
        if query.get("location"):
            params["location"] = query["location"]
        url = f"{BASE}/jobs/search?{urlencode(params)}"

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("xing_playwright_missing")
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
                # Accept consent if shown
                try:
                    page.click(
                        "button[data-testid='uc-accept-all-button'], "
                        "button:has-text('Alle akzeptieren')",
                        timeout=4_000,
                    )
                except Exception:
                    pass
                # Xing SSR renders job items inside list elements
                page.wait_for_selector(
                    "[data-testid='job-listing-item'], li[class*='JobsList']",
                    timeout=15_000,
                )
                cards = page.query_selector_all(
                    "[data-testid='job-listing-item'], li[class*='JobsList']"
                )
                for card in cards:
                    # Title link
                    link_el = card.query_selector(
                        "a[data-testid='job-listing-item-title-link'], "
                        "a[class*='title'], h2 a"
                    )
                    if not link_el:
                        continue
                    title = link_el.inner_text().strip()
                    href = link_el.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = f"{BASE}{href}"
                    # Company
                    company_el = card.query_selector(
                        "[data-testid='job-listing-item-company-name'], "
                        "[class*='company'], [class*='Company']"
                    )
                    company = company_el.inner_text().strip() if company_el else "Unknown"
                    # Location
                    location_el = card.query_selector(
                        "[data-testid='job-listing-item-location'], "
                        "[class*='location'], [class*='Location']"
                    )
                    location = location_el.inner_text().strip() if location_el else None
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
            log.warning("xing_fetch_failed", error=str(exc))
        time.sleep(random.uniform(2.0, 4.0))
        return out
