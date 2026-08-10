"""Scraper interface."""
from __future__ import annotations

import hashlib
import re
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import structlog

from ..models import JobPosting

log = structlog.get_logger()


SearchQuery = dict[str, Any]


class ListingGone(Exception):
    """The detail page proves the posting has been pulled from the board.

    `fetch_detail` returning None means "no usable body this time", which is
    a transient verdict: the enrichment runner retries such rows on later
    runs. A listing that answers HTTP 410, or redirects to a generic search
    page, will never produce a body, and retrying it every run is pure
    waste. Measured 2026-07-31: 37 of 100 detail fetches failed, dominated
    by exactly these two shapes.

    Raise this instead of returning None when the source has told us the
    posting is dead. The runner marks the row `listing_expired`, which is a
    terminal status, so it leaves both the enrichment and the scoring queue
    for good.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def stable_id(source: str, url: str) -> str:
    h = hashlib.sha1(f"{source}::{url}".encode()).hexdigest()
    return f"{source}_{h[:16]}"


# Feed fetches MUST go through here, never `feedparser.parse(<url>)`.
# feedparser does its own fetch with urllib, which has NO default timeout, so
# a server that accepts the connection and then never answers hangs the whole
# run forever. That is not hypothetical: run 347 blocked on the
# weworkremotely RSS feed at 2026-08-09 08:42 and was still blocked 32 hours
# later, holding the single-run lock, so all eight scheduled runs after it
# were skipped and the dashboard sat on two-day-old data.
FEED_TIMEOUT_S = 20.0


def fetch_feed(url: str, *, timeout: float = FEED_TIMEOUT_S, headers: dict | None = None):
    """Fetch an RSS/Atom feed with a hard timeout, then parse the bytes.

    Returns the parsed feedparser result, or a result with no entries when the
    fetch fails, so callers keep their "return [] on failure" contract.
    """
    import feedparser  # local import: keeps this module importable without it
    import httpx

    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers=headers or {})
        r.raise_for_status()
    except Exception as exc:
        log.warning("feed_fetch_failed", url=url, error=str(exc))
        return feedparser.parse(b"")
    return feedparser.parse(r.content)


# Relative-date phrase units, English + German, mapped to a timedelta kind.
_REL_RE = re.compile(
    r"(\d+)\s*"
    r"(minuten|minute|min|stunden|stunde|hours|hour|hr|"
    r"tagen|tage|tag|days|day|"
    r"wochen|woche|weeks|week|"
    r"monaten|monate|monat|months|month)",
    re.IGNORECASE,
)


def parse_posted_at(value: Any) -> datetime | None:
    """Normalise a posting-date signal into a tz-aware UTC datetime.

    Accepts the shapes scrapers actually hand us:
      - feedparser's `published_parsed` (time.struct_time)
      - a datetime (returned as-is, made tz-aware)
      - an ISO-8601 string (schema.org `datePosted`, e.g. "2026-05-10" or
        "2026-05-10T08:00:00Z")
      - a relative phrase in English or German ("posted 28 days ago",
        "vor 3 Tagen", "heute", "yesterday", "2 weeks ago")

    Returns None when nothing parseable is present, callers then leave
    `JobPosting.posted_at` unset and the dashboard falls back to
    `first_seen_at` as before. We never guess.
    """
    if value is None or value == "":
        return None
    if isinstance(value, _time.struct_time):
        return datetime(*value[:6], tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    s = str(value).strip()
    if not s:
        return None

    # ISO-8601 first (schema.org datePosted, RSS already-formatted dates).
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    return _parse_relative(s)


def _parse_relative(s: str) -> datetime | None:
    low = s.lower()
    now = datetime.now(timezone.utc)
    if any(w in low for w in ("today", "heute", "just posted", "gerade", "soeben")):
        return now
    if any(w in low for w in ("yesterday", "gestern")):
        return now - timedelta(days=1)
    m = _REL_RE.search(low)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("min"):
        return now  # sub-hour, treat as today
    if unit.startswith(("stunde", "stunden", "hour", "hr")):
        return now - timedelta(hours=n)
    if unit.startswith(("tag", "day")):
        return now - timedelta(days=n)
    if unit.startswith(("woche", "wochen", "week")):
        return now - timedelta(weeks=n)
    if unit.startswith(("monat", "month")):
        return now - timedelta(days=30 * n)
    return None


class BaseScraper(Protocol):
    source: str

    def fetch(self, query: SearchQuery) -> list[JobPosting]:
        """Fetch postings for one search query. Should be polite (rate-limited).

        Implementations should:
        - timeout aggressively (e.g. 20s per request)
        - identify with a real User-Agent
        - return [] on transient failure rather than raising, log via structlog
        - raise only on programmer errors (bad query shape)
        """
        ...
