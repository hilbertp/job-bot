"""Walk the truenorth.berlin IMAP inbox, advance dashboard cards.

PRD §7.8 FR-OUT-03.

Two passes:

1. **IMAP walk** — connect to TRUENORTH_IMAP_HOST with TRUENORTH_SMTP_USER/PASS
   (same creds work on IONOS). For each UNREAD message in INBOX, classify:

      bounce        → flips the matching application to apply_failed
      auto-reply    → advances proof to L2 ("received")
      interview     → advances proof to L4
      rejection     → advances proof to L5
      human reply   → advances proof to L3 (when sender domain matches a
                       company we applied to)

   Each successful match calls `state.transition_application` so the
   Outbound Pipeline panel auto-refreshes the card without operator
   intervention. Messages we successfully matched are marked \\Seen;
   anything else stays unread for the human to handle.

2. **No-bounce-24h pass** — any L1 application sent ≥24h ago that did
   NOT bounce in pass 1 gets advanced to L2 ("no bounce detected").

The scanner is read-only-friendly: when TRUENORTH_SMTP_* creds are
missing, pass 1 is skipped (graceful no-op) and only pass 2 runs.
"""
from __future__ import annotations

import email
import imaplib
import re
import ssl
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message

import structlog

from ..config import Config, Secrets
from ..state import transition_application
from .classifier import classify_message
from .proof_ladder import ProofLevel, advance_proof_level

log = structlog.get_logger()

LOOKBACK_DAYS = 90
NO_BOUNCE_GRACE = timedelta(hours=24)


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


# Bounce / auto-reply detection — kept as compiled regexes so the scanner
# stays cheap on inboxes with hundreds of messages.
_BOUNCE_FROM_RE = re.compile(
    r"(mailer-daemon|postmaster|mail.?delivery|mail.?delivery.subsystem|"
    r"failure-?notice|mailer)@",
    re.IGNORECASE,
)
_BOUNCE_SUBJECT_RE = re.compile(
    r"(undelivered|undeliverable|delivery (?:failed|failure|status|notification)|"
    r"returned (?:mail|message)|mail delivery failed|unzustellbar|"
    r"konnte nicht zugestellt werden|absender unbekannt|"
    r"mail.?delivery.?failed|delivery.+rejected)",
    re.IGNORECASE,
)
# Auto-reply: many providers tag headers, some only the subject.
_AUTOREPLY_SUBJECT_RE = re.compile(
    r"(automatic reply|auto[- ]?reply|out of office|abwesenheit|"
    r"eingangsbest[äa]tigung|empfangsbest[äa]tigung|bewerbungseingang|"
    r"wir haben (?:ihre |deine )?(?:bewerbung|nachricht|anfrage) erhalten|"
    r"thank you for (?:your )?application|application received|"
    r"vielen dank f[üu]r (?:ihre|deine|dein) bewerbung)",
    re.IGNORECASE,
)
_AUTOREPLY_HEADERS = (
    "auto-submitted", "x-autoreply", "x-auto-response-suppress",
    "x-autorespond", "precedence",
)
# Extract email addresses from arbitrary text (used to pull the failed
# recipient out of a bounce body).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _body_text(msg: Message) -> str:
    """Return the message body as a flat string (concatenate text/plain
    parts, fall back to decoded payload)."""
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    chunks.append(payload.decode(
                        part.get_content_charset() or "utf-8",
                        errors="replace",
                    ))
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            chunks.append(payload.decode(
                msg.get_content_charset() or "utf-8",
                errors="replace",
            ))
        except Exception:
            pass
    return "\n".join(chunks)


def _is_auto_reply(msg: Message, subject: str) -> bool:
    """Heuristic: header tags OR subject pattern."""
    for h in _AUTOREPLY_HEADERS:
        val = (msg.get(h) or "").lower()
        if val and val not in ("", "bulk"):
            if h == "precedence" and val == "list":
                continue  # mailing-list traffic, not auto-reply
            if "auto" in val or h != "precedence":
                return True
    return bool(_AUTOREPLY_SUBJECT_RE.search(subject))


def _is_bounce(msg: Message, subject: str) -> bool:
    from_hdr = (msg.get("From") or "").lower()
    if _BOUNCE_FROM_RE.search(from_hdr):
        return True
    return bool(_BOUNCE_SUBJECT_RE.search(subject))


def _match_application(
    msg: Message, body: str, subject: str,
    sent_by_email: dict[str, str], sent_by_domain: dict[str, list[str]],
) -> tuple[str | None, str]:
    """Match an inbound message to a sent application.

    Returns (job_id, matcher_kind). matcher_kind is one of "bounce_target",
    "sender_email", "sender_domain", or "" if no match.

    Match priority:
      1. Bounce body contains a recipient we applied to.
      2. Sender's full address is one we applied to (the recruiter
         replying from the same address).
      3. Sender's domain matches a company we applied to.
    """
    # 1. Bounce: scan body for any of our outbound recipients
    if _is_bounce(msg, subject):
        for addr in _EMAIL_RE.findall(body):
            jid = sent_by_email.get(addr.lower())
            if jid:
                return jid, "bounce_target"

    # 2. Sender's full address
    sender = _decode(msg.get("From"))
    sender_addrs = _EMAIL_RE.findall(sender)
    for addr in sender_addrs:
        jid = sent_by_email.get(addr.lower())
        if jid:
            return jid, "sender_email"

    # 3. Sender's domain
    for addr in sender_addrs:
        domain = addr.split("@", 1)[-1].lower()
        candidates = sent_by_domain.get(domain) or []
        if len(candidates) == 1:
            return candidates[0], "sender_domain"
        # If multiple sent applications share a domain, we can't
        # disambiguate without more signal — skip rather than guess.

    return None, ""


def _classify_and_transition(
    conn, job_id: str, msg: Message, subject: str, body: str,
    matcher_kind: str,
) -> tuple[str, bool]:
    """Run the classifier + advance the dashboard card. Returns
    (new_state, changed) where changed=True means proof level moved."""
    sender = _decode(msg.get("From")) or "unknown"

    # Bounce wins regardless of body content.
    if matcher_kind == "bounce_target":
        transition_application(
            conn, job_id, new_state="bounced",
            note=f"Bounce from {sender}: {subject[:80]}",
        )
        return "bounced", True

    # Auto-reply detection: marker headers OR subject pattern.
    if _is_auto_reply(msg, subject):
        transition_application(
            conn, job_id, new_state="received",
            note=f"Auto-reply from {sender}: {subject[:80]}",
        )
        return "received", True

    # Otherwise: classify as interview / rejection / other (human reply).
    intent, conf, evidence_quote = classify_message(subject, body)
    if intent == "interview" and conf >= 0.7:
        transition_application(
            conn, job_id, new_state="interview",
            note=f"Interview signal from {sender}: {evidence_quote[:80]}",
        )
        return "interview", True
    if intent == "rejection" and conf >= 0.7:
        transition_application(
            conn, job_id, new_state="rejected",
            note=f"Rejection from {sender}: {evidence_quote[:80]}",
        )
        return "rejected", True

    # Plain human reply (sender's domain matched but no interview /
    # rejection markers): advance to L3 ("replied").
    transition_application(
        conn, job_id, new_state="replied",
        note=f"Reply from {sender}: {subject[:80]}",
    )
    return "replied", True


def _imap_connect(secrets: Secrets) -> imaplib.IMAP4_SSL | None:
    """Open an IMAP connection or return None when creds are missing."""
    if not (secrets.truenorth_smtp_user and secrets.truenorth_smtp_pass):
        log.info("inbox_scan_skipped_no_creds")
        return None
    ctx = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(
        secrets.truenorth_imap_host, secrets.truenorth_imap_port,
        ssl_context=ctx,
    )
    imap.login(secrets.truenorth_smtp_user, secrets.truenorth_smtp_pass)
    return imap


def scan_inbox(conn, secrets: Secrets, config: Config) -> dict:
    """Run one inbox-scan pass. Returns summary counts for the digest."""
    since_dt = datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_iso = since_dt.isoformat()
    no_bounce_cutoff = (
        datetime.now(tz=timezone.utc) - NO_BOUNCE_GRACE
    ).isoformat()

    counts = {
        "checked": 0, "imap_messages": 0, "matched": 0,
        "bounces": 0, "auto_replies": 0, "human_replies": 0,
        "interviews": 0, "rejections": 0,
        "advanced_waiting": 0,
    }

    # Build lookups of submitted applications by recipient + by domain.
    apps = conn.execute("""
        SELECT a.job_id, a.attempted_at, s.apply_email
        FROM applications a JOIN seen_jobs s ON s.id = a.job_id
        WHERE a.submitted = 1 AND a.attempted_at >= ?
    """, (since_iso,)).fetchall()
    counts["checked"] = len(apps)

    sent_by_email: dict[str, str] = {}
    sent_by_domain: dict[str, list[str]] = {}
    for a in apps:
        addr = (a["apply_email"] or "").strip().lower()
        if not addr or "@" not in addr:
            continue
        sent_by_email[addr] = a["job_id"]
        sent_by_domain.setdefault(addr.split("@", 1)[-1], []).append(a["job_id"])

    # Pass 1 — IMAP walk
    bounced_ids: set[str] = set()
    matched_ids: set[str] = set()
    imap = _imap_connect(secrets)
    if imap is not None:
        try:
            imap.select("INBOX", readonly=False)
            # Walk every UNREAD message since the oldest still-pending app.
            search_since = since_dt.strftime("%d-%b-%Y")
            typ, data = imap.search(None, "UNSEEN", "SINCE", search_since)
            uids = data[0].split() if data and data[0] else []
            counts["imap_messages"] = len(uids)
            for uid in uids:
                typ, raw = imap.fetch(uid, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = email.message_from_bytes(raw[0][1])
                subject = _decode(msg.get("Subject"))
                body = _body_text(msg)
                job_id, kind = _match_application(
                    msg, body, subject, sent_by_email, sent_by_domain,
                )
                if not job_id:
                    continue
                new_state, changed = _classify_and_transition(
                    conn, job_id, msg, subject, body, kind,
                )
                if not changed:
                    continue
                matched_ids.add(job_id)
                if new_state == "bounced":
                    bounced_ids.add(job_id)
                    counts["bounces"] += 1
                elif new_state == "received":
                    counts["auto_replies"] += 1
                elif new_state == "interview":
                    counts["interviews"] += 1
                elif new_state == "rejected":
                    counts["rejections"] += 1
                elif new_state == "replied":
                    counts["human_replies"] += 1
                # Mark as Seen — we only flag what we matched, leaving
                # the rest of the inbox untouched for the human.
                try:
                    imap.store(uid, "+FLAGS", "\\Seen")
                except Exception:
                    pass
            counts["matched"] = len(matched_ids)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    # Pass 2 — advance L1 apps older than 24h that did NOT bounce.
    waiting_candidates = conn.execute(
        "SELECT job_id FROM applications "
        "WHERE submitted = 1 "
        "  AND attempted_at <= ? "
        "  AND COALESCE(proof_level, 0) < ? "
        "  AND COALESCE(proof_level, 0) >= 1",
        (no_bounce_cutoff, int(ProofLevel.NO_BOUNCE_24H)),
    ).fetchall()
    for row in waiting_candidates:
        if row["job_id"] in bounced_ids:
            continue
        if advance_proof_level(
            conn, row["job_id"], ProofLevel.NO_BOUNCE_24H,
            {"source": "inbox", "evidence": "no bounce detected after 24h"},
        ):
            counts["advanced_waiting"] += 1

    log.info("inbox_scan_complete", **counts)
    return counts
