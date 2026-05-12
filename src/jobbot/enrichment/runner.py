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
import re
import structlog

from ..models import JobPosting
from ..scrapers import REGISTRY
from ..state import update_enrichment, update_run_stage_progress
from .email_extractor import extract_apply_email

log = structlog.get_logger()

_SENIORITY_RE = re.compile(r"\b(intern|junior|mid|senior|lead|principal|staff|head)\b", re.IGNORECASE)
_SALARY_RE = re.compile(r"(?:€\s?\d+[\d.,kK-]*|\b\d+\s?[kK]\b|\b\d{2,3}\s?[-–]\s?\d{2,3}\s?[kK]\b)")
_MIN_WORDS = 100


@dataclass
class EnrichmentReport:
    n_attempted: int = 0
    n_succeeded: int = 0
    n_failed: int = 0
    per_source_success: Counter = field(default_factory=Counter)
    per_source_failure: Counter = field(default_factory=Counter)
    enriched_jobs: list[JobPosting] = field(default_factory=list)


def enrich_new_postings(
    jobs: list[JobPosting],
    conn,
    registry: dict[str, object] | None = None,
    *,
    run_id: int | None = None,
) -> EnrichmentReport:
    """Walk new jobs, call each scraper's fetch_detail, persist enrichment cols.

    Returns counts suitable for the digest's per-source health table.
    """
    report = EnrichmentReport()

    scraper_registry = REGISTRY if registry is None else registry
    log.info("enrichment_starting", n_jobs=len(jobs), n_scrapers=len(scraper_registry))
    if run_id is not None:
        update_run_stage_progress(
            conn, run_id, "enrichment",
            total=len(jobs), started=0, completed=0, failed=0, skipped=0,
            current_index=0, current_item_id=None, current_label=None,
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
        if not callable(fetch_detail):
            log.warning("enrichment_no_fetch_detail", job_id=job.id, source=job.source)
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
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
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                )
            continue

        try:
            enriched = fetch_detail(job)
        except Exception as e:
            log.exception("enrichment_fetch_detail_failed", job_id=job.id, source=job.source)
            enriched = None

        if enriched is None:
            log.debug("enrichment_no_description", job_id=job.id, source=job.source)
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
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
            if run_id is not None:
                update_run_stage_progress(
                    conn, run_id, "enrichment",
                    completed=report.n_succeeded,
                    failed=report.n_failed,
                )
            continue

        text = (enriched.description or "").strip()
        word_count = len(text.split())
        salary_match = _SALARY_RE.search(text)
        seniority_match = _SENIORITY_RE.search(f"{enriched.title} {text}")
        apply_email = extract_apply_email(text)
        description_scraped = bool(text and word_count >= _MIN_WORDS)

        log.debug("enrichment_persisting", job_id=job.id, source=job.source, word_count=word_count, scraped=description_scraped)

        update_enrichment(
            conn,
            job_id=job.id,
            description_full=text,
            description_scraped=description_scraped,
            description_word_count=word_count,
            seniority=seniority_match.group(1).lower() if seniority_match else None,
            salary_text=salary_match.group(0) if salary_match else None,
            apply_email=apply_email,
        )

        if description_scraped:
            report.n_succeeded += 1
            report.per_source_success[job.source] += 1
            report.enriched_jobs.append(enriched)
        else:
            report.n_failed += 1
            report.per_source_failure[job.source] += 1
        if run_id is not None:
            update_run_stage_progress(
                conn, run_id, "enrichment",
                completed=report.n_succeeded,
                failed=report.n_failed,
            )
    
    log.info("enrichment_complete", n_attempted=report.n_attempted, n_succeeded=report.n_succeeded, n_failed=report.n_failed)

    return report
