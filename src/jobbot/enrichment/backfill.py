"""Backfill body text for rows scraped before enrichment was wired in,
or that came back below the 200-word scoring floor.

PRD §7.3 FR-ENR-04 + §7.5 FR-SCO-01.

The pipeline's `enrich_new_postings` runs once per posting at scrape time
and treats any miss as a hard "no_body". A long tail of pre-enrichment
rows therefore sits permanently at `cannot_score:no_body`. This module
exists to drain that tail: it re-targets the same scrapers' fetch_detail
hooks but applies different failure semantics — a transient fetch failure
leaves the row untouched so the next backfill run can retry.

Differences from `enrichment.runner.enrich_new_postings`:
  - Failure (exception, None, captcha-shaped body) LEAVES the row alone
    and logs URL + error to stderr. The pipeline's runner would mark
    description_scraped=False, locking the row at no_body forever.
  - freelance_de has no fetch_detail at all. Rows from that source are
    marked `cannot_score:source_unsupported` and skipped, since no future
    run can ever succeed without a code change.
  - Explicit 1-req-per-second-per-source rate limit, layered on top of
    whatever the scraper does internally. This keeps polite spacing
    consistent across a long-tail backfill where the scraper's per-call
    sleep is the only throttle.
  - `--dry-run` reports what would happen without writing.
  - `--source <name>` restricts the run to one scraper for debugging.
"""
from __future__ import annotations

import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import structlog

from ..models import JobPosting, JobStatus
from ..state import update_enrichment, update_status
from .email_extractor import extract_apply_email

log = structlog.get_logger()

# Per-source minimum spacing between fetch_detail calls. 1s is the boring
# floor the scrapers already aim for; this layer guarantees it for the
# backfill path regardless of what the scraper does internally.
_MIN_INTERVAL_S = 1.0

# Sources with no fetch_detail. A backfill row from one of these can
# never be enriched, so terminal-mark and skip instead of retrying.
UNSUPPORTED_SOURCES: frozenset[str] = frozenset({"freelance_de"})

# Match runner.py: a fetched body needs >=100 words before we call it
# "description_scraped=True". Anything shorter is almost always a
# captcha page or login wall.
_MIN_REAL_BODY_WORDS = 100

_SENIORITY_RE = re.compile(
    r"\b(intern|junior|mid|senior|lead|principal|staff|head)\b", re.IGNORECASE
)
_SALARY_RE = re.compile(
    r"(?:€\s?\d+[\d.,kK-]*|\b\d+\s?[kK]\b|\b\d{2,3}\s?[-–]\s?\d{2,3}\s?[kK]\b)"
)


@dataclass
class BackfillReport:
    n_attempted: int = 0
    n_enriched: int = 0          # body fetched and persisted
    n_failed: int = 0            # exception / None / too short — row untouched
    n_unsupported: int = 0       # source has no fetch_detail — terminal mark
    n_skipped_filter: int = 0    # filtered out by --source
    per_source_success: Counter = field(default_factory=Counter)
    per_source_failure: Counter = field(default_factory=Counter)


class _PerSourceRateLimiter:
    """Hold the wall-clock time of the last call per source and sleep up
    to `_MIN_INTERVAL_S` before the next one. Stateless across runs."""

    def __init__(self, sleep=time.sleep, monotonic=time.monotonic) -> None:
        self._last: dict[str, float] = {}
        self._sleep = sleep
        self._monotonic = monotonic

    def wait(self, source: str) -> None:
        last = self._last.get(source)
        now = self._monotonic()
        if last is not None:
            delta = now - last
            if delta < _MIN_INTERVAL_S:
                self._sleep(_MIN_INTERVAL_S - delta)
        self._last[source] = self._monotonic()


def _persist_enrichment(
    conn,
    job: JobPosting,
    description: str,
    word_count: int,
) -> None:
    salary_match = _SALARY_RE.search(description)
    seniority_match = _SENIORITY_RE.search(f"{job.title} {description}")
    apply_email = extract_apply_email(description)
    update_enrichment(
        conn,
        job_id=job.id,
        description_full=description,
        description_scraped=True,
        description_word_count=word_count,
        seniority=seniority_match.group(1).lower() if seniority_match else None,
        salary_text=salary_match.group(0) if salary_match else None,
        apply_email=apply_email,
    )


def run_backfill(
    jobs: list[JobPosting],
    conn,
    registry: dict,
    *,
    dry_run: bool = False,
    source: str | None = None,
    rate_limiter: _PerSourceRateLimiter | None = None,
) -> BackfillReport:
    """Walk `jobs`, attempt fetch_detail per source, persist or skip.

    `source` (optional): restrict to one scraper key (e.g. "linkedin").
    Rows from other sources are counted in `n_skipped_filter` and not
    touched.

    `dry_run`: log intent but do not call update_enrichment or
    update_status. The rate limiter is still exercised so dry-run timing
    matches a real run.
    """
    report = BackfillReport()
    limiter = rate_limiter or _PerSourceRateLimiter()

    for job in jobs:
        if source is not None and job.source != source:
            report.n_skipped_filter += 1
            continue

        report.n_attempted += 1

        if job.source in UNSUPPORTED_SOURCES:
            report.n_unsupported += 1
            print(
                f"[backfill] unsupported source: {job.source} {job.id} "
                f"{job.url} — marking cannot_score:source_unsupported",
                file=sys.stderr,
            )
            if not dry_run:
                update_status(
                    conn, job.id, JobStatus.CANNOT_SCORE_SOURCE_UNSUPPORTED,
                    reason=f"source {job.source} has no fetch_detail",
                )
            continue

        scraper = registry.get(job.source)
        fetch_detail = getattr(scraper, "fetch_detail", None) if scraper else None
        if not callable(fetch_detail):
            # Source registered but no fetch_detail — treat like unsupported.
            report.n_unsupported += 1
            print(
                f"[backfill] no fetch_detail on registry[{job.source!r}] "
                f"for {job.id} {job.url}",
                file=sys.stderr,
            )
            if not dry_run:
                update_status(
                    conn, job.id, JobStatus.CANNOT_SCORE_SOURCE_UNSUPPORTED,
                    reason=f"source {job.source} has no fetch_detail",
                )
            continue

        limiter.wait(job.source)

        if dry_run:
            print(
                f"[backfill] DRY-RUN would fetch_detail({job.source}) "
                f"{job.id} {job.url}",
                file=sys.stderr,
            )
            report.n_enriched += 1
            report.per_source_success[job.source] += 1
            continue

        try:
            enriched = fetch_detail(job)
        except Exception as exc:
            print(
                f"[backfill] fetch_detail FAILED {job.source} {job.id} "
                f"{job.url} — {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            log.warning(
                "backfill_fetch_detail_exception",
                job_id=job.id, source=job.source, url=str(job.url),
                error=str(exc),
            )
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            continue

        if enriched is None:
            print(
                f"[backfill] fetch_detail returned None {job.source} "
                f"{job.id} {job.url} — row untouched",
                file=sys.stderr,
            )
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            continue

        text = (enriched.description or "").strip()
        word_count = len(text.split())
        if word_count < _MIN_REAL_BODY_WORDS:
            print(
                f"[backfill] fetch_detail body too short ({word_count} words) "
                f"{job.source} {job.id} {job.url} — row untouched",
                file=sys.stderr,
            )
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            continue

        _persist_enrichment(conn, job, text, word_count)
        report.n_enriched += 1
        report.per_source_success[job.source] += 1

    log.info(
        "backfill_complete",
        n_attempted=report.n_attempted,
        n_enriched=report.n_enriched,
        n_failed=report.n_failed,
        n_unsupported=report.n_unsupported,
        n_skipped_filter=report.n_skipped_filter,
        dry_run=dry_run,
    )
    return report
