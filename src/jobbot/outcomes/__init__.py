"""outcomes, proof-ladder tracking for sent applications.

PRD §7.8.

Each application accumulates evidence as time passes:
  L0, none (failed before send)
  L1, SMTP 250 OK or form confirmation page (captured at send time)
  L2, no bounce after 24h (captured by inbox_scanner)
  L3, human reply from <company-domain> (captured by inbox_scanner)
  L4, reply contains interview / Vorstellungsgespräch / calendar invite
  L5, reply contains rejection language

Status flips: pending → submitted (L1+) → acknowledged (L3) →
              interview (L4) | rejected (L5) | failed (L0)

When L5 is reached, the snooze table records the company with
snooze_until = now + 6 months so future scrapes from the same company are
skipped.
"""
from .proof_ladder import advance_proof_level, ProofLevel  # noqa: F401
from .inbox_scanner import scan_inbox  # noqa: F401
