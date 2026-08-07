"""Read job-alert emails over IMAP.

This is the sanctioned alternative to crawling boards that forbid it
(bayt.com, freelance.de): the board pushes its own matches to the user's
inbox and we read them there. Nothing is fetched from the board itself.

Deliberately READ-ONLY: the mailbox is selected with readonly=True and no
message is ever flagged, moved or deleted. Re-reading the same alert on the
next pass is harmless because `upsert_new` ignores postings we already know,
so the scan needs no "already processed" bookkeeping.
"""
from __future__ import annotations

import email
import imaplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message

import structlog

from ..config import Secrets

log = structlog.get_logger()


@dataclass
class AlertEmail:
    """One alert message, decoded and flattened for the parsers."""
    sender: str
    subject: str
    received_at: datetime | None
    html: str = ""
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def _part_text(msg: Message) -> tuple[str, str]:
    """Return (html, plain) for a message, walking multipart alternatives."""
    html_chunks: list[str] = []
    text_chunks: list[str] = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/html", "text/plain"):
            continue
        if part.get_filename():
            continue  # attachment, not body
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            continue
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            decoded = payload.decode("utf-8", errors="replace")
        (html_chunks if ctype == "text/html" else text_chunks).append(decoded)
    return "\n".join(html_chunks), "\n".join(text_chunks)


def _received_at(msg: Message) -> datetime | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sender(msg: Message) -> str:
    _, addr = email.utils.parseaddr(msg.get("From") or "")
    return (addr or "").strip().lower()


def connect(secrets: Secrets, mailbox: str = "gmail") -> imaplib.IMAP4_SSL | None:
    """Open an IMAP connection to the chosen mailbox, or None if unconfigured.

    Three mailboxes are supported, because board accounts are not always
    registered to the address the bot already reads:

      "gmail"     - the personal Gmail digest address (default).
      "truenorth" - the outbound business box the outcome scanner reads.
      "alerts"    - a dedicated read-only box (ALERTS_IMAP_* in .env), for
                    boards registered to some other address entirely.
    """
    if mailbox == "truenorth":
        host, port = secrets.truenorth_imap_host, secrets.truenorth_imap_port
        user, password = secrets.truenorth_smtp_user, secrets.truenorth_smtp_pass
    elif mailbox == "alerts":
        host, port = secrets.alerts_imap_host, secrets.alerts_imap_port
        user, password = secrets.alerts_imap_user, secrets.alerts_imap_pass
    else:
        host, port = secrets.imap_host, secrets.imap_port
        user, password = secrets.gmail_address, secrets.gmail_app_password
    if not (user and password and host):
        log.info("alert_scan_skipped_no_creds", mailbox=mailbox)
        return None
    imap = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
    imap.login(user, password)
    return imap


def fetch_alert_emails(
    secrets: Secrets,
    *,
    senders: list[str],
    mailbox: str = "gmail",
    folder: str = "INBOX",
    lookback_days: int = 3,
    limit: int = 200,
) -> list[AlertEmail]:
    """Return alert messages from `senders` seen in the last `lookback_days`.

    `senders` are matched as substrings of the From address, so
    "freelance.de" catches noreply@mail.freelance.de and friends.
    """
    imap = connect(secrets, mailbox)
    if imap is None:
        return []
    out: list[AlertEmail] = []
    try:
        # readonly: never flag the user's mail as read.
        typ, _ = imap.select(folder, readonly=True)
        if typ != "OK":
            log.warning("alert_folder_missing", folder=folder, mailbox=mailbox)
            return []
        since = (datetime.now(tz=timezone.utc) - timedelta(days=lookback_days))
        typ, data = imap.search(None, "SINCE", since.strftime("%d-%b-%Y"))
        uids = (data[0].split() if data and data[0] else [])[-limit:]
        for uid in uids:
            typ, raw = imap.fetch(uid, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            sender = _sender(msg)
            if senders and not any(s.lower() in sender for s in senders):
                continue
            html, text = _part_text(msg)
            out.append(AlertEmail(
                sender=sender,
                subject=_decode(msg.get("Subject")),
                received_at=_received_at(msg),
                html=html,
                text=text,
                headers={"message-id": (msg.get("Message-ID") or "").strip()},
            ))
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass
    log.info("alert_emails_fetched", n=len(out), folder=folder, mailbox=mailbox)
    return out
