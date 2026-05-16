"""Regression: rows in a terminal status must not be re-scored.

Real-world driver, 2026-05-16:
  - Rush Street Interactive's WWR posting was marked LISTING_EXPIRED on
    2026-05-15 (canonical Greenhouse board didn't carry it, WWR's apply
    button was paywalled).
  - The WWR scraper still found the listing the next day. Even though
    `INSERT OR IGNORE` left the seen_jobs row alone, the JobPosting
    object still flowed through enrichment → to_score → the
    unconditional `update_status(JobStatus.SCORED, ...)` at the end of
    the scoring loop. Status got reverted to 'scored'.

This test pins the fix: the scoring loop must skip rows whose current
DB status is in TERMINAL_STATUSES.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from jobbot.config import (
    ApplyConfig, Config, DigestConfig, EnrichmentConfig,
    Secrets, SourceConfig,
)
from jobbot.models import JobPosting, JobStatus, ScoreResult


class FakeScraper:
    source = "fake"

    def __init__(self, job_id: str = "existing_expired"):
        self.job_id = job_id

    def fetch(self, _query: str) -> list[JobPosting]:
        return [JobPosting(
            id=self.job_id, source="fake",
            title="Senior PM",
            company="ExpiredCo",
            url=f"https://example.com/jobs/{self.job_id}",
            apply_url=f"https://example.com/jobs/{self.job_id}",
            posted_at=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=1),
            description="body" * 50,
        )]


def _make_config():
    return Config(
        sources={"fake": SourceConfig(enabled=True, queries=[{"q": "pm"}])},
        enrichment=EnrichmentConfig(),
        digest=DigestConfig(),
        apply=ApplyConfig(),
        score_threshold=70,
    )


def _make_secrets():
    return Secrets(
        anthropic_api_key="x", gmail_address="a@b.com",
        gmail_app_password="x", notify_to="a@b.com",
    )


def _make_profile():
    from jobbot.profile import Profile
    return Profile(
        personal={"full_name": "Test", "email": "t@example.com"},
        preferences={},
    )


def test_listing_expired_row_is_not_rescored_when_scraper_finds_it_again(
    tmp_path: Path, monkeypatch,
) -> None:
    """Pre-existing seen_jobs row with status=listing_expired must remain
    listing_expired after a pipeline pass that re-scrapes the same listing."""
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    # Seed a row that is already in a terminal state.
    from jobbot.state import upsert_new  # forces schema init
    with connect(db) as conn:
        upsert_new(conn, [JobPosting(
            id="existing_expired", source="fake",
            title="Senior PM", company="ExpiredCo",
            url="https://example.com/jobs/existing_expired",
            apply_url="https://example.com/jobs/existing_expired",
            description="body" * 50,
        )])
        conn.execute(
            "UPDATE seen_jobs SET status = ?, score = ?, "
            "description_scraped = 1, description_word_count = 200, "
            "description_full = ? WHERE id = ?",
            (
                JobStatus.LISTING_EXPIRED.value, 72,
                "body" * 100, "existing_expired",
            ),
        )

    monkeypatch.setattr(
        pipeline, "REGISTRY", {"fake": FakeScraper("existing_expired")},
    )
    monkeypatch.setattr(pipeline, "load_profile", _make_profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)

    # If guard works, llm_score must NOT be called for this row.
    def _fail_if_called(*_a, **_kw):
        pytest.fail(
            "llm_score should not run for a row already in TERMINAL_STATUSES"
        )

    monkeypatch.setattr(pipeline, "llm_score", _fail_if_called)
    # Disable in-pipeline housekeep (separate concern).
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(
        pipeline, "housekeep_shortlist",
        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []),
    )

    pipeline.run_once(_make_config(), _make_secrets())

    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score FROM seen_jobs WHERE id = 'existing_expired'"
        ).fetchone()
    assert row["status"] == JobStatus.LISTING_EXPIRED.value, (
        f"row's terminal status got clobbered; new status={row['status']}"
    )
    assert row["score"] == 72, "score should not have been touched"
