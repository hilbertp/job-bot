"""Poll IMAP for an emailed verification code."""
from __future__ import annotations

import email
import imaplib
import re
import time
from email.message import Message

from ..config import Config, Secrets

CODE_RE = re.compile(r"\b(\d{4,8})\b")


class OtpFetcher:
    def __init__(self, secrets: Secrets, config: Config) -> None:
        self.s = secrets
        self.cfg = config.otp

    def wait_for_code(self, sender_domain: str = "") -> str | None:
        """Poll inbox for an unread message from sender_domain. Return first 4-8 digit code."""
        deadline = time.time() + self.cfg.timeout_s
        while time.time() < deadline:
            code = self._scan_once(sender_domain)
            if code:
                return code
            time.sleep(self.cfg.poll_interval_s)
        return None

    def _scan_once(self, sender_domain: str) -> str | None:
        m = imaplib.IMAP4_SSL(self.s.imap_host, self.s.imap_port)
        try:
            m.login(self.s.gmail_address, self.s.gmail_app_password)
            m.select("INBOX")
            criteria = ["UNSEEN"]
            if sender_domain:
                criteria += ["FROM", f'"{sender_domain}"']
            typ, data = m.search(None, *criteria)
            if typ != "OK" or not data or not data[0]:
                return None
            for num in reversed(data[0].split()):
                typ, msg_data = m.fetch(num, "(RFC822)")
                if typ != "OK":
                    continue
                msg: Message = email.message_from_bytes(msg_data[0][1])
                body = self._body(msg)
                hit = CODE_RE.search(body)
                if hit:
                    m.store(num, "+FLAGS", "\\Seen")
                    return hit.group(1)
            return None
        finally:
            try:
                m.logout()
            except Exception:
                pass

    @staticmethod
    def _body(msg: Message) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")
        return (msg.get_payload(decode=True) or b"").decode(errors="ignore")
