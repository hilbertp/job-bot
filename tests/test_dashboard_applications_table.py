"""Stage 4 transparency — the per-application audit table.

Three contracts:
1. `/api/applications` returns one row per `applications` row with the
   fields the Stage 4 table renders (company, to, subject from .eml,
   proof_level, channel).
2. When the persisted .eml exists, the API surfaces its actual Subject
   header (so what's shown in the dashboard matches what was sent, not
   a reconstruction).
3. `/applications/<job_id>/application.eml` serves the persisted .eml
   when it exists, returns 404 otherwise — and refuses path traversal
   via the job_id.
"""
from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import ApplyResult, JobPosting, JobStatus
from jobbot.state import (
    connect,
    mark_application_manually,
    record_application,
    update_status,
    upsert_new,
)


def _seed_job_with_output_dir(
    db: Path, job_id: str, *, company: str, title: str,
    apply_email: str | None, output_dir: Path | None = None,
) -> None:
    job = JobPosting(
        id=job_id, source="fake", title=title, company=company,
        url=f"https://example.com/jobs/{job_id}",
        apply_url=f"https://example.com/jobs/{job_id}",
        description="x",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        if output_dir is not None:
            conn.execute(
                "UPDATE seen_jobs SET output_dir = ?, apply_email = ? WHERE id = ?",
                (str(output_dir), apply_email, job_id),
            )


def _write_eml(output_dir: Path, *, to: str, subject: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    msg = EmailMessage()
    msg["From"] = "hilbert@true-north.berlin"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("test body")
    (output_dir / "application.eml").write_bytes(bytes(msg))


def test_api_applications_returns_bot_send_with_real_subject_from_eml(
    tmp_path: Path, monkeypatch,
) -> None:
    """A bot-sent application must surface the exact Subject line from
    the persisted .eml so the operator sees what actually went out, not
    a reconstructed/templated guess."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    out = tmp_path / "out" / "bot_send_1"
    _seed_job_with_output_dir(
        db, "bot_send_1",
        company="ACME GmbH", title="Senior PM",
        apply_email="careers@acme.test", output_dir=out,
    )
    _write_eml(out, to="careers@acme.test",
               subject="Application: Senior PM — Philipp Hilbert")

    with connect(db) as conn:
        record_application(
            conn, "bot_send_1",
            ApplyResult(
                status=JobStatus.APPLY_SUBMITTED, submitted=True,
                confirmation_url="mailto:careers@acme.test",
            ),
        )
        update_status(conn, "bot_send_1", JobStatus.APPLY_SUBMITTED)

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/applications")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    r = rows[0]
    assert r["company"] == "ACME GmbH"
    assert r["title"] == "Senior PM"
    assert r["channel"] == "bot"
    assert r["to"] == "careers@acme.test"
    assert r["subject"] == "Application: Senior PM — Philipp Hilbert"
    assert r["proof_level"] == 1
    assert r["submitted"] is True
    assert r["has_eml"] is True


def test_api_applications_surfaces_manual_marks_without_eml(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_job_with_output_dir(
        db, "manual_1",
        company="HERO Software", title="Senior PM (manual)",
        apply_email=None,
    )
    with connect(db) as conn:
        mark_application_manually(conn, "manual_1",
                                  note="Applied via LinkedIn UI")

    client = _load_legacy_dashboard_module().app.test_client()
    rows = client.get("/api/applications").get_json()
    manual = [r for r in rows if r["job_id"] == "manual_1"][0]
    assert manual["channel"] == "manual"
    assert manual["has_eml"] is False
    # No .eml on disk, so subject is None — the table renders the fallback
    # placeholder ("(no subject captured)") client-side, not server-side.
    assert manual["subject"] is None
    assert manual["proof_level"] == 1


def test_application_eml_route_serves_file_when_present(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    out = tmp_path / "out" / "eml_1"
    _seed_job_with_output_dir(
        db, "eml_1", company="ACME", title="PM",
        apply_email="careers@acme.test", output_dir=out,
    )
    _write_eml(out, to="careers@acme.test", subject="Application: PM")

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/applications/eml_1/application.eml")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Subject: Application: PM" in body
    assert "To: careers@acme.test" in body


def test_application_eml_route_404_when_no_eml_on_disk(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    out = tmp_path / "out" / "no_eml"
    _seed_job_with_output_dir(
        db, "no_eml", company="X", title="X",
        apply_email=None, output_dir=out,
    )
    # output_dir exists but no application.eml inside it
    out.mkdir(parents=True, exist_ok=True)

    client = _load_legacy_dashboard_module().app.test_client()
    assert client.get("/applications/no_eml/application.eml").status_code == 404


def test_application_eml_route_404_when_job_unknown(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    client = _load_legacy_dashboard_module().app.test_client()
    assert client.get("/applications/nonexistent/application.eml").status_code == 404


def test_application_eml_route_rejects_path_traversal_via_job_id(
    tmp_path: Path, monkeypatch,
) -> None:
    """A job_id with .. shouldn't be able to walk outside its output_dir.
    Flask normalises /../ in URL paths so the route never matches for such
    inputs — but it's still worth asserting the behaviour."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/applications/..%2F..%2Fetc%2Fpasswd/application.eml")
    assert resp.status_code in (404, 400)
