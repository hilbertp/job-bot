"""Classify an inbound email as one of: interview | rejection | other.

PRD §7.8 FR-OUT-01 (levels L4 / L5 detection).

Strategy: cheap regex prefilter, then Claude Haiku for ambiguous cases.

Regex prefilter (catches ~80% with no LLM cost):
  INTERVIEW_RE = compile of: interview, vorstellungsgespräch, "let's chat",
                              calendar invite (text/calendar in headers),
                              "would love to talk", "schedule a call"
  REJECT_RE    = compile of: unfortunately, leider, "we have decided to",
                              "weiterverfolgen", "moving forward with other",
                              "wish you the best", "no longer considering"

If both fire (rare — interview-after-rejection), prefer interview.
If neither fires and the message is from a company we've applied to,
fall back to LLM with a short JSON-output prompt.

Returns (intent, confidence, evidence_quote).
intent ∈ {"interview", "rejection", "other"}.
confidence ∈ [0, 1] for both regex (0.95) and LLM paths.
"""
from __future__ import annotations

from typing import Literal

Intent = Literal["interview", "rejection", "other"]


def classify_message(subject: str, body: str, secrets=None) -> tuple[Intent, float, str]:
    """Return (intent, confidence, short evidence quote)."""
    raise NotImplementedError("Copilot to implement per module docstring")
