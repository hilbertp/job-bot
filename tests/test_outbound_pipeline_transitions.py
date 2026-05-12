"""CRM-style transitions on the Outbound Pipeline panel.

Each click on an action button POSTs to /api/applications/<id>/transition
with one of: received | replied | interview | rejected | bounced.

Contracts:
1. transition_application() updates proof_level + response_type +
   last_response_at on the applications row, and appends to
   proof_evidence (preserving timeline).
2. The "bounced" transition is special — it flips submitted=0 and
   seen_jobs.status=apply_failed so the row no longer counts as
   "applied + waiting for reply".
3. The HTTP endpoint validates the state name (400 on bad input)
   and returns 404 for unknown job_ids.
4. Repeated transitions are idempotent in the sense that the proof
   trail grows correctly — each call appends a new evidence entry
   without losing prior ones.
"""
from __future__ import annotations

import json
from pathlib import Path

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import ApplyResult, JobPosting, JobStatus
from jobbot.state import (
    VALID_APPLICATION_TRANSITIONS,
    connect,
    record_application,
    transition_application,
    update_status,
    upsert_new,
)


def _seed_submitted_application(db: Path, job_id: str = "tx_1") -> None:
    job = JobPosting(
        id=job_id, source="fake", title="PM", company="ACME",
        url=f"https://example.com/jobs/{job_id}",
        apply_url=f"https://example.com/jobs/{job_id}",
        description="x",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        record_application(
            conn, job_id,
            ApplyResult(
                status=JobStatus.APPLY_SUBMITTED, submitted=True,
                confirmation_url="mailto:careers@acme.test",
            ),
        )
        update_status(conn, job_id, JobStatus.APPLY_SUBMITTED)


# ---------------------------------------------------------------------------
# Contract 1 — transition writes proof_level / response_type / evidence
# ---------------------------------------------------------------------------

def test_received_transition_advances_proof_level_to_2(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_submitted_application(db)
    with connect(db) as conn:
        transition_application(conn, "tx_1", new_state="received", note="autoreply seen")
        row = conn.execute(
            "SELECT proof_level, response_type, last_response_at, proof_evidence "
            "FROM applications WHERE job_id = ?", ("tx_1",),
        ).fetchone()
    assert row["proof_level"] == 2
    assert row["response_type"] == "acknowledged"
    assert row["last_response_at"] is not None
    evidence = json.loads(row["proof_evidence"])
    # First entry is the original submitted record (from record_application);
    # second is the transition we just made.
    last = evidence[-1]
    assert last["transition"] == "received"
    assert last["source"] == "manual_transition"
    assert last["note"] == "autoreply seen"


def test_each_transition_writes_correct_state(tmp_path: Path, monkeypatch) -> None:
    expected = {
        "received":  (2, "acknowledged"),
        "replied":   (3, "replied"),
        "interview": (4, "interview"),
        "rejected":  (5, "rejected"),
    }
    for state, (level, rtype) in expected.items():
        db = tmp_path / f"jobbot_{state}.db"
        monkeypatch.setattr("jobbot.state.DB_PATH", db)
        _seed_submitted_application(db)
        with connect(db) as conn:
            transition_application(conn, "tx_1", new_state=state)
            row = conn.execute(
                "SELECT proof_level, response_type FROM applications WHERE job_id = ?",
                ("tx_1",),
            ).fetchone()
        assert (row["proof_level"], row["response_type"]) == (level, rtype), (
            f"{state} → expected (L{level}, {rtype}), got "
            f"(L{row['proof_level']}, {row['response_type']})"
        )


# ---------------------------------------------------------------------------
# Contract 2 — bounce flips submitted=0 + seen_jobs.status=apply_failed
# ---------------------------------------------------------------------------

def test_bounced_transition_marks_application_as_failed(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_submitted_application(db)
    with connect(db) as conn:
        transition_application(
            conn, "tx_1", new_state="bounced",
            note="NDR from postmaster@haufe-lexware.com",
        )
        row = conn.execute("""
            SELECT a.submitted, a.proof_level, a.status AS app_status, a.error,
                   s.status AS seen_status
            FROM applications a JOIN seen_jobs s ON s.id = a.job_id
            WHERE a.job_id = ?
        """, ("tx_1",)).fetchone()
    assert row["submitted"] == 0, "bounce must clear submitted=0"
    assert row["proof_level"] == 0
    assert row["app_status"] == "apply_failed"
    assert row["seen_status"] == "apply_failed", (
        "seen_jobs.status must drop out of apply_submitted so the funnel "
        "and the already-applied guard reflect the failed send"
    )
    assert "haufe-lexware" in (row["error"] or "")


# ---------------------------------------------------------------------------
# Contract 3 — HTTP endpoint validation
# ---------------------------------------------------------------------------

def test_post_transition_endpoint_happy_path(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_submitted_application(db)
    client = _load_legacy_dashboard_module().app.test_client()

    resp = client.post("/api/applications/tx_1/transition",
                       json={"state": "interview", "note": "phone screen booked"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True, "job_id": "tx_1", "state": "interview"}

    with connect(db) as conn:
        row = conn.execute(
            "SELECT proof_level FROM applications WHERE job_id = ?", ("tx_1",),
        ).fetchone()
    assert row["proof_level"] == 4


def test_post_transition_rejects_invalid_state(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_submitted_application(db)
    client = _load_legacy_dashboard_module().app.test_client()

    resp = client.post("/api/applications/tx_1/transition", json={"state": "ghosted"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "unsupported state" in body["error"]
    # The allowlist must include all 5 documented transitions:
    assert set(body["allowed"]) == set(VALID_APPLICATION_TRANSITIONS)


def test_post_transition_404_for_unknown_job(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.post("/api/applications/no_such_id/transition",
                       json={"state": "received"})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False


# ---------------------------------------------------------------------------
# Contract 4 — proof_evidence preserves the full timeline
# ---------------------------------------------------------------------------

def test_multiple_transitions_grow_the_proof_evidence_timeline(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_submitted_application(db)
    with connect(db) as conn:
        transition_application(conn, "tx_1", new_state="received",
                                note="auto-reply 24h after send")
        transition_application(conn, "tx_1", new_state="replied",
                                note="human reply 3 days later")
        transition_application(conn, "tx_1", new_state="interview",
                                note="phone screen booked for next week")
        row = conn.execute(
            "SELECT proof_level, response_type, proof_evidence "
            "FROM applications WHERE job_id = ?", ("tx_1",),
        ).fetchone()
    evidence = json.loads(row["proof_evidence"])
    transitions = [
        e["transition"] for e in evidence
        if isinstance(e, dict) and e.get("source") == "manual_transition"
    ]
    assert transitions == ["received", "replied", "interview"], (
        "manual_transition entries should accumulate in order"
    )
    # Final state reflects the LAST transition
    assert row["proof_level"] == 4
    assert row["response_type"] == "interview"
