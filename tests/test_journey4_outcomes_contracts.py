"""Journey 4 contract tests for inbound employer outcomes.

These are strict xfail tests by design. They document the backend and UI
contract for the "sent / received / waiting / rejected / interview" journey
before the implementation exists.
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(
    strict=True,
    reason="Journey 4 JobStatus values are not modeled yet",
)
def test_journey4_job_status_values_are_modeled() -> None:
    from jobbot.models import JobStatus

    assert JobStatus.EMPLOYER_RECEIVED.value == "employer_received"
    assert JobStatus.WAITING_RESPONSE.value == "waiting_response"
    assert JobStatus.REJECTED.value == "rejected"
    assert JobStatus.INTERVIEW_INVITED.value == "interview_invited"


@pytest.mark.xfail(
    strict=True,
    reason="Applications response metadata or responses table is not modeled yet",
)
def test_application_response_persistence_schema_exists(tmp_path, monkeypatch) -> None:
    from jobbot.state import connect

    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")
    with connect() as conn:
        app_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(applications)")
        }
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    required_response_cols = {
        "received_at",
        "last_response_at",
        "response_type",
        "response_subject",
        "response_snippet",
    }
    assert required_response_cols.issubset(app_cols) or "responses" in tables


@pytest.mark.xfail(
    strict=True,
    reason="Inbound email classifier is not implemented yet",
)
def test_inbound_classifier_detects_interview_and_rejection() -> None:
    from jobbot.outcomes.classifier import classify_message

    assert classify_message(
        "Interview invitation",
        "We would love to schedule a call next week.",
    )[0] == "interview"
    assert classify_message(
        "Application update",
        "Unfortunately, we have decided to move forward with other candidates.",
    )[0] == "rejection"


@pytest.mark.xfail(
    strict=True,
    reason="Proof ladder status transitions are not implemented yet",
)
def test_proof_ladder_advances_application_to_employer_received(
    tmp_path, monkeypatch,
) -> None:
    from jobbot.models import ApplyResult, JobPosting, JobStatus
    from jobbot.outcomes.proof_ladder import ProofLevel, advance_proof_level
    from jobbot.state import connect, record_application, upsert_new

    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")
    job = JobPosting(
        id="outcome_1",
        source="fake",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/outcome_1",  # type: ignore
        apply_url="https://example.com/jobs/outcome_1",  # type: ignore
        description=" ".join(["responsibility"] * 240),
    )

    with connect() as conn:
        upsert_new(conn, [job])
        record_application(
            conn,
            job.id,
            ApplyResult(
                status=JobStatus.APPLY_SUBMITTED,
                submitted=True,
                dry_run=False,
                confirmation_url="https://example.com/confirmation",
            ),
        )
        changed = advance_proof_level(
            conn,
            job.id,
            ProofLevel.ACKNOWLEDGED,
            {
                "source": "inbox",
                "sender": "recruiter@acme.example",
                "subject": "We received your application",
            },
        )
        row = conn.execute(
            "SELECT status, proof_level, proof_evidence FROM applications WHERE job_id = ?",
            (job.id,),
        ).fetchone()

    assert changed is True
    assert row["status"] == JobStatus.EMPLOYER_RECEIVED.value
    assert row["proof_level"] == ProofLevel.ACKNOWLEDGED.value
    assert "recruiter@acme.example" in row["proof_evidence"]


@pytest.mark.xfail(
    strict=True,
    reason="scan-inbox CLI command is not registered yet",
)
def test_scan_inbox_cli_command_is_registered(monkeypatch) -> None:
    import jobbot.cli as cli_module

    calls: list[str] = []
    monkeypatch.setattr(
        "jobbot.outcomes.scan_inbox",
        lambda *_args, **_kwargs: calls.append("scan") or {"checked": 0},
    )

    rc = cli_module.main(["scan-inbox"])

    assert rc == 0
    assert calls == ["scan"]


@pytest.mark.xfail(
    strict=True,
    reason="Dashboard Stage 4 outcome panel is not implemented yet",
)
def test_dashboard_renders_stage4_outcome_panel(tmp_path, monkeypatch) -> None:
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")
    client = _load_legacy_dashboard_module().app.test_client()

    resp = client.get("/")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Stage 4" in html
    assert "Received" in html
    assert "Waiting" in html
    assert "Rejected" in html
    assert "Interview" in html
