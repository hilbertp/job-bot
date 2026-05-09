"""Scraper interface."""
from __future__ import annotations

import hashlib
from typing import Any, Protocol

from ..models import JobPosting


SearchQuery = dict[str, Any]


def stable_id(source: str, url: str) -> str:
    h = hashlib.sha1(f"{source}::{url}".encode()).hexdigest()
    return f"{source}_{h[:16]}"


class BaseScraper(Protocol):
    source: str

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """Fetch postings for one search query. Should be polite (rate-limited).

        Implementations should:
        - timeout aggressively (e.g. 20s per request)
        - identify with a real User-Agent
        - return [] on transient failure rather than raising — log via structlog
        - raise only on programmer errors (bad query shape)
        """
        ...
