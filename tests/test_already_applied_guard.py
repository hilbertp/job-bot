"""The "already applied" foot-gun guard.

Two contracts MUST hold or the pipeline will re-send applications to the
same employer on every cron tick:

1. After `record_application` runs with a submitted result, the same
   job_id appears in `jobs_with_submitted_application(conn)`. The flag
   must be reliable — if writing the row silently dropped the
   `submitted = 1` bit, the guard would let a duplicate through.
2. The pipeline's apply step skips any job already in
   `jobs_with_submitted_application` — manual mark OR prior bot send.

Plus: the `jobbot mark-applied` CLI must record a manual application
that the guard then honours.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from jobbot.config import (
    Config, DigestConfig, EnrichmentConfig, Secrets, SourceConfig,
)
from jobbot.models import (
    ApplyResult, GeneratedDocs, JobPosting, JobStatus, ScoreResult,
)
from jobbot.profile import Profile
from jobbot.state import (
    connect,
    jobs_with_submitted_application,
    mark_application_manually,
    record_application,
)


def _make_job(job_id: str = "guard_1") -> JobPosting:
    return JobPosting(
        id=job_id, source="fake", title="Senior PM", company="ACME",
        url=f"https://example.com/jobs/{job_id}",
        apply_url=f"https://example.com/jobs/{job_id}",
        description=" ".join(["responsibility"] * 240),
    )


def _seed_job(db: Path, job: JobPosting) -> None:
    from jobbot.state import upsert_new
    with connect(db) as conn:
        upsert_new(conn, [job])


# ---------------------------------------------------------------------------
# Contract 1 — record_application reliably flips the submitted bit
# ---------------------------------------------------------------------------

def test_record_application_with_submitted_result_lands_in_guard_set(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("rec_1")
    _seed_job(db, job)

    result = ApplyResult(
        status=JobStatus.APPLY_SUBMITTED, submitted=True, dry_run=False,
        confirmation_url="mailto:careers@example.com",
    )
    with connect(db) as conn:
        record_application(conn, job.id, result)
        applied = jobs_with_submitted_application(conn)

    assert job.id in applied, (
        "submitted=True must land in jobs_with_submitted_application; "
        "the guard depends on this"
    )


def test_dry_run_application_does_NOT_count_as_submitted(
    tmp_path: Path, monkeypatch,
) -> None:
    """A dry-run preview (.eml on disk, no SMTP) is a queued draft, not a
    confirmed send. It must NOT trip the guard — otherwise reviewing a
    dry-run permanently locks the job out of real sending."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("rec_dry")
    _seed_job(db, job)

    result = ApplyResult(
        status=JobStatus.APPLY_NEEDS_REVIEW, submitted=False, dry_run=True,
        needs_review_reason="email_channel: dry_run",
    )
    with connect(db) as conn:
        record_application(conn, job.id, result)
        applied = jobs_with_submitted_application(conn)

    assert job.id not in applied


def test_record_application_failure_does_NOT_count_as_submitted(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("rec_fail")
    _seed_job(db, job)

    result = ApplyResult(
        status=JobStatus.APPLY_FAILED, submitted=False, error="smtp timeout",
    )
    with connect(db) as conn:
        record_application(conn, job.id, result)
        applied = jobs_with_submitted_application(conn)

    assert job.id not in applied


# ---------------------------------------------------------------------------
# Contract 2 — manual mark via state helper lands in the guard set
# ---------------------------------------------------------------------------

def test_mark_application_manually_lands_in_guard_set(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("manual_1")
    _seed_job(db, job)

    with connect(db) as conn:
        mark_application_manually(conn, job.id, note="Applied via LinkedIn UI")
        applied = jobs_with_submitted_application(conn)
        status = conn.execute(
            "SELECT status FROM seen_jobs WHERE id = ?", (job.id,),
        ).fetchone()["status"]

    assert job.id in applied
    assert status == JobStatus.APPLY_SUBMITTED.value, (
        "manual mark must also flip seen_jobs.status so the dashboard "
        "shows the job as applied, not still on the shortlist"
    )


def test_mark_application_manually_preserves_note_in_proof_evidence(
    tmp_path: Path, monkeypatch,
) -> None:
    import json
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("manual_2")
    _seed_job(db, job)

    with connect(db) as conn:
        mark_application_manually(conn, job.id, note="applied via referral")
        row = conn.execute(
            "SELECT proof_evidence FROM applications WHERE job_id = ?",
            (job.id,),
        ).fetchone()

    evidence = json.loads(row["proof_evidence"])
    assert evidence[0]["source"] == "manual"
    assert evidence[0]["note"] == "applied via referral"
    assert evidence[0]["submitted"] is True


def test_mark_application_manually_is_idempotent(
    tmp_path: Path, monkeypatch,
) -> None:
    """Running the CLI twice on the same job must not pile up duplicate
    application rows; INSERT OR REPLACE handles this."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _make_job("manual_idem")
    _seed_job(db, job)

    with connect(db) as conn:
        mark_application_manually(conn, job.id, note="first")
        mark_application_manually(conn, job.id, note="second")
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM applications WHERE job_id = ?",
            (job.id,),
        ).fetchone()

    assert rows["n"] == 1, "duplicate mark must not create a second row"


# ---------------------------------------------------------------------------
# Contract 3 — pipeline skips jobs already in the guard set
# ---------------------------------------------------------------------------

class _SingleJobScraper:
    """One-shot fake scraper returning a job already marked as applied."""
    source = "fake"

    def __init__(self, job_id: str):
        self._job_id = job_id

    def fetch(self, _query):
        return [_make_job(self._job_id)]

    def fetch_detail(self, job):
        long_body = " ".join(["responsibility"] * 240)
        return job.model_copy(update={"description": long_body})


def _make_profile() -> Profile:
    return Profile(
        personal={"full_name": "Test"},
        preferences={"remote": True},
        deal_breakers={"keywords": [], "industries": [], "on_site_only": False},
    )


def _make_secrets() -> Secrets:
    return Secrets(
        anthropic_api_key="dummy", gmail_address="x@example.com",
        gmail_app_password="x", notify_to="x@example.com",
    )


def _make_config() -> Config:
    return Config(
        score_threshold=70, max_jobs_per_run=10,
        digest=DigestConfig(generate_docs_above_score=70, max_per_email=10),
        enrichment=EnrichmentConfig(per_run_cap=10),
        sources={"fake": SourceConfig(
            enabled=True, auto_submit=True,
            queries=[{"q": "pm"}],
        )},
    )


def _fake_generate_application_package(job, profile, base_cv, secrets, config, **_kw):
    """Mirror of the test_e2e_user_journeys fake — writes minimal artifacts."""
    out = Path(config.output_dir).resolve() / "guard-run" / job.id
    out.mkdir(parents=True, exist_ok=True)
    (out / "cv.md").write_text("# CV\n")
    (out / "cover_letter.md").write_text("Dear team")
    return GeneratedDocs(
        cv_md="# CV", cv_html="<h1>CV</h1>",
        cover_letter_md="Dear team", cover_letter_html="<p>Dear team</p>",
        output_dir=str(out),
    )


def test_pipeline_skips_jobs_already_marked_applied(
    tmp_path: Path, monkeypatch,
) -> None:
    """Full end-to-end: mark a job, then run the pipeline. The applier
    must NOT be invoked. apply_status on the digest entry == 'skipped_already_applied'."""
    import jobbot.pipeline as pipeline

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    job_id = "skip_me"

    # Pre-seed: job exists and is already marked as applied (manual or bot).
    job = _make_job(job_id)
    _seed_job(db, job)
    with connect(db) as conn:
        mark_application_manually(conn, job_id, note="already done")

    # Stub the pipeline so it actually reaches the apply step.
    monkeypatch.setattr(pipeline, "REGISTRY",
                        {"fake": _SingleJobScraper(job_id)})
    monkeypatch.setattr(pipeline, "load_profile", _make_profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic",
                        lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest",
                        lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline, "llm_score",
                        lambda *_a, **_kw: ScoreResult(score=80, reason="match"))
    monkeypatch.setattr(pipeline, "generate_documents",
                        _fake_generate_application_package)
    monkeypatch.setattr(pipeline, "generate_application_package",
                        _fake_generate_application_package)

    apply_calls: list[str] = []

    def _spy_apply(job, *_args, **_kw):
        apply_calls.append(job.id)
        return ApplyResult(status=JobStatus.APPLY_SUBMITTED, submitted=True)

    monkeypatch.setattr(pipeline, "apply_to_job", _spy_apply)

    pipeline.run_once(_make_config(), _make_secrets())

    assert apply_calls == [], (
        f"pipeline must not call apply_to_job for already-applied jobs; "
        f"saw calls for {apply_calls}"
    )
