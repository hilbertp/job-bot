"""Gmail SMTP digest + failure alerts."""
from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import REPO_ROOT, Secrets

TEMPLATES = REPO_ROOT / "src" / "jobbot" / "notify" / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html"]),
)


def _send(secrets: Secrets, subject: str, html: str, attachments: list[Path] | None = None) -> None:
    msg = EmailMessage()
    msg["From"] = secrets.gmail_address
    msg["To"] = secrets.notify_to
    msg["Subject"] = subject
    msg.set_content("This message is HTML-only, please view in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    for path in attachments or []:
        if not path.exists():
            continue
        data = path.read_bytes()
        maintype, _, subtype = (path.suffix.lstrip(".") or "octet-stream").partition("/")
        msg.add_attachment(data, maintype="application",
                           subtype=subtype or "octet-stream", filename=path.name)

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(secrets.gmail_address, secrets.gmail_app_password.replace(" ", ""))
        s.send_message(msg)


def send_digest(secrets: Secrets, matches: list[dict], errors: list[dict],
                run_started: datetime,
                cannot_score: list[dict] | None = None) -> None:
    """matches:      [{job, score, reason, output_dir, apply_status, apply_screenshot, cover_letter_html}]
    errors:        [{source, error}]
    cannot_score:  [{job, status, reason}], PRD §7.5 FR-SCO-01 refusal rows."""
    tmpl = _env.get_template("digest.html.j2")
    html = tmpl.render(
        matches=matches, errors=errors, run_started=run_started, n=len(matches),
        cannot_score=cannot_score or [],
    )
    subject = f"jobbot · {len(matches)} new match{'es' if len(matches) != 1 else ''}"
    if cannot_score:
        subject += f" · {len(cannot_score)} cannot_score"
    if errors:
        subject += f" · {len(errors)} error{'s' if len(errors) != 1 else ''}"
    _send(secrets, subject, html)


def send_failure_alert(secrets: Secrets, message: str, traceback: str) -> None:
    tmpl = _env.get_template("failure.html.j2")
    html = tmpl.render(message=message, traceback=traceback,
                       at=datetime.utcnow().isoformat())
    _send(secrets, "jobbot · run failed", html)
