"""Walk the truenorth.berlin inbox via IMAP, advance proof levels for sent
applications.

PRD §7.8 FR-OUT-03.

Runs once per day from launchd (com.philipp.jobbot.inbox.plist) at 09:30.

Algorithm:
  1. Pull all applications sent in the last 90 days, indexed by company domain.
  2. Connect to IMAP, walk INBOX messages newer than the oldest application.
  3. For each message:
       a. Detect bounce: From contains mailer-daemon / postmaster, or
          subject contains "Undelivered" / "Mail Delivery Failure".
          → If matches a sent application's recipient, do NOT advance L2 for it.
            (Track bounced ids so step 4 doesn't promote them.)
       b. Detect human reply: From's domain matches the company domain of one
          of our sent applications, sender is not a no-reply.
          → advance to L3.
       c. Run classifier on the message body (see classifier.py):
          → "interview" intent advances to L4.
          → "rejection" intent advances to L5 (and triggers snooze).
  4. After the walk, for any L1 application sent ≥ 24h ago that did NOT bounce,
     advance to L2.

Be polite to IMAP: read-only mode, batched fetches, mark messages \\Seen only
when they affect a known application.
"""
from __future__ import annotations

from datetime import timedelta

from ..config import Config, Secrets

LOOKBACK_DAYS = 90
NO_BOUNCE_GRACE = timedelta(hours=24)


def scan_inbox(conn, secrets: Secrets, config: Config) -> dict:
    """Run one inbox-scan pass. Return summary counts for the digest."""
    raise NotImplementedError("Copilot to implement per module docstring")
