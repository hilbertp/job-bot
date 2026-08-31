"""Every mail socket must carry a deadline.

Run 451 opened an SMTP connection to Gmail on 2026-08-30 at 09:09 UTC and
sat in ESTABLISHED for 25 hours: 6 seconds of CPU across a day. The digest
send in `notify.email._send` had no `timeout=`, so the socket never gave
up. Because the send happens inside the single-run lock, every scheduled
run behind it was skipped, and the dashboard could only tell the operator
to kill the process by hand.

The digest call site is already wrapped in try/except, so a timeout is all
that was ever needed to turn a wedged pipeline into one logged error.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from jobbot.config import Secrets
from jobbot.notify import email as notify_email

SRC = Path(__file__).resolve().parents[1] / "src" / "jobbot"

#: Constructors that open a network socket to a mail server.
MAIL_CONSTRUCTORS = {"SMTP", "SMTP_SSL", "IMAP4", "IMAP4_SSL"}


def _secrets() -> Secrets:
    return Secrets(anthropic_api_key="x", gmail_address="a@b.test",
                   gmail_app_password="pw", notify_to="a@b.test")


def _mail_calls_without_timeout(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name not in MAIL_CONSTRUCTORS:
            continue
        if not any(kw.arg == "timeout" for kw in node.keywords):
            offenders.append(f"{path.name}:{node.lineno} {name}(...)")
    return offenders


def test_no_mail_socket_is_opened_without_a_timeout():
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        offenders.extend(_mail_calls_without_timeout(path))
    assert not offenders, (
        "mail sockets without a timeout will wedge the run that opens them: "
        + "; ".join(offenders))


def test_digest_send_passes_the_timeout_to_smtp(monkeypatch):
    seen: dict = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None, **kw):
            seen.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            seen["sent"] = True

    monkeypatch.setattr(notify_email.smtplib, "SMTP", _FakeSMTP)
    notify_email._send(_secrets(), "subject", "<p>body</p>")

    assert seen.get("sent") is True
    assert seen["timeout"] == notify_email.MAIL_TIMEOUT_S
    assert seen["timeout"] and seen["timeout"] > 0


def test_mail_timeout_is_shorter_than_the_stuck_run_threshold():
    """A hung notification must be reported as an error long before the
    dashboard would call the whole run stuck."""
    from jobbot.pipeline import STUCK_RUN_AFTER_H

    assert notify_email.MAIL_TIMEOUT_S < STUCK_RUN_AFTER_H * 3600


def test_digest_failure_does_not_abort_the_run():
    """The guard that makes the timeout sufficient: the digest call site
    catches, logs and records the error instead of propagating."""
    src = (SRC / "pipeline.py").read_text()
    block = re.search(r"send_digest\(secrets, matches, errors, started,"
                      r".*?except Exception as e:", src, re.S)
    assert block, "send_digest call site changed; re-verify it is guarded"
