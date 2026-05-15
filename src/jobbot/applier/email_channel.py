"""Apply to a job by sending an email from `hilbert@true-north.berlin` with
CV + cover letter PDFs attached.

PRD §7.7 FR-APP-02.

Public entrypoint:
    send_email_application(job, profile, docs, secrets, config) -> ApplyResult

Subject template, language-aware:
    DE → "Bewerbung als <Title>"
    EN → "Application: <Title>, <Candidate Name>"

Body = the cover letter, plain-text + HTML alternatives.
Attachments = `cv.pdf` + `cover_letter.pdf` from `docs.output_dir`.

SMTP creds come from secrets (TRUENORTH_SMTP_*). Never use Gmail for
outbound applications, Gmail is reserved for the digest + fallback only.

Safety rails:
- If config.apply.dry_run is true → write the rendered .eml to
  docs.output_dir/application.eml and return without sending.
- If any TRUENORTH_SMTP_* secret is missing → also dry-run, regardless
  of config, with a needs_review_reason that names the missing creds.
The channel CANNOT accidentally send when the operator hasn't both
flipped the config flag AND provided the SMTP credentials.

Returns ApplyResult with submitted=True on SMTP 250 OK; the proof ladder
advances to L2 later via the daily inbox-scan job (no bounce after 24h).
"""
from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from ..config import Config, Secrets
from ..models import ApplyResult, GeneratedDocs, JobPosting, JobStatus
from ..profile import Profile

DEFAULT_FROM_ADDRESS = "hilbert@true-north.berlin"

# Heuristic German-vs-English language detection on title + first chunk of
# description. Catches the common gender markers (m/w/d), German cities,
# and a small set of postings-specific filler words. Defaults to English
# when neither fires.
_DE_INDICATORS = re.compile(
    r"\(m[\s/|]?w[\s/|]?d\)|\(d[\s/|]?m[\s/|]?w\)|\(w[\s/|]?m[\s/|]?d\)|"
    r"\b(Bewerbung|Berlin|München|Hamburg|Köln|Deutschland|deutschlandweit|"
    r"Mitarbeiter:?in|Stellenbeschreibung|Vollzeit|Teilzeit|Stelle|"
    r"Aufgaben|Anforderungen|Standort|Erfahrung|Erforderlich)\b",
    re.IGNORECASE,
)


def _detect_language(job: JobPosting) -> str:
    text = f"{job.title or ''} {(job.description or '')[:600]}"
    return "de" if _DE_INDICATORS.search(text) else "en"


def _subject(job: JobPosting, profile: Profile) -> str:
    lang = _detect_language(job)
    title = (job.title or "").strip()
    if lang == "de":
        return f"Bewerbung als {title}".strip()
    name = (profile.personal or {}).get("full_name", "").strip()
    return f"Application: {title}, {name}".rstrip(" ,")


def _from_address(secrets: Secrets) -> str:
    return (secrets.truenorth_smtp_user or "").strip() or DEFAULT_FROM_ADDRESS


def _missing_smtp_creds(secrets: Secrets) -> list[str]:
    missing: list[str] = []
    if not (secrets.truenorth_smtp_host or "").strip():
        missing.append("TRUENORTH_SMTP_HOST")
    if not (secrets.truenorth_smtp_user or "").strip():
        missing.append("TRUENORTH_SMTP_USER")
    if not (secrets.truenorth_smtp_pass or "").strip():
        missing.append("TRUENORTH_SMTP_PASS")
    return missing


def _build_message(
    job: JobPosting, profile: Profile, docs: GeneratedDocs, secrets: Secrets,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = _from_address(secrets)
    msg["To"] = job.apply_email or ""
    msg["Subject"] = _subject(job, profile)
    msg.set_content(docs.cover_letter_md or "")
    if docs.cover_letter_html:
        msg.add_alternative(docs.cover_letter_html, subtype="html")

    # Prefer the unified opus-style application package (one polished PDF
    # with cover letter as Section I and CV as Section II). Fall back to
    # the separate cv.pdf + cover_letter.pdf when the package didn't render
    #, recruiters get something either way.
    if docs.application_package_pdf and Path(docs.application_package_pdf).exists():
        attachments: list[tuple[str, str]] = [
            ("application_package.pdf", docs.application_package_pdf),
        ]
    else:
        attachments = [
            ("cv.pdf", docs.cv_pdf or ""),
            ("cover_letter.pdf", docs.cover_letter_pdf or ""),
        ]
    for filename, pdf_path in attachments:
        if not pdf_path:
            continue
        p = Path(pdf_path)
        if not p.exists():
            continue
        msg.add_attachment(
            p.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=filename,
        )
    return msg


def send_email_application(
    job: JobPosting,
    profile: Profile,
    docs: GeneratedDocs,
    secrets: Secrets,
    config: Config,
) -> ApplyResult:
    """Send the application email, or save a dry-run .eml for review."""
    if not job.apply_email:
        return ApplyResult(
            status=JobStatus.APPLY_NEEDS_REVIEW,
            needs_review_reason="email_channel: no apply_email on posting",
        )

    msg = _build_message(job, profile, docs, secrets)
    output_dir = Path(docs.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    eml_path = output_dir / "application.eml"

    missing = _missing_smtp_creds(secrets)
    forced_dry = bool(missing)
    is_dry_run = config.apply.dry_run or forced_dry

    if is_dry_run:
        eml_path.write_bytes(bytes(msg))
        if forced_dry and not config.apply.dry_run:
            reason = (
                "email_channel: smtp_creds_missing, review application.eml; "
                f"set {', '.join(missing)} in .env to enable live send"
            )
        else:
            reason = (
                "email_channel: dry_run, review application.eml before "
                "flipping config.apply.dry_run=false"
            )
        return ApplyResult(
            status=JobStatus.APPLY_NEEDS_REVIEW,
            submitted=False,
            dry_run=True,
            needs_review_reason=reason,
            confirmation_url=str(eml_path),
        )

    try:
        with smtplib.SMTP(
            secrets.truenorth_smtp_host, secrets.truenorth_smtp_port,
            timeout=30,
        ) as smtp:
            smtp.starttls()
            smtp.login(secrets.truenorth_smtp_user, secrets.truenorth_smtp_pass)
            smtp.send_message(msg)
    except Exception as e:
        # Persist the .eml so the operator can inspect what was attempted.
        eml_path.write_bytes(bytes(msg))
        return ApplyResult(
            status=JobStatus.APPLY_FAILED,
            submitted=False,
            error=f"email_channel: smtp_send_failed: {type(e).__name__}: {e}",
            confirmation_url=str(eml_path),
        )

    # Persist the sent message for audit / inbox-scan reply matching.
    eml_path.write_bytes(bytes(msg))
    return ApplyResult(
        status=JobStatus.APPLY_SUBMITTED,
        submitted=True,
        confirmation_url=f"mailto:{job.apply_email}",
    )
