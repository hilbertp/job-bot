"""Backfill candidate selector for the tailored-CV rescore.

The CLI command (`jobbot rescore --backfill`) is exercised manually with a
real Anthropic call; these tests pin the SELECT that gates which rows are
eligible — generated jobs that already have docs on disk but no
score_tailored row yet.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.models import JobPosting, JobStatus
from jobbot.state import (
    connect,
    jobs_needing_tailored_rescore,
    update_enrichment,
    update_score_tailored,
    update_status,
    upsert_new,
)


def _seed_generated_job(
    db: Path, *, job_id: str, output_dir: str | None = "/tmp/job_x",
    full_body_words: int = 250,
) -> None:
    job = JobPosting(
        id=job_id,
        source="working_nomads",
        title="Senior PM",
        company="Acme",
        url=f"https://example.com/jobs/{job_id}",  # type: ignore
        apply_url=f"https://example.com/jobs/{job_id}",  # type: ignore
        description="short snippet",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        update_enrichment(
            conn, job_id,
            description_full=" ".join(["responsibility"] * full_body_words),
            description_scraped=True,
            description_word_count=full_body_words,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_status(conn, job_id, JobStatus.SCORED, score=75, reason="good fit")
        update_status(conn, job_id, JobStatus.GENERATED, output_dir=output_dir)


def test_jobs_needing_tailored_rescore_picks_generated_without_tailored(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_generated_job(db, job_id="want", output_dir=str(tmp_path / "want"))
    _seed_generated_job(db, job_id="already", output_dir=str(tmp_path / "already"))
    with connect(db) as conn:
        update_score_tailored(conn, "already", 80, "tailored lifted it")
        candidates = jobs_needing_tailored_rescore(conn, limit=10)

    ids = [job.id for job, _ in candidates]
    assert ids == ["want"]


def test_jobs_needing_tailored_rescore_skips_rows_without_output_dir(
    tmp_path: Path, monkeypatch,
) -> None:
    """Rows with no output_dir can't be rescored — there's nowhere on disk
    to read cv.md / cover_letter.md from. Skip them so the CLI doesn't try."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_generated_job(db, job_id="orphan", output_dir=None)
    with connect(db) as conn:
        assert jobs_needing_tailored_rescore(conn, limit=10) == []


def test_jobs_needing_tailored_rescore_uses_description_full_not_snippet(
    tmp_path: Path, monkeypatch,
) -> None:
    """Rescore prompt needs the full enriched body, not the original scrape
    snippet. The state helper merges description_full into the JobPosting it
    re-hydrates from raw_json."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_generated_job(db, job_id="full_body", output_dir=str(tmp_path / "x"))

    with connect(db) as conn:
        candidates = jobs_needing_tailored_rescore(conn, limit=10)

    assert len(candidates) == 1
    job, _ = candidates[0]
    assert len(job.description.split()) == 250  # NOT the 2-word "short snippet"
