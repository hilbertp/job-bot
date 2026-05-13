"""Stage-2 disagree-and-rescore: the user clicks "comment" on a low-scored
row, writes context the bot missed, and the row rescores with that context
in the prompt. The feedback is ALSO persisted as a durable fact in the
candidate's profile so every future scoring run picks it up.

This file pins the four contracts that matter end-to-end:

1. state.update_user_feedback_rescore writes to seen_jobs without
   touching the original `score` column (so the dashboard can render
   a true before/after).
2. profile.append_user_fact writes the feedback into profile.yaml's
   user_facts list and is idempotent on duplicates.
3. POST /api/jobs/<id>/rescore-with-feedback wires those two together,
   plus a stubbed llm_score, and returns the new score + delta.
4. The Stage 2 table renders the Disagree column + ships
   score_after_feedback in the latest-run-jobs payload.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting
from jobbot.profile import append_user_fact, load_profile
from jobbot.state import (
    connect,
    finish_run,
    start_run,
    update_enrichment,
    update_status,
    update_user_feedback_rescore,
    upsert_new,
)
from jobbot.models import JobStatus


def _seed_low_scored_job(db: Path) -> int:
    job = JobPosting(
        id="job-low",
        source="stepstone",
        title="Senior Product Manager",
        company="Acme Logistics",
        url="https://example.com/jobs/low",  # type: ignore
        apply_url="https://example.com/jobs/low",  # type: ignore
        description=" ".join(["responsibility"] * 220),
    )
    with connect(db) as conn:
        run_id = start_run(conn)
        upsert_new(conn, [job])
        update_enrichment(
            conn, "job-low",
            description_full=" ".join(["responsibility"] * 220),
            description_scraped=True,
            description_word_count=220,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_status(
            conn, "job-low", JobStatus.BELOW_THRESHOLD,
            score=45, reason="role=60, skills=30, seniority=70",
        )
        finish_run(
            conn, run_id,
            n_fetched=1, n_new=1,
            summary={"per_source_fetched": {"stepstone": 1}, "fetched_ids": ["job-low"]},
        )
    return run_id


# ---------------------------------------------------------------------------
# 1. state helper
# ---------------------------------------------------------------------------

def test_update_user_feedback_rescore_keeps_original_score(
    tmp_path: Path, monkeypatch,
) -> None:
    """The original `score` column must stay frozen — the new value goes
    into score_after_feedback so the UI can show before/after."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_low_scored_job(db)

    with connect(db) as conn:
        update_user_feedback_rescore(
            conn, "job-low",
            feedback="I have 5 years of Python experience not on my CV.",
            score=72,
            reason="reweighted skills given new context",
        )
        row = conn.execute(
            "SELECT score, score_after_feedback, score_after_feedback_reason, "
            "user_feedback, feedback_at FROM seen_jobs WHERE id = ?",
            ("job-low",),
        ).fetchone()

    assert row["score"] == 45, "original score must not be overwritten"
    assert row["score_after_feedback"] == 72
    assert "reweighted" in row["score_after_feedback_reason"]
    assert row["user_feedback"].startswith("I have 5 years")
    assert row["feedback_at"], "feedback_at timestamp must be set"


# ---------------------------------------------------------------------------
# 2. profile fact persistence
# ---------------------------------------------------------------------------

def _write_minimal_profile(path: Path) -> None:
    path.write_text(yaml.safe_dump({
        "personal": {"full_name": "Jane Doe", "email": "jane@example.com"},
        "preferences": {"remote": True},
        "must_have_skills": [],
        "nice_to_have_skills": [],
        "user_facts": [],
    }))


def test_append_user_fact_writes_to_profile_yaml(tmp_path: Path) -> None:
    p = tmp_path / "profile.yaml"
    _write_minimal_profile(p)
    append_user_fact(
        "I have 5 years of Python experience not on my CV.",
        profile_path=p,
    )
    data = yaml.safe_load(p.read_text())
    assert data["user_facts"] == [
        "I have 5 years of Python experience not on my CV."
    ]


def test_append_user_fact_is_idempotent_on_duplicates(tmp_path: Path) -> None:
    """Re-submitting the same comment must not add a second copy. We
    normalize whitespace + case so trivial variations don't slip in."""
    p = tmp_path / "profile.yaml"
    _write_minimal_profile(p)
    append_user_fact("Willing to relocate to Freiburg.", profile_path=p)
    append_user_fact("willing to relocate to Freiburg.", profile_path=p)
    append_user_fact("  Willing to relocate to   Freiburg.  ", profile_path=p)

    data = yaml.safe_load(p.read_text())
    assert len(data["user_facts"]) == 1


def test_append_user_fact_refuses_empty_input(tmp_path: Path) -> None:
    p = tmp_path / "profile.yaml"
    _write_minimal_profile(p)
    try:
        append_user_fact("   ", profile_path=p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on empty fact")


def test_load_profile_picks_up_appended_facts(tmp_path: Path, monkeypatch) -> None:
    """The scoring path reads facts via load_profile(). An appended fact
    must therefore be visible to the very next scoring call."""
    p = tmp_path / "profile.yaml"
    _write_minimal_profile(p)
    monkeypatch.setattr("jobbot.profile.REPO_ROOT", tmp_path.parent)
    # Point load_profile at our temp file directly.
    profile = load_profile(p)
    assert profile.user_facts == []

    append_user_fact("Comfortable in regulated industries.", profile_path=p)
    profile2 = load_profile(p)
    assert profile2.user_facts == ["Comfortable in regulated industries."]


# ---------------------------------------------------------------------------
# 3. POST endpoint
# ---------------------------------------------------------------------------

def test_rescore_endpoint_persists_score_and_fact(
    tmp_path: Path, monkeypatch,
) -> None:
    """End-to-end with a stubbed scorer: POST a comment, expect (a) the new
    score on the row, (b) the original score untouched, (c) the comment
    appended to profile.yaml's user_facts, (d) the right JSON shape."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_low_scored_job(db)

    profile_yaml = tmp_path / "profile.yaml"
    _write_minimal_profile(profile_yaml)

    # Stub the LLM scorer so the test doesn't need API credentials.
    from jobbot import dashboard as dash_module
    from jobbot.scoring import ScoreResult

    def fake_llm_score(job, profile, secrets, **kwargs):
        # Confirm the endpoint passed our feedback through to the scorer.
        assert kwargs.get("user_feedback", "").startswith("I have 5 years")
        return ScoreResult(score=78, reason="reweighted given new Python context")

    # Point both the dashboard module's lookups and the imports inside
    # api_rescore_with_feedback at our stubs.
    monkeypatch.setattr("jobbot.scoring.llm_score", fake_llm_score)
    # The endpoint reads load_secrets() — stub it so we don't touch real env.
    class _DummySecrets:
        anthropic_api_key = "sk-test"
    monkeypatch.setattr("jobbot.config.load_secrets", lambda: _DummySecrets())
    # And load_profile must read OUR temp file, not data/profile.yaml.
    from jobbot import profile as profile_module
    monkeypatch.setattr(
        profile_module, "load_profile",
        lambda path=None: load_profile(profile_yaml),
    )
    # append_user_fact also defaults to data/profile.yaml — redirect it.
    real_append = profile_module.append_user_fact
    monkeypatch.setattr(
        profile_module, "append_user_fact",
        lambda fact, profile_path=None: real_append(fact, profile_path=profile_yaml),
    )

    # The endpoint does local imports (from .profile import ..., from
    # .scoring import ...) at call time. Those look up the names in the
    # source modules' namespaces — patching jobbot.profile.* / jobbot.scoring.*
    # / jobbot.config.* above is sufficient. No need to also patch the
    # dashboard module itself (it doesn't bind those names).
    legacy = _load_legacy_dashboard_module()
    client = legacy.app.test_client()
    res = client.post(
        "/api/jobs/job-low/rescore-with-feedback",
        json={"feedback": "I have 5 years of Python experience not on my CV."},
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert body["ok"] is True
    assert body["score_before"] == 45
    assert body["score_after"] == 78
    assert body["delta"] == 33
    assert body["fact_persisted"] is True

    # DB: original score untouched, rescored value persisted alongside.
    with connect(db) as conn:
        row = conn.execute(
            "SELECT score, score_after_feedback, user_feedback "
            "FROM seen_jobs WHERE id = 'job-low'"
        ).fetchone()
    assert row["score"] == 45
    assert row["score_after_feedback"] == 78
    assert row["user_feedback"].startswith("I have 5 years")

    # profile.yaml gained the new fact.
    data = yaml.safe_load(profile_yaml.read_text())
    assert any("Python" in f for f in data["user_facts"])


def test_rescore_endpoint_rejects_empty_feedback(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_low_scored_job(db)

    client = _load_legacy_dashboard_module().app.test_client()
    res = client.post(
        "/api/jobs/job-low/rescore-with-feedback",
        json={"feedback": "   "},
    )
    assert res.status_code == 400


def test_rescore_endpoint_404s_unknown_job(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    # No seed.
    with connect(db) as _:
        pass

    client = _load_legacy_dashboard_module().app.test_client()
    res = client.post(
        "/api/jobs/does-not-exist/rescore-with-feedback",
        json={"feedback": "anything"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 4. UI pin
# ---------------------------------------------------------------------------

def test_stage2_table_renders_disagree_column(tmp_path: Path, monkeypatch) -> None:
    """The Disagree column header + cell + JS handler must all be present
    so the user can submit a comment without an upstream code change."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_low_scored_job(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)

    assert ">Disagree?<" in html
    assert "disagreeCell(job)" in html
    assert "/api/jobs/" in html
    assert "rescore-with-feedback" in html


def test_latest_run_jobs_ships_score_after_feedback(
    tmp_path: Path, monkeypatch,
) -> None:
    """The API payload must include score_after_feedback so the row's
    score cell can render the old → new pair."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_low_scored_job(db)

    with connect(db) as conn:
        update_user_feedback_rescore(
            conn, "job-low",
            feedback="I have 5 years of Python experience not on my CV.",
            score=72,
            reason="reweighted skills",
        )

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/latest-run-jobs").get_json()
    row = next(j for j in payload if j["title"] == "Senior Product Manager")
    assert row["score"] == 45
    assert row["score_after_feedback"] == 72
    assert row["user_feedback"].startswith("I have 5 years")
