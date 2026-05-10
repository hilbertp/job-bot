"""Apply to a job by sending an email from `hilbert@truenorth.berlin` with
CV + cover letter PDFs attached.

PRD §7.7 FR-APP-02.

Public entrypoint:
    send_email_application(job, profile, docs, secrets, config) -> ApplyResult

Subject template, language-aware:
    DE → "Bewerbung als <Title>"
    EN → "Application: <Title> — Philipp Hilbert"

Body = the cover letter, rendered to plain text from Markdown.
Attachments = `cv.pdf` + `cover_letter.pdf` from `docs.output_dir`.

SMTP creds come from secrets (TRUENORTH_SMTP_*). Never use Gmail for
outbound applications — Gmail is reserved for the digest + fallback only.

Returns ApplyResult with proof_level=1 on SMTP 250 OK, or proof_level=0 with
error string on any failure. The proof ladder advances to L2 later via
the daily inbox-scan job (no bounce after 24h).
"""
from __future__ import annotations

from ..config import Config, Secrets
from ..models import ApplyResult, GeneratedDocs, JobPosting
from ..profile import Profile


def send_email_application(
    job: JobPosting,
    profile: Profile,
    docs: GeneratedDocs,
    secrets: Secrets,
    config: Config,
) -> ApplyResult:
    """Send the application email. SMTP-accepted = L1; failure = L0 + error."""
    raise NotImplementedError("Copilot to implement per module docstring")
