"""Permanent vs transient fetch failures.

The retry queue exists for transients (429s, timeouts). Three kinds of
failure can never succeed and must leave the queue for good instead:
a board that walls its detail pages (Brainville: 0 successes in 96
attempts), a source disabled in config (freelance.de robots.txt), and a
dead page that keeps failing on an otherwise healthy board.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jobbot.enrichment.runner import _MAX_FETCH_ATTEMPTS, enrich_new_postings
from jobbot.models import JobPosting, JobStatus, TERMINAL_STATUSES
from jobbot.state import (
    connect, jobs_needing_enrichment, run_stage_progress, start_run, upsert_new,
)


def _job(job_id: str, source: str) -> JobPosting:
    return JobPosting(
        id=job_id, source=source, title="Product Owner", company="Acme",
        location="Remote", url=f"https://example.com/{job_id}",
        apply_url=f"https://example.com/{job_id}/apply", description="teaser",
    )


def _status(db, job_id: str) -> str:
    with connect(db) as conn:
        return conn.execute(
            "SELECT status FROM seen_jobs WHERE id = ?", (job_id,)
        ).fetchone()["status"]


class _MustNotFetch:
    """fetch_detail that fails the test if anyone calls it."""

    detail_walled = "full text requires an account"

    def fetch_detail(self, job):
        raise AssertionError("walled source must not be fetched")


class _AlwaysNone:
    def fetch_detail(self, job):
        return None


def test_unfetchable_is_terminal():
    assert JobStatus.UNFETCHABLE.value in TERMINAL_STATUSES


def test_walled_source_resolved_without_fetch(tmp_path: Path):
    db = tmp_path / "jobbot.db"
    job = _job("brainville_1", "brainville")
    with connect(db) as conn:
        upsert_new(conn, [job])
        run_id = start_run(conn)
        report = enrich_new_postings(
            [job], conn, registry={"brainville": _MustNotFetch()}, run_id=run_id,
        )
        stage = next(s for s in run_stage_progress(conn, run_id)
                     if s["stage"] == "enrichment")
        queue = jobs_needing_enrichment(conn)

    assert report.n_walled == 1
    assert report.n_failed == 0  # not a failure: nothing will be retried
    assert _status(db, job.id) == JobStatus.UNFETCHABLE.value
    assert queue == []
    assert stage["skipped"] == 1
    assert stage["metadata"]["walled_by_source"] == {"brainville": 1}
    assert "account" in stage["metadata"]["walled_reasons"]["brainville"]


def test_disabled_source_is_never_crawled(tmp_path: Path):
    """robots.txt compliance: a source disabled in config must not get
    detail-page requests for its leftover rows either."""
    db = tmp_path / "jobbot.db"
    job = _job("freelance_de_1", "freelance_de")

    class _Fetcher:
        def fetch_detail(self, j):
            raise AssertionError("disabled source must not be crawled")

    config = SimpleNamespace(
        sources={"freelance_de": SimpleNamespace(enabled=False)},
        apply_research_enabled=False,
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        report = enrich_new_postings(
            [job], conn, registry={"freelance_de": _Fetcher()}, config=config,
        )
    assert report.n_walled == 1
    assert _status(db, job.id) == JobStatus.UNFETCHABLE.value


def test_transient_failures_give_up_at_cap(tmp_path: Path):
    db = tmp_path / "jobbot.db"
    job = _job("stepstone_dead", "stepstone")
    registry = {"stepstone": _AlwaysNone()}
    with connect(db) as conn:
        upsert_new(conn, [job])
        for attempt in range(1, _MAX_FETCH_ATTEMPTS + 1):
            run_id = start_run(conn)
            report = enrich_new_postings(
                [job], conn, registry=registry, run_id=run_id,
            )
            if attempt < _MAX_FETCH_ATTEMPTS:
                assert _status(db, job.id) != JobStatus.UNFETCHABLE.value
                assert [j.id for j, _ in jobs_needing_enrichment(conn)] == [job.id]
            # simulate the next run picking the row up again
        stage = next(s for s in run_stage_progress(conn, run_id)
                     if s["stage"] == "enrichment")

    assert report.n_gave_up == 1
    assert _status(db, job.id) == JobStatus.UNFETCHABLE.value
    assert stage["metadata"]["gave_up"] == 1
    with connect(db) as conn:
        assert jobs_needing_enrichment(conn) == []


def test_source_without_fetcher_stays_scorable_but_caps(tmp_path: Path):
    """No fetch_detail is NOT a wall: the card body is persisted so scoring
    can work from it. But the attempt cap still retires the row if it never
    leaves the queue (pipeline_salary_floor tests guard the scoring half)."""
    db = tmp_path / "jobbot.db"
    job = _job("manual_1", "manual")
    with connect(db) as conn:
        upsert_new(conn, [job])
        for _ in range(_MAX_FETCH_ATTEMPTS):
            report = enrich_new_postings([job], conn, registry={})
        row = conn.execute(
            "SELECT description_full, status FROM seen_jobs WHERE id = ?",
            (job.id,),
        ).fetchone()
        queue = jobs_needing_enrichment(conn)
    assert report.n_walled == 0
    assert report.n_failed == 1
    assert row["description_full"] == "teaser"  # card body kept for scoring
    assert row["status"] == JobStatus.UNFETCHABLE.value  # capped after 3 runs
    assert queue == []
