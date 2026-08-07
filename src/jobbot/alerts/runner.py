"""Ingest job-alert emails into seen_jobs so they flow through scoring.

Design note, and the reason this module exists at all: bayt.com and
freelance.de forbid crawling, so their postings reach us only through the
alerts they email out themselves. Rows created here must therefore never be
sent back to those boards for a detail fetch. That is enforced by writing
the email body through `update_enrichment(description_scraped=True)` at
ingestion: `jobs_needing_enrichment` only ever selects rows whose body is
missing, so an alert row is invisible to the enrichment queue and no HTTP
request to the board is ever made on its behalf.

The email body is all the text we will ever have for these rows. When it
clears the scorer's 100-word floor the row scores like any scraped posting;
when it does not, the row is still recorded (so the link is not lost) and
counted as `thin` in the summary rather than silently dropped.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from ..config import Config, Secrets
from ..models import JobPosting
from ..scrapers.base import stable_id
from ..state import update_enrichment, upsert_new
from .mailbox import fetch_alert_emails
from .parsers import PROVIDERS, parser_for

log = structlog.get_logger()

# The scorer refuses to judge a posting below this; mirrors
# enrichment.runner._MIN_WORDS so the two cannot drift apart silently.
_MIN_SCORABLE_WORDS = 100


def _sender_list(config: Config) -> list[str]:
    """Every sender substring we are willing to parse."""
    configured = list(getattr(config.alerts, "senders", []) or [])
    if configured:
        return configured
    hints: list[str] = []
    for _source, (_fn, sender_hints) in PROVIDERS.items():
        hints.extend(sender_hints)
    return hints


def scan_alerts(conn, secrets: Secrets, config: Config) -> dict[str, Any]:
    """One ingestion pass. Returns summary counts for the digest/CLI."""
    alerts_cfg = config.alerts
    summary: dict[str, Any] = {
        "emails": 0, "postings": 0, "new": 0, "thin": 0,
        "per_source": {}, "skipped": None,
    }
    if not alerts_cfg.enabled:
        summary["skipped"] = "alerts disabled in config"
        return summary

    emails = fetch_alert_emails(
        secrets,
        senders=_sender_list(config),
        mailbox=alerts_cfg.mailbox,
        folder=alerts_cfg.folder,
        lookback_days=alerts_cfg.lookback_days,
    )
    summary["emails"] = len(emails)
    if not emails:
        return summary

    # Collapse duplicates across emails before touching the DB: the same job
    # appears in every daily alert until it is filled.
    by_key: dict[str, tuple[str, JobPosting, str]] = {}
    for msg in emails:
        source, parse = parser_for(msg.sender)
        try:
            parsed = parse(msg.html, msg.text)
        except Exception:
            log.exception("alert_parse_failed", sender=msg.sender,
                          subject=msg.subject[:80])
            continue
        for item in parsed:
            key = item.dedup_key or item.url
            if key in by_key:
                continue
            job = JobPosting(
                id=stable_id(source, key),
                source=source,
                title=item.title[:200],
                company=item.company or "(see posting)",
                location=item.location,
                url=item.url,
                apply_url=item.url,
                posted_at=item.posted_at or msg.received_at,
                description=item.description[:12000],
                tags=["email_alert"],
            )
            by_key[key] = (source, job, item.description)

    jobs = [job for _source, job, _body in by_key.values()]
    summary["postings"] = len(jobs)
    if not jobs:
        return summary

    new_jobs = upsert_new(conn, jobs)
    summary["new"] = len(new_jobs)
    new_ids = {j.id for j in new_jobs}

    for source, job, body in by_key.values():
        if job.id not in new_ids:
            continue  # already known; body was written on first sight
        word_count = len(body.split())
        scorable = word_count >= _MIN_SCORABLE_WORDS
        if not scorable:
            summary["thin"] += 1
        per_source = summary["per_source"].setdefault(
            source, {"new": 0, "thin": 0})
        per_source["new"] += 1
        per_source["thin"] += 0 if scorable else 1
        # description_scraped=True unconditionally: there is no detail page
        # we are allowed to fetch, so marking it False would park the row in
        # the enrichment retry queue forever for a fetch that must not happen.
        update_enrichment(
            conn,
            job_id=job.id,
            description_full=body[:12000],
            description_scraped=True,
            description_word_count=word_count,
            seniority=None,
            salary_text=None,
            apply_email=None,
            company=job.company,
            posted_at=(job.posted_at.isoformat() if job.posted_at else None),
        )

    log.info("alert_scan_complete", **{k: v for k, v in summary.items()
                                       if k != "per_source"})
    return summary


def scan_alerts_standalone(config: Config, secrets: Secrets) -> dict[str, Any]:
    """CLI entrypoint: open the DB, run one pass, commit."""
    from ..state import connect
    with connect() as conn:
        summary = scan_alerts(conn, secrets, config)
        conn.commit()
    return summary


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
