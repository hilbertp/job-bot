"""Apply channel derivation per PRD §7.7 FR-APP-01.

Pure presentation helper — no DB writes, no schema change.
"""
from __future__ import annotations

import sqlite3

import pytest

from jobbot.state import apply_channel, apply_channel_ats_name


# --------------------------- channel selection ----------------------------


@pytest.mark.parametrize("email,url,expected", [
    ("careers@acme.com", None, "email"),
    ("careers@acme.com", "https://acme.com/jobs/123", "email"),  # email wins over url
    (None, "https://boards.greenhouse.io/acme/jobs/123", "form"),
    (None, "https://jobs.lever.co/acme/123", "form"),
    (None, "https://acme.myworkdayjobs.com/Careers/job/123", "form"),
    (None, "https://jobs.smartrecruiters.com/acme/123", "form"),
    (None, "https://acme.personio.de/job/123", "form"),
    (None, "https://acme.com/careers/pm-role", "external"),
    (None, "https://random-ats.io/jobs/123", "external"),
    (None, None, "manual"),
    ("", "", "manual"),
    ("  ", None, "manual"),  # whitespace-only treated as absent
])
def test_apply_channel_kwargs(email, url, expected) -> None:
    assert apply_channel(apply_email=email, apply_url=url) == expected


def test_apply_channel_case_insensitive_ats_match() -> None:
    assert apply_channel(apply_url="https://BOARDS.GREENHOUSE.IO/acme/123") == "form"
    assert apply_channel(apply_url="https://JOBS.LEVER.CO/acme/123") == "form"


def test_apply_channel_accepts_sqlite_row() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (apply_email TEXT, apply_url TEXT)")
    conn.execute("INSERT INTO t VALUES (?, ?)", ("careers@acme.com", None))
    conn.execute("INSERT INTO t VALUES (?, ?)", (None, "https://boards.greenhouse.io/x/123"))
    conn.execute("INSERT INTO t VALUES (?, ?)", (None, "https://acme.com/careers"))
    conn.execute("INSERT INTO t VALUES (?, ?)", (None, None))

    rows = list(conn.execute("SELECT apply_email, apply_url FROM t"))
    assert [apply_channel(r) for r in rows] == ["email", "form", "external", "manual"]


# --------------------------- ATS name lookup ------------------------------


@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/acme/123", "Greenhouse"),
    ("https://jobs.lever.co/acme/123", "Lever"),
    ("https://acme.myworkdayjobs.com/job/123", "Workday"),
    ("https://jobs.smartrecruiters.com/acme/123", "SmartRecruiters"),
    ("https://acme.personio.de/job/123", "Personio"),
    ("https://acme.com/careers", None),
    (None, None),
    ("", None),
])
def test_apply_channel_ats_name(url, expected) -> None:
    assert apply_channel_ats_name(url) == expected
