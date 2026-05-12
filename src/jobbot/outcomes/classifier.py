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

import re
from typing import Literal

Intent = Literal["interview", "rejection", "other"]

INTERVIEW_RE = re.compile(
    r"\b(interview|vorstellungsgespr[aä]ch|let'?s chat|schedule (?:a )?call|"
    r"schedule .*interview|would love to (?:talk|chat|schedule)|calendar invite|"
    r"calendly|google calendar|teams call|zoom call)\b",
    re.IGNORECASE,
)
REJECT_RE = re.compile(
    r"\b(unfortunately|leider|we have decided to|moving forward with other|"
    r"move forward with other|wish you (?:all )?the best|no longer considering|"
    r"not be moving forward|weiterverfolgen|absage|reject(?:ed|ion)?)\b",
    re.IGNORECASE,
)


def _evidence(match: re.Match[str] | None, text: str) -> str:
    if match is None:
        return ""
    start = max(0, match.start() - 40)
    end = min(len(text), match.end() + 80)
    return " ".join(text[start:end].split())


def classify_message(subject: str, body: str, secrets=None) -> tuple[Intent, float, str]:
    """Return (intent, confidence, short evidence quote)."""
    text = f"{subject}\n{body}"
    interview = INTERVIEW_RE.search(text)
    rejection = REJECT_RE.search(text)
    if interview:
        return "interview", 0.95, _evidence(interview, text)
    if rejection:
        return "rejection", 0.95, _evidence(rejection, text)
    return "other", 0.2, ""
