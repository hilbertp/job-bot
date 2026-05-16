"""Housekeeping: detect and mark stale listings.

Runs the same HEAD pre-flight the apply runner uses, but across every
live shortlist row instead of one job at a time. The point is to catch
roles that the employer pulled between scoring and apply BEFORE the user
clicks "apply" on a dead link or the runner wastes a Chromium launch.

Surfaced two ways:
  - `jobbot housekeep [--dry-run]` from the CLI, an explicit audit.
  - Pipeline integration in `pipeline.run_once` runs the audit after
    scoring so stale rows are demoted before Stage 3 generation.

Marks rows `listing_expired` (yellow pill in the dashboard) with a
`discard_reason` that names the signal that fired.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sqlite3
from dataclasses import dataclass

import httpx

from .expiry import is_expired_listing
from .models import TERMINAL_STATUSES, JobStatus
from .state import update_status


# How many HEAD probes to run concurrently. Conservative default, jobs
# boards often share infrastructure (Greenhouse, Lever) so a too-high
# parallel count looks like a probe storm to them.
_PROBE_CONCURRENCY = 10

# How long we'll wait for a HEAD response per row before giving up. A
# slow site does not mean the listing is dead; we treat timeouts as
# "unknown" and leave the row alone.
_PROBE_TIMEOUT_SEC = 10


@dataclass
class HousekeepReport:
    scanned: int
    marked_expired: int
    skipped_email_apply: int
    skipped_no_url: int
    network_errors: int
    expired_rows: list[dict]
    error_rows: list[dict]


def _resolve_apply_url(row: sqlite3.Row) -> str | None:
    raw_json = row["raw_json"]
    if raw_json:
        try:
            raw = json.loads(raw_json)
            return raw.get("apply_url") or row["url"]
        except json.JSONDecodeError:
            pass
    return row["url"]


def _probe_one(
    row: sqlite3.Row,
) -> tuple[sqlite3.Row, str | None, int | None, str | None, bool, str]:
    """HEAD-probe one row's apply URL.

    Returns (row, url, status_code, final_url, is_expired, reason).
    reason values worth caring about:
      - "" (live)
      - "email_apply" / "no_url" (skipped, not probed)
      - "net_err: ..." (probe failed, leave row alone)
      - "<expiry reason>" when is_expired=True
    """
    if row["apply_email"]:
        return row, None, None, None, False, "email_apply"
    url = _resolve_apply_url(row)
    if not url:
        return row, None, None, None, False, "no_url"
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=_PROBE_TIMEOUT_SEC,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as c:
            r = c.head(url)
        expired, reason = is_expired_listing(str(r.url), r.status_code)
        return row, url, r.status_code, str(r.url), expired, reason
    except httpx.HTTPError as e:
        return row, url, None, None, False, f"net_err: {type(e).__name__}"


def housekeep_shortlist(
    conn: sqlite3.Connection,
    *,
    min_score: int = 70,
    dry_run: bool = False,
) -> HousekeepReport:
    """Scan live shortlist rows (score >= min_score, non-terminal status)
    and mark anything whose apply URL no longer resolves as
    `listing_expired`.

    When `dry_run=True`, returns the same report but skips the UPDATE.
    """
    terminal_placeholders = ",".join("?" * len(TERMINAL_STATUSES))
    rows = conn.execute(
        f"""
        SELECT id, title, company, source, status, score, score_tailored,
               url, apply_email, raw_json
        FROM seen_jobs
        WHERE score IS NOT NULL AND score >= ?
          AND status NOT IN ({terminal_placeholders})
        ORDER BY score_tailored DESC NULLS LAST, score DESC
        """,
        (min_score, *TERMINAL_STATUSES),
    ).fetchall()

    results = []
    if rows:
        with cf.ThreadPoolExecutor(max_workers=_PROBE_CONCURRENCY) as ex:
            for r in ex.map(_probe_one, rows):
                results.append(r)

    expired_rows: list[dict] = []
    error_rows: list[dict] = []
    n_marked = n_email = n_no_url = n_err = 0
    for row, url, status_code, final_url, expired, reason in results:
        if reason == "email_apply":
            n_email += 1
            continue
        if reason == "no_url":
            n_no_url += 1
            continue
        if reason.startswith("net_err"):
            n_err += 1
            error_rows.append({
                "id": row["id"], "title": row["title"], "company": row["company"],
                "url": url, "error": reason,
            })
            continue
        if expired:
            n_marked += 1
            expired_rows.append({
                "id": row["id"],
                "title": row["title"],
                "company": row["company"],
                "source": row["source"],
                "score": row["score"],
                "score_tailored": row["score_tailored"],
                "url": url,
                "final_url": final_url,
                "status_code": status_code,
                "reason": reason,
            })
            if not dry_run:
                update_status(
                    conn, row["id"], JobStatus.LISTING_EXPIRED,
                    discard_reason=f"housekeep: {reason}",
                )
    return HousekeepReport(
        scanned=len(rows),
        marked_expired=n_marked,
        skipped_email_apply=n_email,
        skipped_no_url=n_no_url,
        network_errors=n_err,
        expired_rows=expired_rows,
        error_rows=error_rows,
    )
