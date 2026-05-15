"""dailyremote.com, HTML listings (JSON-LD ItemList) + JSON-LD detail pages.

The listings page hides company names behind a "[Unlock with Premium]"
placeholder; the real company comes from the detail page's JobPosting JSON-LD,
so fetch() returns title + URL only and fetch_detail() fills in everything else.
"""
from __future__ import annotations

import html as html_lib
import json
import re
import time
from urllib.parse import urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import JobPosting
from .base import BaseScraper, SearchQuery, stable_id

log = structlog.get_logger()

_BASE = "https://dailyremote.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_LD_BLOCK_RE = re.compile(
    r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _ld_blocks(html: str) -> list[dict | list]:
    out: list[dict | list] = []
    for raw in _LD_BLOCK_RE.findall(html):
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return HTMLParser(html_lib.unescape(s)).text(separator="\n", strip=True)


def _title_from_listing_name(name: str) -> str:
    # listing entries look like "Product Manager at [Unlock with Premium]"
    marker = " at "
    return name.rpartition(marker)[0].strip() if marker in name else name.strip()


class DailyRemoteScraper(BaseScraper):
    source = "dailyremote"

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        # query example: {"q": "product manager"}, passes through to the
        # site's search parameter, which returns ~20 results per call.
        q = (query.get("q") or "").strip()
        params = {"search": q} if q else {}
        url = f"{_BASE}/remote-jobs"
        if params:
            url = f"{url}?{urlencode(params)}"
        try:
            r = httpx.get(url, headers={"User-Agent": _UA}, timeout=20.0, follow_redirects=True)
            r.raise_for_status()
        except Exception as exc:
            log.warning("dailyremote_fetch_failed", error=str(exc), url=url)
            return []

        item_list: list[dict] = []
        for block in _ld_blocks(r.text):
            entries = block.get("@graph") if isinstance(block, dict) else None
            entries = entries if isinstance(entries, list) else [block]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("@type") == "ItemList":
                    item_list = entry.get("itemListElement") or []
                    break
            if item_list:
                break

        out: list[JobPosting] = []
        for entry in item_list:
            href = entry.get("url") or ""
            name = entry.get("name") or ""
            if not href or not name:
                continue
            title = _title_from_listing_name(name)
            out.append(JobPosting(
                id=stable_id(self.source, href),
                source=self.source,
                title=title,
                company="Unknown",  # filled in by fetch_detail
                url=href,
                apply_url=href,
                description="",
                tags=["remote"],
            ))
        return out

    def fetch_detail(self, job: "JobPosting") -> JobPosting | None:
        try:
            r = httpx.get(
                str(job.url),
                headers={"User-Agent": _UA},
                timeout=20.0,
                follow_redirects=True,
            )
        except Exception:
            return None
        time.sleep(1.0)
        if r.status_code in (429, 999) or r.status_code != 200:
            return None

        posting: dict | None = None
        for block in _ld_blocks(r.text):
            entries = block.get("@graph") if isinstance(block, dict) else None
            entries = entries if isinstance(entries, list) else [block]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                    posting = entry
                    break
            if posting:
                break
        if not posting:
            return None

        description = _strip_html(posting.get("description") or "")
        if len(description.split()) < 100:
            return None

        company = ((posting.get("hiringOrganization") or {}).get("name") or job.company).strip()
        return job.model_copy(update={
            "description": description[:12000],
            "company": company or "Unknown",
        })
