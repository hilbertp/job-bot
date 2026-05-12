"""Append-only evidence accumulator for application proof levels.

PRD §7.8 FR-OUT-01..02.

Each application row in `applications` carries:
  - proof_level INT (0-5)
  - proof_evidence TEXT (JSON list, append-only)
  - status TEXT
  - last_checked_at TEXT

`advance_proof_level(conn, job_id, level, evidence)` records a new piece of
evidence and updates `proof_level` / `status` if the new level is strictly
higher than the current one. Lower-level evidence (e.g. another bounce-check
returning "still no bounce") still updates `last_checked_at` but doesn't
change the level.

`verify_yourself_hint(level, channel, subject, sender)` returns the
human-readable hint shown in the digest at each level.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import IntEnum

from ..models import JobStatus


class ProofLevel(IntEnum):
    NONE = 0
    SMTP_ACCEPTED = 1
    NO_BOUNCE_24H = 2
    ACKNOWLEDGED = 3
    INTERVIEW = 4
    REJECTED = 5


_STATUS_BY_LEVEL = {
    ProofLevel.NONE: JobStatus.APPLY_FAILED.value,
    ProofLevel.SMTP_ACCEPTED: JobStatus.APPLY_SUBMITTED.value,
    ProofLevel.NO_BOUNCE_24H: JobStatus.WAITING_RESPONSE.value,
    ProofLevel.ACKNOWLEDGED: JobStatus.EMPLOYER_RECEIVED.value,
    ProofLevel.INTERVIEW: JobStatus.INTERVIEW_INVITED.value,
    ProofLevel.REJECTED: JobStatus.REJECTED.value,
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _response_type(level: ProofLevel) -> str | None:
    if level == ProofLevel.ACKNOWLEDGED:
        return "acknowledgement"
    if level == ProofLevel.INTERVIEW:
        return "interview"
    if level == ProofLevel.REJECTED:
        return "rejection"
    return None


def advance_proof_level(conn, job_id: str, level: ProofLevel, evidence: dict) -> bool:
    """Record evidence; update level if higher than current. Returns True if changed."""
    row = conn.execute(
        "SELECT proof_level, proof_evidence FROM applications WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        return False

    current = int(row["proof_level"] or 0)
    try:
        evidence_items = json.loads(row["proof_evidence"] or "[]")
        if not isinstance(evidence_items, list):
            evidence_items = []
    except json.JSONDecodeError:
        evidence_items = []

    now = _now()
    item = dict(evidence)
    item.setdefault("level", int(level))
    item.setdefault("at", now)
    evidence_items.append(item)

    response_type = _response_type(level)
    response_subject = evidence.get("subject")
    response_snippet = evidence.get("snippet") or evidence.get("body") or evidence.get("evidence")

    changed = int(level) > current
    if changed:
        conn.execute(
            "UPDATE applications SET proof_level = ?, status = ?, proof_evidence = ?, "
            "last_checked_at = ?, "
            "received_at = COALESCE(received_at, ?), "
            "last_response_at = CASE WHEN ? IS NOT NULL THEN ? ELSE last_response_at END, "
            "response_type = COALESCE(?, response_type), "
            "response_subject = COALESCE(?, response_subject), "
            "response_snippet = COALESCE(?, response_snippet) "
            "WHERE job_id = ?",
            (
                int(level), _STATUS_BY_LEVEL[level], json.dumps(evidence_items), now,
                now if int(level) >= int(ProofLevel.ACKNOWLEDGED) else None,
                response_type, now,
                response_type, response_subject, response_snippet,
                job_id,
            ),
        )
    else:
        conn.execute(
            "UPDATE applications SET proof_evidence = ?, last_checked_at = ? "
            "WHERE job_id = ?",
            (json.dumps(evidence_items), now, job_id),
        )
    return changed


def verify_yourself_hint(level: ProofLevel, channel: str,
                         subject: str | None = None,
                         sender: str | None = None) -> str:
    """Return the language-appropriate verify-yourself hint for the digest row."""
    source = sender or channel
    if level == ProofLevel.REJECTED:
        return f"Rejection detected from {source}; verify before snoozing or archiving."
    if level == ProofLevel.INTERVIEW:
        return f"Interview signal detected from {source}; open the message and schedule."
    if level == ProofLevel.ACKNOWLEDGED:
        return f"Employer response received from {source}; verify the thread."
    if level == ProofLevel.NO_BOUNCE_24H:
        return "No bounce detected after 24h; keep waiting for a human reply."
    if level == ProofLevel.SMTP_ACCEPTED:
        return "Submitted; inbox scan has not yet confirmed delivery outcome."
    return "No submission proof yet; verify manually."
