"""Orchestrate detail-page fetches across all scrapers.

PRD §7.3 FR-ENR-01..04.

Public entrypoint:
    enrich_new_postings(jobs: list[JobPosting], conn) -> EnrichmentReport

Behavior per posting:
  - Look up the scraper from REGISTRY by `job.source`.
  - If the scraper has a `fetch_detail` method, call it.
  - If it returns a JobPosting with non-empty `description`:
      compute word_count, run email extractor, run light regex for
      seniority hints (Senior/Junior/Lead/Principal in title or body) and
      salary (€\\d+, \\d+k, etc.).
  - Persist all of the above to seen_jobs via state.update_enrichment(...).
  - On failure / short body / no fetch_detail: mark description_scraped = False
    and continue.

The runner accumulates per-source success/failure counts so the digest can
display body-fetch health.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import structlog

from ..models import JobPosting, JobStatus
from ..scrapers import REGISTRY
from ..scrapers.base import ListingGone
from ..state import (
    increment_fetch_attempts, update_enrichment, update_run_stage_progress,
    update_status,
)
from .email_extractor import extract_apply_email

log = structlog.get_logger()

_SENIORITY_RE = re.compile(r"\b(intern|junior|mid|senior|lead|principal|staff|head)\b", re.IGNORECASE)
_SALARY_RE = re.compile(r"(?:€\s?\d+[\d.,kK-]*|\b\d+\s?[kK]\b|\b\d{2,3}\s?[-–]\s?\d{2,3}\s?[kK]\b)")
_MIN_WORDS = 100
# Give up on a row after this many failed detail fetches across runs.
# One failure is a rate limit or a hiccup; three, on three separate runs,
# is a page that is not coming back.
_MAX_FETCH_ATTEMPTS = 3


@dataclass
class EnrichmentReport:
    n_attempted: int = 0
    n_succeeded: int = 0
    n_failed: int = 0
    # Permanently closed rows: walled/disabled sources and rows that hit
    # the failed-fetch cap. Not failures (nothing is retried), not successes.
    n_walled: int = 0
    n_gave_up: int = 0
    # Rows whose source told us the posting is gone. Counted apart from
    # n_failed because they are a clean outcome, not a fetch problem, and
    # they will never be retried.
    n_expired: int = 0
    per_source_success: Counter = field(default_factory=Counter)
    per_source_failure: Counter = field(default_factory=Counter)
    enriched_jobs: list[JobPosting] = field(default_factory=list)


def _give_up_if_capped(conn, job: JobPosting, report: EnrichmentReport,
                       stage_meta: dict) -> None:
    """Count a failed fetch; retire the row for good once the cap is hit.

    Called from every transient-failure branch. Keeps genuinely flaky rows
    retryable (attempt 1..cap-1) while dead pages on otherwise healthy
    boards stop poisoning the retry queue after `_MAX_FETCH_ATTEMPTS` runs.
    """
    attempts = increment_fetch_attempts(conn, job.id)
    if attempts < _MAX_FETCH_ATTEMPTS:
        return
    why = f"gave up after {attempts} failed detail fetches"
    log.info("enrichment_gave_up", job_id=job.id, source=job.source,
             attempts=attempts)
    update_status(conn, job.id, JobStatus.UNFETCHABLE,
                  reason=why, discard_reason=f"unfetchable: {why}")
    report.n_gave_up += 1
    stage_meta["gave_up"] = report.n_gave_up


def enrich_new_postings(
    jobs: list[JobPosting],
    conn,
    registry: dict[str, object] | None = None,
    *,
    run_id: int | None = None,
    config=None,
    secrets=None,
    stage_metadata: dict | None = None,
) -> EnrichmentReport:
    """Walk new jobs, call each scraper's fetch_detail, persist enrichment cols.

    When `config.apply_research_enabled` and `secrets` are provided, rows
    whose only apply link is a paywalled aggregator get a web-search pass
    to resolve the canonical employer apply URL (bounded by
    `config.apply_research_max_per_run`, results cached per company+title
    within the run).

    `stage_metadata` (e.g. the caller's scrape→fetch funnel counts) is merged
    into the stage's progress metadata, and per-source failure counts are
    added live under `fail_by_source` so the dashboard can say WHICH boards
    are failing while the stage runs, not just how many rows did.

    Returns counts suitable for the digest's per-source health table.
    """
    report = EnrichmentReport()

    scraper_registry = REGISTRY if registry is None else registry
    # Apply-path research bookkeeping.
    research_enabled = bool(
        getattr(config, "apply_research_enabled", False) and secrets is not None
    )
    research_cap = int(getattr(config, "apply_research_max_per_run", 0) or 0)
    n_researched = 0
    research_cache: dict[tuple[str, str], str | None] = {}
    log.info("enrichment_starting", n_jobs=len(jobs), n_scrapers=len(scraper_registry))
    # One dict mutated in place; every metadata= write snapshots it whole.
    stage_meta: dict = {
        "stage_started_at": datetime.now(timezone.utc).isoformat(),
        **(stage_metadata or {}),
    }
    if run_id is not None:
        update_run_stage_progress(
            conn, run_id, "enrichment",
            total=len(jobs), started=0, completed=0, failed=0, skipped=0,
            current_index=0, current_item_id=None, current_label=None,
            metadata=stage_meta,
        )

    for idx, job in enumerate(jobs, start=1):
        report.n_attempted += 1
        if run_id is not None:
            update_run_stage_progress(
                conn, run_id, "enrichment",
                total=len(jobs), started=idx, current_index=idx,
                current_item_id=job.id,
                current_label=f"{job.title} @ {job.company} ({job.source})",
            )
        scraper = scraper_registry.get(job.source)
        fetch_detail = getattr(scraper, "fetch_detail", None) if scraper is not None else None

        # Permanent no-gos, resolved WITHOUT an HTTP request: the board
        # walls its detail pages (login/paywall), or the source is disabled
        # in config (e.g. robots.txt compliance). Marking the row
        # unfetchable (terminal) takes it out of the retry queue for good.
        # NOTE: a missing fetch_detail is NOT in this set — such rows are
        # scored from their card body below, and the attempt cap retires
        # the ones that never make it.
        walled = getattr(scraper, "detail_walled", None) if scraper is not None else None
        src_cfg = getattr(config, "sources", None) or {}
        source_disabled = (
            job.source in src_cfg and not getattr(src_cfg[job.source], "enabled", True)
        )
        if walled or source_disabled:
            why = walled or "source disabled in config"
            log.info("enrichment_unfetchable", job_id=job.id, source=job.source,
                     reason=why)
            update_status(conn, job.id, JobStatus.UNFETCHABLE,
                          reason=why, discard_reason=f"unfetchable: {why}")
            report.n_walled += 1
            walled_by_source = stage_meta.setdefault("walled_by_source", {})
            walled_by_source[job.source] = walled_by_source.get(job.source, 0) + 1
            stage_meta.setdefault("walled_reasons", {})[job.source] = why
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                    skipped=report.n_expired + report.n_walled,
                    metadata=stage_meta,
                )
            continue

        if not callable(fetch_detail):
            # No fetcher for this source: persist the card body so scoring
            # can still work from it (description_scraped stays False), and
            # let the attempt cap retire rows that never reach a score.
            log.warning("enrichment_no_fetch_detail", job_id=job.id, source=job.source)
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            stage_meta["fail_by_source"] = dict(report.per_source_failure)
            update_enrichment(
                conn,
                job_id=job.id,
                description_full=job.description or "",
                description_scraped=False,
                description_word_count=len((job.description or "").split()),
                seniority=None,
                salary_text=None,
                apply_email=None,
            )
            _give_up_if_capped(conn, job, report, stage_meta)
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                    metadata=stage_meta,
                )
            continue

        try:
            enriched = fetch_detail(job)
        except ListingGone as gone:
            # Final verdict from the source: the posting is off the board.
            # Marking it listing_expired (a terminal status) takes it out of
            # both the enrichment and the scoring queue for good, instead of
            # re-requesting the same dead URL on every run.
            log.info("enrichment_listing_gone", job_id=job.id, source=job.source,
                     reason=gone.reason)
            update_status(conn, job.id, JobStatus.LISTING_EXPIRED,
                          reason=gone.reason,
                          discard_reason=f"listing gone: {gone.reason}")
            report.n_expired += 1
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                    skipped=report.n_expired + report.n_walled,
                )
            continue
        except Exception as e:
            log.exception("enrichment_fetch_detail_failed", job_id=job.id, source=job.source)
            enriched = None

        if enriched is None:
            log.debug("enrichment_no_description", job_id=job.id, source=job.source)
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            stage_meta["fail_by_source"] = dict(report.per_source_failure)
            update_enrichment(
                conn,
                job_id=job.id,
                description_full=job.description or "",
                description_scraped=False,
                description_word_count=len((job.description or "").split()),
                seniority=None,
                salary_text=None,
                apply_email=None,
            )
            _give_up_if_capped(conn, job, report, stage_meta)
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                    metadata=stage_meta,
                )
            continue

        text = (enriched.description or "").strip()
        word_count = len(text.split())
        salary_match = _SALARY_RE.search(text)
        seniority_match = _SENIORITY_RE.search(f"{enriched.title} {text}")
        apply_email = extract_apply_email(text)
        description_scraped = bool(text and word_count >= _MIN_WORDS)

        log.debug("enrichment_persisting", job_id=job.id, source=job.source, word_count=word_count, scraped=description_scraped)

        # Thread the extracted contact through the in-memory job so the
        # applier can route to the email channel without a DB round-trip.
        enriched.apply_email = apply_email

        # Apply-path research: when the row's only apply link is a
        # paywalled aggregator (and there's no email fallback), web-search
        # for the canonical employer apply URL. Skips rows that already
        # have a usable route, caps per run, caches per company+title.
        resolved_apply_url = None
        if research_enabled and n_researched < research_cap:
            from ..state import is_paywalled_apply_url
            cur_url = str(enriched.apply_url or enriched.url or "")
            # Research any paywalled row (hard dailyremote OR soft
            # linkedin/xing) that has no email fallback, to upgrade it to
            # the canonical employer URL. Soft-wall rows keep their link
            # as a fallback if research can't resolve one.
            if not apply_email and is_paywalled_apply_url(cur_url):
                key = (enriched.company or "", enriched.title or "")
                if key in research_cache:
                    resolved_apply_url = research_cache[key]
                else:
                    from .apply_research import research_apply_url
                    resolved_apply_url, note = research_apply_url(
                        enriched.company, enriched.title, cur_url, secrets,
                    )
                    research_cache[key] = resolved_apply_url
                    n_researched += 1
                    log.info(
                        "apply_research", job_id=job.id,
                        resolved=bool(resolved_apply_url), note=note,
                    )
                if resolved_apply_url:
                    enriched.apply_url = resolved_apply_url  # type: ignore[assignment]

        update_enrichment(
            conn,
            job_id=job.id,
            description_full=text,
            description_scraped=description_scraped,
            description_word_count=word_count,
            seniority=seniority_match.group(1).lower() if seniority_match else None,
            salary_text=salary_match.group(0) if salary_match else None,
            apply_email=apply_email,
            company=enriched.company,
            posted_at=(
                enriched.posted_at.isoformat()
                if enriched.posted_at is not None else None
            ),
            apply_url=resolved_apply_url,
        )

        if description_scraped:
            report.n_succeeded += 1
            report.per_source_success[job.source] += 1
            report.enriched_jobs.append(enriched)
        else:
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
            stage_meta["fail_by_source"] = dict(report.per_source_failure)
            _give_up_if_capped(conn, job, report, stage_meta)
        if run_id is not None:
            update_run_stage_progress(
                conn, run_id, "enrichment",
                completed=report.n_succeeded,
                failed=report.n_failed,
                metadata=stage_meta if not description_scraped else None,
            )
    
    log.info("enrichment_complete", n_attempted=report.n_attempted,
             n_succeeded=report.n_succeeded, n_failed=report.n_failed,
             n_walled=report.n_walled, n_gave_up=report.n_gave_up)

    return report
