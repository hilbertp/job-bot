"""Inbox scanner end-to-end: IMAP walk → classify → transition cards.

Five contracts pinned:

1. Bounce-pattern message that names a recipient we sent to → the
   matching application gets transitioned to `bounced` (proof L0,
   submitted=0, seen_jobs.status=apply_failed).
2. Auto-reply-pattern message from the same recipient → matching
   application transitions to `received` (proof L2).
3. Interview-signal message → transitions to `interview` (proof L4).
4. Rejection-signal message → transitions to `rejected` (proof L5).
5. Missing TRUENORTH SMTP creds → IMAP pass skipped cleanly; the
   no-bounce-24h pass still runs.
"""
from __future__ import annotations

import email
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jobbot.config import ApplyConfig, Config, DigestConfig, Secrets, SourceConfig
from jobbot.models import ApplyResult, JobPosting, JobStatus
from jobbot.outcomes import inbox_scanner
from jobbot.state import (
    connect,
    record_application,
    update_status,
    upsert_new,
)


def _seed_sent(db: Path, *, job_id: str, company: str, apply_email: str) -> None:
    job = JobPosting(
        id=job_id, source="fake", title="PM", company=company,
        url=f"https://example.com/jobs/{job_id}",
        apply_url=f"https://example.com/jobs/{job_id}",
        description="x",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        conn.execute(
            "UPDATE seen_jobs SET apply_email = ? WHERE id = ?",
            (apply_email, job_id),
        )
        record_application(
            conn, job_id,
            ApplyResult(
                status=JobStatus.APPLY_SUBMITTED, submitted=True,
                confirmation_url=f"mailto:{apply_email}",
            ),
        )
        update_status(conn, job_id, JobStatus.APPLY_SUBMITTED)


def _make_eml(*, subject: str, from_addr: str, body: str,
              extra_headers: dict[str, str] | None = None) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = "hilbert@true-north.berlin"
    msg["Subject"] = subject
    for k, v in (extra_headers or {}).items():
        msg[k] = v
    msg.set_content(body)
    return bytes(msg)


class _FakeIMAP:
    """Stand-in for imaplib.IMAP4_SSL that replays a fixed message list."""
    def __init__(self, eml_messages: list[bytes]):
        self._messages = eml_messages
        self.seen_uids: list[bytes] = []

    def select(self, *args, **kwargs): return ("OK", [b"1"])
    def search(self, *args, **kwargs):
        uids = b" ".join(str(i + 1).encode() for i in range(len(self._messages)))
        return ("OK", [uids])
    def fetch(self, uid, what):
        idx = int(uid) - 1
        if 0 <= idx < len(self._messages):
            return ("OK", [(b"x", self._messages[idx])])
        return ("NO", [b""])
    def store(self, uid, flags, val):
        self.seen_uids.append(uid)
        return ("OK", [b""])
    def logout(self): return ("BYE", [b""])


def _secrets_with_imap() -> Secrets:
    return Secrets(
        anthropic_api_key="x", gmail_address="a@b", gmail_app_password="x",
        notify_to="a@b",
        truenorth_smtp_host="smtp.ionos.de", truenorth_smtp_port=587,
        truenorth_smtp_user="hilbert@true-north.berlin",
        truenorth_smtp_pass="appapikey",
        truenorth_imap_host="imap.ionos.de", truenorth_imap_port=993,
    )


def _config() -> Config:
    return Config(
        score_threshold=70, max_jobs_per_run=10,
        digest=DigestConfig(generate_docs_above_score=70, max_per_email=10),
        apply=ApplyConfig(dry_run=True),
        sources={"fake": SourceConfig(enabled=True, auto_submit=False)},
    )


# ---------------------------------------------------------------------------
# Contract 1 — bounce
# ---------------------------------------------------------------------------

def test_bounce_message_transitions_application_to_bounced(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_sent(db, job_id="haufe_1",
               company="Haufe Group SE",
               apply_email="marco.andris@haufe-lexware.com")

    bounce_eml = _make_eml(
        from_addr="mailer-daemon@example.com",
        subject="Mail delivery failed: returning message to sender",
        body=(
            "Your email could not be delivered. The following recipient "
            "address(es) could not be reached:\n"
            "  * marco.andris@haufe-lexware.com\n"
            "  Reason: 550 5.1.1 User unknown"
        ),
    )
    fake_imap = _FakeIMAP([bounce_eml])
    monkeypatch.setattr(inbox_scanner, "_imap_connect", lambda secrets: fake_imap)

    with connect(db) as conn:
        counts = inbox_scanner.scan_inbox(conn, _secrets_with_imap(), _config())
        row = conn.execute("""
            SELECT a.submitted, a.proof_level, a.status AS app_status,
                   a.response_type, a.error, s.status AS seen_status
            FROM applications a JOIN seen_jobs s ON s.id = a.job_id
            WHERE a.job_id = ?
        """, ("haufe_1",)).fetchone()

    assert counts["bounces"] == 1
    assert row["submitted"] == 0
    assert row["proof_level"] == 0
    assert row["app_status"] == "apply_failed"
    assert row["response_type"] == "bounced"
    assert row["seen_status"] == "apply_failed"
    assert fake_imap.seen_uids, "matched messages must be marked \\Seen"


# ---------------------------------------------------------------------------
# Contract 2 — auto-reply
# ---------------------------------------------------------------------------

def test_autoreply_message_transitions_application_to_received(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_sent(db, job_id="nox_1",
               company="nox Germany GmbH",
               apply_email="bewerbungen@nox-nachtexpress.de")

    autoreply_eml = _make_eml(
        from_addr="bewerbungen@nox-nachtexpress.de",
        subject="Automatic reply: Bewerbung als Product Owner",
        body="Liebe Bewerbende, herzlichen Dank für deine E-Mail …",
        extra_headers={"Auto-Submitted": "auto-replied"},
    )
    fake_imap = _FakeIMAP([autoreply_eml])
    monkeypatch.setattr(inbox_scanner, "_imap_connect", lambda secrets: fake_imap)

    with connect(db) as conn:
        counts = inbox_scanner.scan_inbox(conn, _secrets_with_imap(), _config())
        row = conn.execute(
            "SELECT proof_level, response_type FROM applications WHERE job_id = ?",
            ("nox_1",),
        ).fetchone()

    assert counts["auto_replies"] == 1
    assert row["proof_level"] == 2
    assert row["response_type"] == "acknowledged"


# ---------------------------------------------------------------------------
# Contract 3 — interview
# ---------------------------------------------------------------------------

def test_interview_message_transitions_to_interview(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_sent(db, job_id="eterno_1", company="ETERNO",
               apply_email="careers@eterno.health")

    interview_eml = _make_eml(
        from_addr="careers@eterno.health",
        subject="Re: Your application — let's schedule a call",
        body="Hi Philipp, thanks for applying. Could we schedule a call next week?",
    )
    fake_imap = _FakeIMAP([interview_eml])
    monkeypatch.setattr(inbox_scanner, "_imap_connect", lambda secrets: fake_imap)

    with connect(db) as conn:
        counts = inbox_scanner.scan_inbox(conn, _secrets_with_imap(), _config())
        row = conn.execute(
            "SELECT proof_level, response_type FROM applications WHERE job_id = ?",
            ("eterno_1",),
        ).fetchone()

    assert counts["interviews"] == 1
    assert row["proof_level"] == 4
    assert row["response_type"] == "interview"


# ---------------------------------------------------------------------------
# Contract 4 — rejection
# ---------------------------------------------------------------------------

def test_rejection_message_transitions_to_rejected(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_sent(db, job_id="some_1", company="Some Co",
               apply_email="careers@some.com")

    reject_eml = _make_eml(
        from_addr="careers@some.com",
        subject="Update on your application",
        body=("Unfortunately we have decided to move forward with other candidates. "
              "We wish you the best in your search."),
    )
    fake_imap = _FakeIMAP([reject_eml])
    monkeypatch.setattr(inbox_scanner, "_imap_connect", lambda secrets: fake_imap)

    with connect(db) as conn:
        counts = inbox_scanner.scan_inbox(conn, _secrets_with_imap(), _config())
        row = conn.execute(
            "SELECT proof_level, response_type FROM applications WHERE job_id = ?",
            ("some_1",),
        ).fetchone()

    assert counts["rejections"] == 1
    assert row["proof_level"] == 5
    assert row["response_type"] == "rejected"


# ---------------------------------------------------------------------------
# Contract 5 — missing creds doesn't crash; no-bounce-24h still runs
# ---------------------------------------------------------------------------

def test_scan_without_imap_creds_skips_imap_walk_cleanly(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_sent(db, job_id="x_1", company="X", apply_email="x@y.com")
    # Force the IMAP connector to return None.
    monkeypatch.setattr(inbox_scanner, "_imap_connect", lambda secrets: None)

    no_creds = Secrets(
        anthropic_api_key="x", gmail_address="a@b", gmail_app_password="x",
        notify_to="a@b",
        # Note: no truenorth_smtp_* set
    )
    with connect(db) as conn:
        counts = inbox_scanner.scan_inbox(conn, no_creds, _config())

    assert counts["imap_messages"] == 0
    assert counts["matched"] == 0
    # The checked count still reflects the application audit even when
    # the IMAP walk is skipped — the no-bounce-24h pass needs it.
    assert counts["checked"] == 1
