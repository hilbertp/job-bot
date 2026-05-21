"""`parse_posted_at` normalises the posting-date signals scrapers hand us
into tz-aware UTC datetimes. This is the prerequisite for categorising
discovery by posting date instead of scrape date.

Sources and their shapes:
  - RSS (WWR, nodesk): feedparser `published_parsed` (time.struct_time)
  - JSON-LD (dailyremote, xing, stepstone): schema.org `datePosted` ISO string
  - HTML (linkedin): <time datetime="..."> or relative text
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timezone

import pytest

from jobbot.scrapers.base import parse_posted_at


def _days_ago(dt: datetime) -> int:
    return (datetime.now(timezone.utc) - dt).days


# ---------------------------------------------------------------------------
# empty / unparseable -> None (never guess)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "  ", "no date here", "asdf"])
def test_unparseable_returns_none(value):
    assert parse_posted_at(value) is None


# ---------------------------------------------------------------------------
# ISO-8601 (schema.org datePosted)
# ---------------------------------------------------------------------------

def test_iso_date_only():
    dt = parse_posted_at("2026-05-10")
    assert dt == datetime(2026, 5, 10, tzinfo=timezone.utc)


def test_iso_datetime_with_z():
    dt = parse_posted_at("2026-05-10T08:30:00Z")
    assert dt == datetime(2026, 5, 10, 8, 30, tzinfo=timezone.utc)


def test_iso_datetime_with_offset():
    dt = parse_posted_at("2026-05-10T08:30:00+02:00")
    assert dt.tzinfo is not None
    # 08:30 +02:00 == 06:30 UTC
    assert dt.astimezone(timezone.utc).hour == 6


def test_naive_iso_is_made_utc():
    dt = parse_posted_at("2026-05-10T08:30:00")
    assert dt.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# feedparser struct_time
# ---------------------------------------------------------------------------

def test_struct_time_from_feedparser():
    # struct_time for 2026-05-10 08:30:00
    st = _time.struct_time((2026, 5, 10, 8, 30, 0, 0, 0, 0))
    dt = parse_posted_at(st)
    assert dt == datetime(2026, 5, 10, 8, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# datetime passthrough
# ---------------------------------------------------------------------------

def test_naive_datetime_made_utc():
    dt = parse_posted_at(datetime(2026, 5, 10, 8, 30))
    assert dt == datetime(2026, 5, 10, 8, 30, tzinfo=timezone.utc)


def test_aware_datetime_unchanged():
    src = datetime(2026, 5, 10, 8, 30, tzinfo=timezone.utc)
    assert parse_posted_at(src) == src


# ---------------------------------------------------------------------------
# relative phrases, English
# ---------------------------------------------------------------------------

def test_today_en():
    assert _days_ago(parse_posted_at("just posted today")) == 0


def test_yesterday_en():
    assert _days_ago(parse_posted_at("yesterday")) == 1


def test_n_days_ago_en():
    assert _days_ago(parse_posted_at("Posted 28 days ago")) == 28


def test_n_weeks_ago_en():
    # 2 weeks = 14 days
    assert _days_ago(parse_posted_at("2 weeks ago")) == 14


def test_hours_ago_en_is_today():
    assert _days_ago(parse_posted_at("5 hours ago")) == 0


# ---------------------------------------------------------------------------
# relative phrases, German (LinkedIn/Xing DE locale)
# ---------------------------------------------------------------------------

def test_heute_de():
    assert _days_ago(parse_posted_at("heute")) == 0


def test_gestern_de():
    assert _days_ago(parse_posted_at("gestern")) == 1


def test_vor_n_tagen_de():
    assert _days_ago(parse_posted_at("vor 3 Tagen")) == 3


def test_vor_n_wochen_de():
    assert _days_ago(parse_posted_at("vor 2 Wochen")) == 14


def test_vor_einem_monat_style_de():
    # "vor 1 Monat" -> ~30 days
    d = _days_ago(parse_posted_at("vor 1 Monat"))
    assert 29 <= d <= 31


# ---------------------------------------------------------------------------
# JobPosting model accepts posted_at
# ---------------------------------------------------------------------------

def test_jobposting_accepts_posted_at():
    from jobbot.models import JobPosting
    job = JobPosting(
        id="x", source="test", title="PM", company="Co",
        url="https://example.com/j",
        posted_at=parse_posted_at("2026-05-10"),
    )
    assert job.posted_at == datetime(2026, 5, 10, tzinfo=timezone.utc)
