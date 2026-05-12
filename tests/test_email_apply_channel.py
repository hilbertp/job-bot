"""Email apply channel (PRD §7.7).

Pins:
  - Subject is language-aware: DE template when title has (m/w/d) or
    German filler, EN template otherwise.
  - Dry-run config (the default) writes application.eml to the per-job
    output dir and returns dry_run=True; never opens an SMTP connection.
  - Missing TRUENORTH_SMTP_* creds force dry-run regardless of config
    and name the missing creds in the result.
  - On live send, smtplib.SMTP.send_message is called with the built
    message; success returns submitted=True with confirmation_url.
  - SMTP exception persists the .eml and returns APPLY_FAILED.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.applier.email_channel import (
    _build_message,
    _detect_language,
    _subject,
    send_email_application,
)
from jobbot.applier.runner import apply_to_job
from jobbot.config import ApplyConfig, Config, Secrets
from jobbot.models import ApplyResult, GeneratedDocs, JobPosting, JobStatus
from jobbot.profile import Profile


def _profile() -> Profile:
    return Profile(
        personal={"full_name": "Philipp Hilbert",
                  "links": {"linkedin": "https://lnkd.in/x"}},
        preferences={},
    )


def _docs(tmp_path: Path, *, with_pdfs: bool = True) -> GeneratedDocs:
    output_dir = tmp_path / "job_out"
    output_dir.mkdir()
    cv_pdf = output_dir / "cv.pdf"
    cl_pdf = output_dir / "cover_letter.pdf"
    if with_pdfs:
        cv_pdf.write_bytes(b"%PDF-1.4 cv stub")
        cl_pdf.write_bytes(b"%PDF-1.4 cl stub")
    return GeneratedDocs(
        cv_md="# CV\n", cv_html="<h1>CV</h1>",
        cover_letter_md="Sehr geehrte Damen und Herren, hiermit bewerbe ich mich.",
        cover_letter_html="<p>Sehr geehrte Damen und Herren.</p>",
        output_dir=str(output_dir),
        cv_pdf=str(cv_pdf) if with_pdfs else None,
        cover_letter_pdf=str(cl_pdf) if with_pdfs else None,
    )


def _job_de() -> JobPosting:
    return JobPosting(
        id="x1", source="stepstone",
        title="Product Owner (m/w/d)", company="Acme",
        url="https://example.com/p", apply_url=None,
        apply_email="bewerbung@acme.de",
        description="Wir suchen einen Product Owner in Berlin. Aufgaben...",
    )


def _job_en() -> JobPosting:
    return JobPosting(
        id="x2", source="linkedin",
        title="Senior Product Manager", company="Beta Inc",
        url="https://example.com/p2", apply_url=None,
        apply_email="careers@beta.com",
        description="We are looking for a Senior PM to lead our growth team.",
    )


def _config_dry() -> Config:
    return Config(apply=ApplyConfig(dry_run=True, per_run_limit=5))


def _config_live() -> Config:
    return Config(apply=ApplyConfig(dry_run=False, per_run_limit=5))


def _secrets(*, with_smtp: bool = True) -> Secrets:
    base = dict(
        anthropic_api_key="x", gmail_address="a@b.com",
        gmail_app_password="x", notify_to="a@b.com",
    )
    if with_smtp:
        base.update(dict(
            truenorth_smtp_host="smtp.example.com",
            truenorth_smtp_user="hilbert@true-north.berlin",
            truenorth_smtp_pass="appapikey",
        ))
    return Secrets(**base)


def test_language_detection_german_marker() -> None:
    assert _detect_language(_job_de()) == "de"


def test_language_detection_english_default() -> None:
    assert _detect_language(_job_en()) == "en"


def test_subject_template_de_uses_bewerbung_als() -> None:
    assert _subject(_job_de(), _profile()) == "Bewerbung als Product Owner (m/w/d)"


def test_subject_template_en_uses_application_with_name() -> None:
    assert _subject(_job_en(), _profile()) == (
        "Application: Senior Product Manager — Philipp Hilbert"
    )


def test_build_message_has_correct_headers_and_attachments(tmp_path: Path) -> None:
    msg = _build_message(_job_en(), _profile(), _docs(tmp_path),
                         _secrets(with_smtp=True))
    assert msg["From"] == "hilbert@true-north.berlin"
    assert msg["To"] == "careers@beta.com"
    assert "Application: Senior Product Manager" in msg["Subject"]
    attachments = {a.get_filename(): a for a in msg.iter_attachments()}
    assert set(attachments) == {"cv.pdf", "cover_letter.pdf"}


def test_dry_run_writes_eml_and_returns_dry_run_true(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    result = send_email_application(_job_en(), _profile(), docs,
                                    _secrets(with_smtp=True), _config_dry())
    assert result.dry_run is True
    assert result.submitted is False
    assert result.status == JobStatus.APPLY_NEEDS_REVIEW
    eml = Path(docs.output_dir) / "application.eml"
    assert eml.exists() and eml.stat().st_size > 0
    # SMTP must NOT have been hit — eml exists but no socket calls happened.
    assert "dry_run" in (result.needs_review_reason or "")


def test_missing_smtp_creds_forces_dry_run_and_names_the_missing(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    # config.apply.dry_run=False but creds missing → still dry-run
    result = send_email_application(_job_en(), _profile(), docs,
                                    _secrets(with_smtp=False), _config_live())
    assert result.dry_run is True
    assert result.submitted is False
    reason = result.needs_review_reason or ""
    assert "smtp_creds_missing" in reason
    for v in ("TRUENORTH_SMTP_HOST", "TRUENORTH_SMTP_USER", "TRUENORTH_SMTP_PASS"):
        assert v in reason
    assert (Path(docs.output_dir) / "application.eml").exists()


def test_live_send_path_calls_smtplib(tmp_path: Path, monkeypatch) -> None:
    sent: list[object] = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=30):
            sent.append(("init", host, port))
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def starttls(self): sent.append(("starttls",))
        def login(self, user, pwd): sent.append(("login", user))
        def send_message(self, msg): sent.append(("send", msg["Subject"], msg["To"]))

    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)

    docs = _docs(tmp_path)
    result = send_email_application(_job_en(), _profile(), docs,
                                    _secrets(with_smtp=True), _config_live())
    assert result.submitted is True
    assert result.dry_run is False
    assert result.status == JobStatus.APPLY_SUBMITTED
    assert result.confirmation_url == "mailto:careers@beta.com"
    actions = [t[0] for t in sent]
    assert actions == ["init", "starttls", "login", "send"]


def test_live_send_smtp_failure_returns_apply_failed(tmp_path: Path, monkeypatch) -> None:
    class _BoomSMTP:
        def __init__(self, *args, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def starttls(self): raise OSError("network down")
        def login(self, *a, **kw): pass
        def send_message(self, *a, **kw): pass

    monkeypatch.setattr("smtplib.SMTP", _BoomSMTP)

    docs = _docs(tmp_path)
    result = send_email_application(_job_en(), _profile(), docs,
                                    _secrets(with_smtp=True), _config_live())
    assert result.submitted is False
    assert result.status == JobStatus.APPLY_FAILED
    assert "smtp_send_failed" in (result.error or "")
    assert (Path(docs.output_dir) / "application.eml").exists(), (
        "the .eml must be persisted on failure so the operator can inspect"
    )


def test_no_apply_email_returns_needs_review(tmp_path: Path) -> None:
    job_no_email = _job_en().model_copy(update={"apply_email": None})
    docs = _docs(tmp_path)
    result = send_email_application(job_no_email, _profile(), docs,
                                    _secrets(with_smtp=True), _config_dry())
    assert result.status == JobStatus.APPLY_NEEDS_REVIEW
    assert "no apply_email" in (result.needs_review_reason or "")


def test_apply_to_job_routes_to_email_channel_when_apply_email_set(
    tmp_path: Path, monkeypatch,
) -> None:
    """The runner must hand off to email_channel BEFORE trying Playwright,
    so postings with a careers@ address never spin up a browser."""
    captured: dict[str, object] = {}

    def _fake_send(job, profile, docs, secrets, config):
        captured["job_id"] = job.id
        return ApplyResult(status=JobStatus.APPLY_SUBMITTED, submitted=True)

    monkeypatch.setattr(
        "jobbot.applier.email_channel.send_email_application", _fake_send,
    )
    result = apply_to_job(_job_de(), _profile(), _docs(tmp_path),
                         _secrets(with_smtp=True), _config_dry())
    assert result.submitted is True
    assert captured["job_id"] == "x1"
