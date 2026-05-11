"""Minimal smoke tests — verify imports, scoring heuristic, state schema work without network."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def test_imports():
    """All top-level modules import cleanly."""
    import jobbot
    import jobbot.cli
    import jobbot.config
    import jobbot.models
    import jobbot.pipeline
    import jobbot.profile
    import jobbot.scoring
    import jobbot.state
    from jobbot.scrapers import REGISTRY
    from jobbot.applier import apply_to_job  # noqa: F401
    from jobbot.captcha import get_captcha_solver  # noqa: F401
    from jobbot.otp.imap import OtpFetcher  # noqa: F401

    assert jobbot.__version__
    assert set(REGISTRY) == {
        "weworkremotely", "working_nomads", "nodesk", "dailyremote",
        "freelancermap", "freelance_de",
        "indeed", "stepstone", "xing", "linkedin",
    }


def test_heuristic_filter():
    from jobbot.models import JobPosting
    from jobbot.profile import Profile
    from jobbot.scoring import passes_heuristic

    profile = Profile(
        personal={"full_name": "x", "email": "x@x"},
        preferences={"remote": True},
        deal_breakers={"keywords": ["unpaid"], "industries": [], "on_site_only": True},
        must_have_skills=["python"],
    )
    job_ok = JobPosting(id="1", source="x", title="Senior Python Dev", company="A",
                        url="https://example.com/1", description="Python, AWS, remote ok")
    job_bad_kw = JobPosting(id="2", source="x", title="Python Intern", company="A",
                            url="https://example.com/2", description="unpaid internship")
    job_no_skill = JobPosting(id="3", source="x", title="Java Dev", company="A",
                              url="https://example.com/3", description="Java spring")

    assert passes_heuristic(job_ok, profile)[0] is True
    assert passes_heuristic(job_bad_kw, profile)[0] is False
    assert passes_heuristic(job_no_skill, profile)[0] is False


def test_state_schema(tmp_path: Path, monkeypatch):
    """SQLite schema applies cleanly and dedup works."""
    db = tmp_path / "test.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    from jobbot.models import JobPosting
    from jobbot.state import connect, upsert_new

    j = JobPosting(id="abc", source="weworkremotely", title="x", company="y",
                   url="https://example.com/abc")
    with connect(db) as conn:
        new1 = upsert_new(conn, [j])
        new2 = upsert_new(conn, [j])
    assert len(new1) == 1
    assert len(new2) == 0
