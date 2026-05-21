"""Pipeline integration: a posting whose stated salary tops out below the
configured floor is filtered BEFORE llm_score runs (saving the LLM call),
and a posting above floor still gets scored normally.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from jobbot.config import (
    Config, DigestConfig, EnrichmentConfig, Secrets, SourceConfig,
)
from jobbot.models import JobPosting, JobStatus, ScoreResult


class _Scraper:
    source = "fake"

    def __init__(self, jobs):
        self._jobs = jobs

    def fetch(self, _query):
        return self._jobs


def _job(job_id: str, body: str) -> JobPosting:
    return JobPosting(
        id=job_id, source="fake",
        title="Product Manager", company=f"Co {job_id}",
        url=f"https://example.com/jobs/{job_id}",
        apply_url=f"https://example.com/jobs/{job_id}",
        posted_at=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=1),
        description=body,
    )


def _config():
    return Config(
        sources={"fake": SourceConfig(enabled=True, queries=[{"q": "pm"}])},
        enrichment=EnrichmentConfig(),
        digest=DigestConfig(),
        score_threshold=70,
        salary_floor_eur_year=90_000,
    )


def _secrets():
    return Secrets(anthropic_api_key="x", gmail_address="a@b.com",
                   gmail_app_password="x", notify_to="a@b.com")


def _profile():
    from jobbot.profile import Profile
    return Profile(personal={"full_name": "T", "email": "t@example.com"},
                   preferences={})


def test_below_floor_posting_is_filtered_without_llm_call(tmp_path, monkeypatch):
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    body_low = ("We are hiring a Product Manager. " * 20) + \
        " Compensation: EUR 65,000 - 75,000 per year."
    body_ok = ("We are hiring a Product Manager. " * 20) + \
        " Compensation: EUR 100,000 - 120,000 per year."

    scraper = _Scraper([_job("low_pay", body_low), _job("ok_pay", body_ok)])
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": scraper})
    monkeypatch.setattr(pipeline, "load_profile", _profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(pipeline, "housekeep_shortlist",
                        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []))

    scored_ids = []

    def _fake_score(job, *_a, **_kw):
        scored_ids.append(job.id)
        return ScoreResult(score=85, reason="ok")
    monkeypatch.setattr(pipeline, "llm_score", _fake_score)
    # Avoid real generation for the above-floor row.
    monkeypatch.setattr(pipeline, "generate_documents", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "generate_application_package", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "llm_score_tailored",
                        lambda *a, **k: ScoreResult(score=90, reason="t"))

    pipeline.run_once(_config(), _secrets())

    # The below-floor row must NOT have been scored.
    assert "low_pay" not in scored_ids, (
        "below-floor posting reached llm_score; it should have been filtered first"
    )
    assert "ok_pay" in scored_ids, "above-floor posting should have been scored"

    with connect(db) as conn:
        low = conn.execute(
            "SELECT status, score, discard_reason FROM seen_jobs WHERE id='low_pay'"
        ).fetchone()
        ok = conn.execute(
            "SELECT status, score FROM seen_jobs WHERE id='ok_pay'"
        ).fetchone()
    assert low["status"] == JobStatus.FILTERED.value
    assert low["score"] is None
    assert "salary_below_floor" in (low["discard_reason"] or "")
    assert ok["status"] in (JobStatus.SCORED.value, JobStatus.GENERATED.value)


def test_floor_disabled_lets_low_pay_through(tmp_path, monkeypatch):
    """With salary_floor_eur_year=0 the low-pay row is scored normally."""
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    body_low = ("Product Manager role. " * 20) + " Salary: EUR 65,000 - 75,000 per year."
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": _Scraper([_job("low_pay", body_low)])})
    monkeypatch.setattr(pipeline, "load_profile", _profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(pipeline, "housekeep_shortlist",
                        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []))
    monkeypatch.setattr(pipeline, "llm_score", lambda *a, **k: ScoreResult(score=85, reason="ok"))
    monkeypatch.setattr(pipeline, "generate_documents", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "generate_application_package", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "llm_score_tailored", lambda *a, **k: ScoreResult(score=90, reason="t"))

    cfg = _config()
    cfg.salary_floor_eur_year = 0  # disabled
    pipeline.run_once(cfg, _secrets())

    with connect(db) as conn:
        low = conn.execute("SELECT status, score FROM seen_jobs WHERE id='low_pay'").fetchone()
    assert low["score"] == 85, "with floor disabled, low-pay row should be scored"
