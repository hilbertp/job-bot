"""End-to-end coverage for the Scoring Reason column.

Five contracts pin the new behavior so the dashboard stays debuggable:

1. ScoreResult carries the structured breakdown + optional discard_reason
   when the LLM returns them.
2. update_status persists both into seen_jobs (score_breakdown_json +
   discard_reason columns), and update_base_score_only does the same on
   the force-rescore path.
3. The dashboard's _parse_score_breakdown helper recovers the dict from
   EITHER the new JSON column OR the legacy "role=X, skills=Y, …" prefix
   in score_reason — so existing rows render cleanly without a migration.
4. The match_score prompt carries the classical-PO calibration rule that
   prevents demoting PO-coded postings. If anyone weakens or removes the
   rule, the test fails with a pointer to the missing phrase.
5. The match_score prompt instructs the LLM to emit a discard_reason
   when score < 50.
"""
from __future__ import annotations

import json
from pathlib import Path

from jobbot.config import REPO_ROOT
from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting, JobStatus, ScoreResult

_parse_score_breakdown = _load_legacy_dashboard_module()._parse_score_breakdown
from jobbot.state import (
    connect,
    update_base_score_only,
    update_status,
    upsert_new,
)


PROMPT_PATH = REPO_ROOT / "prompts" / "match_score.md"


# ---------------------------------------------------------------------------
# Contract 1 — ScoreResult shape
# ---------------------------------------------------------------------------

def test_score_result_accepts_breakdown_and_discard_reason() -> None:
    res = ScoreResult(
        score=42, reason="role=70, skills=50, location=40, seniority=30; weak fit",
        breakdown={"role": 70, "skills": 50, "location": 40, "seniority": 30},
        discard_reason="role is too junior / mostly backlog support",
    )
    assert res.breakdown == {"role": 70, "skills": 50, "location": 40, "seniority": 30}
    assert res.discard_reason == "role is too junior / mostly backlog support"


def test_score_result_breakdown_and_discard_default_to_none() -> None:
    """Backwards-compat: code that constructed ScoreResult before this
    PR (just `score` + `reason`) must keep working."""
    res = ScoreResult(score=82, reason="strong fit")
    assert res.breakdown is None
    assert res.discard_reason is None


# ---------------------------------------------------------------------------
# Contract 2 — persistence
# ---------------------------------------------------------------------------

def _seed(db: Path, job_id: str = "score_break_1") -> str:
    job = JobPosting(
        id=job_id, source="fake", title="Senior PM", company="ACME",
        url=f"https://example.com/jobs/{job_id}",
        description="x",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
    return job_id


def test_update_status_persists_breakdown_and_discard_reason(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db)

    with connect(db) as conn:
        update_status(
            conn, job_id, JobStatus.BELOW_THRESHOLD,
            score=45, reason="role=45, skills=52, location=90, seniority=40; weak",
            breakdown={"role": 45, "skills": 52, "location": 90, "seniority": 40},
            discard_reason="role is too junior / mostly backlog support",
        )
        row = conn.execute(
            "SELECT score, score_breakdown_json, discard_reason FROM seen_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    assert row["score"] == 45
    assert json.loads(row["score_breakdown_json"]) == {
        "role": 45, "skills": 52, "location": 90, "seniority": 40,
    }
    assert row["discard_reason"] == "role is too junior / mostly backlog support"


def test_update_base_score_only_persists_breakdown_and_discard_reason(
    tmp_path: Path, monkeypatch,
) -> None:
    """The force-rescore loop hits this code path; without persistence
    here, every force-rescore would silently lose the new fields."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db, "score_break_2")

    with connect(db) as conn:
        update_base_score_only(
            conn, job_id, score=72,
            reason="role=85, skills=82, location=45, seniority=80; bumped",
            breakdown={"role": 85, "skills": 82, "location": 45, "seniority": 80},
            discard_reason=None,
        )
        row = conn.execute(
            "SELECT score, score_breakdown_json, discard_reason FROM seen_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    assert row["score"] == 72
    assert json.loads(row["score_breakdown_json"])["role"] == 85
    assert row["discard_reason"] is None


# ---------------------------------------------------------------------------
# Contract 3 — dashboard parser handles BOTH old and new rows
# ---------------------------------------------------------------------------

def test_parse_breakdown_prefers_new_json_column() -> None:
    raw = json.dumps({"role": 82, "skills": 85, "location": 25, "seniority": 78})
    legacy_text = "role=99, skills=99, location=99, seniority=99; should be ignored"
    bd = _parse_score_breakdown(raw, legacy_text)
    assert bd == {"role": 82, "skills": 85, "location": 25, "seniority": 78}


def test_parse_breakdown_falls_back_to_legacy_text_when_json_missing() -> None:
    bd = _parse_score_breakdown(
        None,
        "role=80, skills=78, location=25, seniority=75; Strong PM/SaaS skills...",
    )
    assert bd == {"role": 80, "skills": 78, "location": 25, "seniority": 75}


def test_parse_breakdown_returns_none_when_neither_source_has_data() -> None:
    assert _parse_score_breakdown(None, "no axes embedded here") is None
    assert _parse_score_breakdown(None, None) is None
    assert _parse_score_breakdown("invalid json", None) is None


# ---------------------------------------------------------------------------
# Contract 4 — classical PO calibration is pinned in the prompt
# ---------------------------------------------------------------------------

def test_prompt_protects_classical_po_roles_from_being_demoted() -> None:
    """Failure mode: a clean PO posting (backlog ownership, sprint planning,
    refinement, story-writing) gets marked down because it's 'tactical' or
    'PO-coded rather than PM-coded'. The candidate has ~10y of PO experience
    and explicitly wants these roles in the shortlist."""
    prompt = PROMPT_PATH.read_text()

    assert "Classical Product Owner roles" in prompt
    assert "EXPLICIT target for this candidate" in prompt
    # The specific anti-pattern the model must not fall into:
    assert "PO-coded rather than PM-coded" in prompt
    assert "tactical" in prompt and "strategic" in prompt
    # The numerical floor:
    assert "score 75+ on role_match" in prompt


# ---------------------------------------------------------------------------
# Contract 5 — prompt instructs the LLM to emit discard_reason on low scores
# ---------------------------------------------------------------------------

def test_prompt_requires_discard_reason_when_score_below_50() -> None:
    prompt = PROMPT_PATH.read_text()

    # The output JSON shape must mention discard_reason:
    assert '"discard_reason"' in prompt
    # And the trigger condition must be explicit:
    assert "REQUIRED when score < 50" in prompt
    # And the model must NOT pad shortlist-quality rows with discard text:
    assert "OMITTED for higher scores" in prompt
