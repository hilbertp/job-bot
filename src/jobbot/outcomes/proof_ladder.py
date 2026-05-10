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

from enum import IntEnum


class ProofLevel(IntEnum):
    NONE = 0
    SMTP_ACCEPTED = 1
    NO_BOUNCE_24H = 2
    ACKNOWLEDGED = 3
    INTERVIEW = 4
    REJECTED = 5


def advance_proof_level(conn, job_id: str, level: ProofLevel, evidence: dict) -> bool:
    """Record evidence; update level if higher than current. Returns True if changed."""
    raise NotImplementedError("Copilot to implement per module docstring")


def verify_yourself_hint(level: ProofLevel, channel: str,
                         subject: str | None = None,
                         sender: str | None = None) -> str:
    """Return the language-appropriate verify-yourself hint for the digest row."""
    raise NotImplementedError("Copilot to implement per module docstring")
