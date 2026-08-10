"""RSS feeds must be fetched with a hard timeout.

Run 347 called `feedparser.parse(<url>)`, which does its own fetch with
urllib and NO default timeout. weworkremotely accepted the connection on
2026-08-09 08:42 and never answered, so the run blocked forever, held the
single-run lock, and the eight scheduled runs behind it were all skipped
while the dashboard kept showing two-day-old results.
"""
from __future__ import annotations

import feedparser
import pytest

from jobbot.scrapers import base, nodesk, weworkremotely

_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Acme: Senior Product Manager</title>
<link>https://example.com/jobs/1</link>
<description>A role.</description></item>
</channel></rss>"""


class _Resp:
    content = _RSS

    def raise_for_status(self):
        return None


def test_no_scraper_calls_feedparser_with_a_url():
    """The regression guard: feedparser must only ever parse bytes we fetched.

    A URL argument means feedparser opens the socket itself, with no timeout,
    which is exactly what wedged run 347.
    """
    import pathlib
    scrapers = pathlib.Path(base.__file__).parent
    offenders = []
    for path in scrapers.glob("*.py"):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if "feedparser.parse(" not in line:
                continue
            if line.lstrip().startswith("#"):
                continue  # prose about the rule, not a call
            arg = line.split("feedparser.parse(", 1)[1]
            # Parsing bytes/content is fine; a URL or _FEED_URL name is not.
            if arg.startswith(("b\"", "b'", "r.content", "resp.content")):
                continue
            offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, (
        "use base.fetch_feed() instead of feedparser.parse(<url>): "
        + "; ".join(offenders)
    )


def test_fetch_feed_passes_a_timeout(monkeypatch):
    import httpx

    seen = {}

    def fake_get(url, **kw):
        seen.update(kw)
        seen["url"] = url
        return _Resp()

    monkeypatch.setattr(httpx, "get", fake_get)
    feed = base.fetch_feed("https://example.com/feed.rss")
    assert seen["timeout"] == base.FEED_TIMEOUT_S
    assert seen["url"] == "https://example.com/feed.rss"
    assert len(feed.entries) == 1


def test_fetch_feed_returns_empty_on_failure(monkeypatch):
    import httpx

    def boom(*a, **kw):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx, "get", boom)
    feed = base.fetch_feed("https://example.com/feed.rss")
    assert feed.entries == []


def test_weworkremotely_survives_a_feed_timeout(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get",
                        lambda *a, **kw: (_ for _ in ()).throw(httpx.ReadTimeout("x")))
    assert weworkremotely.WeWorkRemotelyScraper().fetch({"category": "x"}) == []


def test_nodesk_survives_a_feed_timeout(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get",
                        lambda *a, **kw: (_ for _ in ()).throw(httpx.ReadTimeout("x")))
    assert nodesk.NoDeskScraper().fetch({"q": ""}) == []
