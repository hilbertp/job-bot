"""Fetch-stage telemetry: funnel counts ride in, failures grouped by board.

Run 305 spent 84 of 85 fetches on bot-walled boards and the panel could only
say "84 failed" — no who, no why. These tests pin the two halves of the fix:
the caller's funnel numbers (dedup / age gate / retries) reach the stage's
metadata, and per-source failure counts appear live under `fail_by_source`.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.enrichment.runner import enrich_new_postings
from jobbot.models import JobPosting
from jobbot.state import (
    connect, jobs_needing_enrichment, run_stage_progress, start_run, upsert_new,
)


def _job(job_id: str, source: str = "brainville") -> JobPosting:
    return JobPosting(
        id=job_id,
        source=source,
        title="Product Owner",
        company="Acme",
        location="Remote",
        url=f"https://example.com/{job_id}",
        apply_url=f"https://example.com/{job_id}/apply",
        description="teaser",
    )


class _WalledScraper:
    """Detail pages behind a login/bot wall: fetch_detail yields nothing."""

    def fetch_detail(self, job: JobPosting):
        return None


def test_stage_metadata_merges_and_failures_group_by_source(tmp_path: Path):
    db = tmp_path / "jobbot.db"
    jobs = [_job("brainville_1"), _job("brainville_2"),
            _job("xing_1", source="xing")]
    funnel = {"found": 300, "already_seen": 290, "too_old": 7,
              "new": 1, "retries": 2, "deferred_over_cap": 0}
    with connect(db) as conn:
        upsert_new(conn, jobs)
        run_id = start_run(conn)
        enrich_new_postings(
            jobs, conn,
            registry={"brainville": _WalledScraper(), "xing": _WalledScraper()},
            run_id=run_id, stage_metadata=funnel,
        )
        stage = next(s for s in run_stage_progress(conn, run_id)
                     if s["stage"] == "enrichment")

    meta = stage["metadata"]
    # The caller's funnel counts survive every later progress write.
    for key, value in funnel.items():
        assert meta[key] == value, key
    assert meta["stage_started_at"]
    # Failures are grouped by board so the panel can name the culprit.
    assert meta["fail_by_source"] == {"brainville": 2, "xing": 1}
    assert stage["failed"] == 3


def test_dateless_retry_rows_age_out_via_first_seen_fallback(tmp_path: Path):
    """The zombie-queue regression: a bot-walled row with no posted_at must
    age out of the retry queue on first_seen_at, not live forever (Xing rows
    from May were still re-failing their fetch in August)."""
    from jobbot.scoring import too_old_for_market

    db = tmp_path / "jobbot.db"
    job = _job("xing_zombie", source="xing")  # no posted_at on purpose
    with connect(db) as conn:
        upsert_new(conn, [job])
        run_id = start_run(conn)
        enrich_new_postings(
            [job], conn, registry={"xing": _WalledScraper()}, run_id=run_id,
        )
        conn.execute(
            "UPDATE seen_jobs SET first_seen_at = '2026-05-12T00:00:00+00:00' "
            "WHERE id = ?", (job.id,),
        )
        pairs = jobs_needing_enrichment(conn)

    assert [j.id for j, _ in pairs] == [job.id]
    _, first_seen = pairs[0]
    is_stale, reason = too_old_for_market(job, 7, first_seen_at=first_seen)
    assert is_stale, "date-less retry rows must age out via first_seen_at"
    assert "too old" in reason
