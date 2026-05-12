"""Dashboard feedback-rescore endpoint: POST /api/jobs/<id>/feedback-rescore.

Verifies the wiring end-to-end with the LLM call monkeypatched:
  - comment is persisted to seen_jobs.user_comment + user_comment_at
  - llm_score is invoked with user_feedback=<comment>
  - the returned score replaces the row's score + score_reason + scored_at
  - validation errors and not-found errors return the documented codes
"""
from __future__ import annotations

from pathlib import Path

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting, JobStatus, ScoreResult
from jobbot.state import (
    connect,
    finish_run,
    start_run,
    update_enrichment,
    update_status,
    upsert_new,
)


def _seed_scored_job(db: Path, job_id: str = "feedback_target") -> None:
    """Seed a single SCORED row with a real >200-word body so the scorer
    preconditions would pass if the real llm_score were called."""
    body = " ".join(["responsibility"] * 240)
    with connect(db) as conn:
        run_id = start_run(conn)
        upsert_new(conn, [JobPosting(
            id=job_id, source="linkedin", title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/feedback-target",  # type: ignore
            description=body,
        )])
        update_enrichment(
            conn, job_id,
            description_full=body,
            description_scraped=True,
            description_word_count=240,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_status(conn, job_id, JobStatus.SCORED,
                      score=42, reason="initial low score")
        finish_run(conn, run_id, n_fetched=1, n_new=1)


def _capture_user_feedback(monkeypatch, score: int = 71, reason: str = "rescored"):
    """Monkeypatch llm_score to capture the user_feedback kwarg and return a
    deterministic ScoreResult. Returns the dict that gets populated on call."""
    captured: dict[str, object] = {}

    def fake_llm_score(job, profile, secrets, *, description_scraped, user_feedback=None):
        captured["job_id"] = job.id
        captured["description_scraped"] = description_scraped
        captured["user_feedback"] = user_feedback
        return ScoreResult(score=score, reason=reason)

    # The endpoint does `from .scoring import llm_score` *inside* the
    # route, so the import resolves to whatever jobbot.scoring.llm_score
    # is at request time. Patching the source module is therefore enough.
    monkeypatch.setattr("jobbot.scoring.llm_score", fake_llm_score)
    # Profile + secrets loaders also imported locally inside the route;
    # the real ones would fail without ANTHROPIC_API_KEY / a PRIMARY_ CV.
    monkeypatch.setattr("jobbot.config.load_secrets", lambda: object())
    monkeypatch.setattr("jobbot.profile.load_profile", lambda: object())
    return captured


def test_feedback_rescore_persists_comment_and_updates_score(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_scored_job(db)
    captured = _capture_user_feedback(monkeypatch, score=71, reason="reconsidered")

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.post(
        "/api/jobs/feedback_target/feedback-rescore",
        json={"comment": "I am willing to relocate to Freiburg."},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["ok"] is True
    assert data["old_score"] == 42
    assert data["new_score"] == 71
    assert data["reason"] == "reconsidered"
    assert data["user_comment_at"] is not None
    assert data["scored_at"] is not None

    # The scorer was actually invoked with the user's prose.
    assert captured["job_id"] == "feedback_target"
    assert captured["description_scraped"] is True
    assert captured["user_feedback"] == "I am willing to relocate to Freiburg."

    # DB state matches the response.
    with connect(db) as conn:
        row = conn.execute(
            "SELECT score, score_reason, user_comment, user_comment_at "
            "FROM seen_jobs WHERE id = 'feedback_target'"
        ).fetchone()
    assert row["score"] == 71
    assert row["score_reason"] == "reconsidered"
    assert row["user_comment"] == "I am willing to relocate to Freiburg."
    assert row["user_comment_at"] is not None


def test_feedback_rescore_strips_whitespace_then_rejects_empty(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_scored_job(db)
    _capture_user_feedback(monkeypatch)

    client = _load_legacy_dashboard_module().app.test_client()
    for comment in (None, "", "   \n\t  "):
        resp = client.post(
            "/api/jobs/feedback_target/feedback-rescore",
            json={"comment": comment},
        )
        assert resp.status_code == 400, f"expected 400 for {comment!r}"
        assert resp.get_json()["ok"] is False

    # Original score should be untouched after the rejected calls.
    with connect(db) as conn:
        row = conn.execute(
            "SELECT score, user_comment FROM seen_jobs WHERE id = 'feedback_target'"
        ).fetchone()
    assert row["score"] == 42
    assert row["user_comment"] is None


def test_feedback_rescore_404_for_missing_job(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    # Seed an unrelated row so the DB exists and has the schema migrated.
    _seed_scored_job(db, job_id="other_job")
    _capture_user_feedback(monkeypatch)

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.post(
        "/api/jobs/does_not_exist/feedback-rescore",
        json={"comment": "anything"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["ok"] is False


def test_shortlist_api_exposes_user_comment_fields(
    tmp_path: Path, monkeypatch,
) -> None:
    """/api/shortlist must include user_comment + user_comment_at so the
    frontend can preload the textarea and the 'last saved' indicator."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_scored_job(db)
    # Pre-populate the comment column so we know the API exposes it.
    with connect(db) as conn:
        conn.execute(
            "UPDATE seen_jobs SET user_comment = ?, user_comment_at = ? WHERE id = ?",
            ("note from earlier", "2026-05-12T10:00:00+00:00", "feedback_target"),
        )

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/shortlist?min_score=0").get_json()
    target = next((j for j in payload["jobs"] if j["id"] == "feedback_target"), None)
    assert target is not None
    assert target["user_comment"] == "note from earlier"
    assert target["user_comment_at"] == "2026-05-12T10:00:00+00:00"
