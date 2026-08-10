"""Pipeline orchestrator: scrape → score → generate → (apply) → notify."""
from __future__ import annotations

import fcntl
import os
import tempfile
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog

from .applier import apply_to_job
from .applier.salary import posting_below_hourly_floor, posting_below_salary_floor
from .config import Config, Secrets
from .enrichment.runner import enrich_new_postings
from .generators import (
    generate_application_package,
    generate_documents,  # noqa: F401 - public monkeypatch seam for older tests/tools.
    load_existing_docs,
)
from .housekeep import housekeep_shortlist
from .models import TERMINAL_STATUSES, JobPosting, JobStatus
from .notify import send_digest, send_failure_alert
from .profile import load_base_cv, load_profile
from .scoring import (
    CannotScore,
    llm_score,
    llm_score_tailored,
    passes_heuristic,
    too_old_for_market,
)
from .scrapers import REGISTRY
from .state import (
    apply_channel, apply_channel_ats_name, connect, finish_run, jobs_by_status,
    jobs_needing_enrichment, jobs_with_submitted_application,
    mark_run_stopped, record_application, start_run,
    update_score_tailored, update_run_stage_progress, update_status, upsert_new,
    wait_while_paused,
)

log = structlog.get_logger()

# Fallback when no config is threaded through (tests, ad-hoc callers).
# The live value comes from `config.max_market_age_days`.
RECENT_POSTING_DAYS = 3


def _is_recent_posting(
    job: JobPosting, *, now: datetime, max_age_days: int = RECENT_POSTING_DAYS
) -> bool:
    """Return whether a posting should be considered for this run.

    Some portals do not expose a reliable posting timestamp. Those rows stay
    in the pipeline so the detail-body and scoring gates can judge them. When
    a timestamp is present, anything advertised for longer than
    `max_age_days` is stale: the shortlist is already formed, so scraping,
    enriching and scoring it spends work on a race we have lost.

    `max_age_days <= 0` disables the gate.
    """
    if job.posted_at is None or max_age_days <= 0:
        return True
    posted_at = job.posted_at
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    return posted_at >= now - timedelta(days=max_age_days)


#

# A run that outlives this is stuck, not busy: the longest healthy run on
# record is 90 minutes.
STUCK_RUN_AFTER_H = 3.0


def _lock_holder_age(lock_path: Path) -> dict[str, Any]:
    """Describe the process holding the run lock, for the skip log line.

    The lock file carries "<pid> <iso timestamp>" written by the holder.
    Returns pid / age_hours / stuck so one grep answers "is a run wedged?".
    """
    info: dict[str, Any] = {"holder_pid": None, "holder_age_hours": None,
                            "holder_stuck": False}
    try:
        raw = lock_path.read_text().split()
        if len(raw) >= 2:
            info["holder_pid"] = raw[0]
            started = datetime.fromisoformat(raw[1])
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            hours = (datetime.now(tz=timezone.utc) - started).total_seconds() / 3600
            info["holder_age_hours"] = round(hours, 1)
            info["holder_stuck"] = hours > STUCK_RUN_AFTER_H
    except Exception:
        pass
    return info


@contextmanager
def _single_run_lock() -> Any:
    """Refuse to start a second pipeline run while one is in flight.

    Five launchd invocations a day (scrape at 08/12/16/20, daily at 15) plus
    the dashboard's "Run now" button share one machine, one SQLite file and
    one Claude CLI subscription, and nothing stopped them from overlapping.
    Runs 292 and 293 did exactly that on 2026-07-30, starting 114 seconds
    apart: 292 kept scoring while 293 failed 137 of its calls.

    Yields True when the lock was acquired, False when another run holds it.
    """
    # Overridable so the test suite never shares the production lock. Without
    # this, running pytest while a real run is in flight made 18 pipeline
    # tests fail: run_once() saw the live run's lock, returned
    # "already running", and every assertion about scored rows came up empty.
    # A red suite that depends on the time of day is worse than no suite.
    lock_path = Path(os.environ.get("JOBBOT_RUN_LOCK_DIR")
                     or tempfile.gettempdir()) / "jobbot-run.lock"
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # The holder may be hung rather than working. Run 347 blocked on
            # an RSS fetch with no timeout and held this lock for 32 hours,
            # so the eight scheduled runs behind it each logged one quiet
            # "already running" line and did nothing, while the dashboard
            # kept showing two-day-old results as if all were well. Say
            # loudly how old the holder is so a stuck run is visible in the
            # logs of every run it blocks.
            log.warning("run_skipped_already_running", **_lock_holder_age(lock_path))
            yield False
            return
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()} {datetime.now(tz=timezone.utc).isoformat()}\n".encode())
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def run_once(config: Config, secrets: Secrets) -> dict[str, Any]:
    """Single end-to-end pipeline pass. Returns a summary dict."""
    with _single_run_lock() as acquired:
        if not acquired:
            log.warning("run_skipped_already_running")
            return {
                "run_id": None, "n_fetched": 0, "n_new": 0,
                "n_generated": 0, "n_applied": 0, "n_errors": 0,
                "diagnostics": {"skipped": "another pipeline run is already in flight"},
            }
        return _run_once_locked(config, secrets)


def _run_once_locked(config: Config, secrets: Secrets) -> dict[str, Any]:
    profile = load_profile()
    base_cv = load_base_cv()
    started = datetime.now(tz=timezone.utc)

    matches: list[dict] = []
    cannot_score_entries: list[dict] = []
    errors: list[dict] = []
    n_fetched = n_new = n_generated = n_applied = 0
    n_enriched = n_enrichment_failed = 0
    n_filtered = n_scored = n_below_threshold = n_score_failed = 0
    n_stale_postings = 0
    n_cannot_score = 0
    blocker_counts: Counter[str] = Counter()
    score_values: list[int] = []
    per_source_fetched: Counter[str] = Counter()
    per_source_new: Counter[str] = Counter()
    fetched_ids: list[str] = []

    with connect() as conn:
        run_id = start_run(conn)

        def _stopped_result(reason: str) -> dict[str, Any]:
            mark_run_stopped(conn, run_id, reason=reason)
            diagnostics = {
                "stages": {
                    "fetched": n_fetched,
                    "new": n_new,
                    "duplicates_or_seen_before": max(0, n_fetched - n_new),
                    "enriched": n_enriched,
                    "enrichment_failed": n_enrichment_failed,
                    "stale_postings": n_stale_postings,
                    "filtered": n_filtered,
                    "cannot_score": n_cannot_score,
                    "scored": n_scored,
                    "below_threshold": n_below_threshold,
                    "score_failed": n_score_failed,
                    "generated": n_generated,
                    "applied": n_applied,
                    "stopped": 1,
                },
                "per_source_fetched": dict(per_source_fetched),
                "per_source_new": dict(per_source_new),
                "fetched_ids": list(dict.fromkeys(fetched_ids)),
                "score_stats": {},
                "top_blockers": [{"reason": reason, "count": 1}],
            }
            return {
                "run_id": run_id,
                "n_fetched": n_fetched, "n_new": n_new,
                "n_generated": n_generated, "n_applied": n_applied,
                "n_errors": len(errors) + 1,
                "diagnostics": diagnostics,
                "stopped": True,
            }

        def _continue_or_stop() -> dict[str, Any] | None:
            if wait_while_paused(conn, run_id):
                return None
            return _stopped_result("stopped from dashboard")

        # 1) Scrape
        all_new: list[JobPosting] = []
        all_fetched_by_id: dict[str, JobPosting] = {}
        scrape_queries = [
            (name, query)
            for name, src_cfg in config.sources.items()
            if src_cfg.enabled
            for query in src_cfg.queries
        ]
        scrape_meta: dict[str, Any] = {
            "stage_started_at": datetime.now(timezone.utc).isoformat(),
            "hits_so_far": 0,
            "new_so_far": 0,
            # The stage total counts SEARCHES, not job boards: 14 enabled
            # boards carry 29 queries between them. The dashboard showed a
            # bare "29/29", which reads as 29 sites. Ship the board count so
            # the label can say what the number actually is.
            "boards": sum(1 for s in config.sources.values() if s.enabled),
        }
        update_run_stage_progress(
            conn, run_id, "scrape",
            total=len(scrape_queries), started=0, completed=0, failed=0, skipped=0,
            current_index=0, current_item_id=None, current_label=None,
            metadata=scrape_meta,
        )
        scrape_index = 0
        scrape_failed = 0
        scrape_skipped = 0
        for name, src_cfg in config.sources.items():
            if not src_cfg.enabled:
                continue
            scraper = REGISTRY.get(name)
            if scraper is None:
                errors.append({"source": name, "error": "no scraper registered"})
                # Count this source's queries as skipped so the scrape
                # progress bar can complete; a config that names a portal
                # this build doesn't ship must not read as a stuck run.
                scrape_skipped += len(src_cfg.queries)
                scrape_meta["skipped_reason"] = f"no scraper registered: {name}"
                update_run_stage_progress(
                    conn, run_id, "scrape",
                    skipped=scrape_skipped,
                    metadata=scrape_meta,
                )
                continue
            for query in src_cfg.queries:
                if stopped := _continue_or_stop():
                    return stopped
                scrape_index += 1
                update_run_stage_progress(
                    conn, run_id, "scrape",
                    total=len(scrape_queries), started=scrape_index,
                    current_index=scrape_index,
                    current_item_id=name,
                    current_label=f"{name} · {query}",
                    metadata={**scrape_meta,
                              "hits_so_far": n_fetched, "new_so_far": n_new},
                )
                try:
                    fetched_raw = scraper.fetch(query)
                    fetched = [
                        job for job in fetched_raw
                        if _is_recent_posting(
                            job, now=started,
                            max_age_days=config.max_market_age_days,
                        )
                    ]
                    stale_count = len(fetched_raw) - len(fetched)
                    if stale_count:
                        n_stale_postings += stale_count
                        blocker_counts[
                            f"posting older than {config.max_market_age_days} days"
                        ] += stale_count
                    for job in fetched:
                        all_fetched_by_id[job.id] = job
                    n_fetched += len(fetched)
                    per_source_fetched[name] += len(fetched)
                    fetched_ids.extend(j.id for j in fetched)
                    new = upsert_new(conn, fetched)
                    all_new.extend(new)
                    n_new += len(new)
                    per_source_new[name] += len(new)
                    update_run_stage_progress(
                        conn, run_id, "scrape",
                        completed=scrape_index,
                        metadata={
                            "hits_so_far": n_fetched,
                            "new_so_far": n_new,
                        },
                    )
                except Exception as e:
                    log.exception("scraper_failed", source=name, query=query)
                    errors.append({"source": name, "error": f"{type(e).__name__}: {e}"})
                    scrape_failed += 1
                    update_run_stage_progress(
                        conn, run_id, "scrape",
                        completed=max(0, scrape_index - scrape_failed),
                        failed=scrape_failed,
                        metadata={
                            "hits_so_far": n_fetched,
                            "new_so_far": n_new,
                        },
                    )

        # 2) Enrich postings missing a body fetch: genuinely NEW rows this
        # run, plus older seen_jobs rows where description_scraped IS NULL.
        # Crucially we do NOT re-enrich rows we've already enriched on a
        # prior run, re-scraping returns them in all_fetched_by_id every
        # day, and re-fetching their detail page (plus re-running apply-path
        # research and, downstream, re-scoring + re-generating) is pure
        # waste. `all_new` is the upsert's genuinely-new set;
        # jobs_needing_enrichment covers rows still missing a body.
        to_enrich_by_id: dict[str, JobPosting] = {j.id: j for j in all_new}
        retry_first_seen: dict[str, str | None] = {}
        for stale, first_seen in jobs_needing_enrichment(conn):
            if stale.id not in to_enrich_by_id:
                to_enrich_by_id[stale.id] = stale
                retry_first_seen[stale.id] = first_seen

        # Market-age gate, applied BEFORE the detail fetch. A posting that
        # has been advertised for longer than `max_market_age_days` has
        # already collected its shortlist, so both the HTTP detail fetch and
        # the later LLM call would be spent on a race we have lost. Retiring
        # the row here (rather than at scoring time) is what makes this an
        # efficiency win instead of a cosmetic one, and it also stops the row
        # from re-entering the enrichment queue on every subsequent run.
        # Retry rows fall back to first_seen_at, same as the scoring gate:
        # most retry rows have no posted_at at all (bot-walled boards), and
        # without the fallback they re-fail their fetch on every run forever
        # — run 305 spent 84 of its 85 fetches on that zombie queue.
        n_too_old = 0
        for jid, candidate in list(to_enrich_by_id.items()):
            is_stale, age_reason = too_old_for_market(
                candidate, config.max_market_age_days,
                first_seen_at=retry_first_seen.get(jid),
            )
            if is_stale:
                del to_enrich_by_id[jid]
                update_status(conn, jid, JobStatus.FILTERED,
                              reason=age_reason, discard_reason=age_reason)
                n_too_old += 1
        if n_too_old:
            log.info("market_age_gate", stage="pre_enrichment", retired=n_too_old,
                     cutoff_days=config.max_market_age_days)

        cap = config.enrichment.per_run_cap
        to_enrich = list(to_enrich_by_id.values())[:cap]
        n_retries_queued = sum(1 for j in to_enrich if j.id in retry_first_seen)
        # Funnel telemetry between "search job boards" and "fetch details":
        # the panel needs to say why 333 found postings became 13 fetches
        # (dedup, age gate, retry backlog) or the narrowing reads as loss.
        enrich_meta: dict[str, Any] = {
            "found": n_fetched,
            "already_seen": max(0, n_fetched - n_new),
            "too_old": n_too_old,
            "new": len(to_enrich) - n_retries_queued,
            "retries": n_retries_queued,
            "deferred_over_cap": max(0, len(to_enrich_by_id) - cap),
        }
        enrichment = enrich_new_postings(
            to_enrich, conn, registry=REGISTRY, run_id=run_id,
            config=config, secrets=secrets, stage_metadata=enrich_meta,
        )
        n_enriched = enrichment.n_succeeded
        n_enrichment_failed = enrichment.n_failed

        # 3) Score (heuristic → LLM)
        # Retry pending scraped jobs from previous runs as well, so transient
        # LLM/network failures do not leave jobs stuck in "scraped" forever.
        # `to_score` values are (job, description_scraped), the flag must be
        # propagated to the scorer per PRD §7.5 FR-SCO-01.
        to_score: dict[str, tuple[JobPosting, bool]] = {
            j.id: (j, True) for j in enrichment.enriched_jobs
        }
        for row in jobs_by_status(conn, JobStatus.SCRAPED):
            if row["id"] in to_score:
                continue
            try:
                candidate = JobPosting.model_validate_json(row["raw_json"])
                # For legacy SCRAPED rows the raw_json description is just the
                # listing-card snippet. Swap in the enriched body if we have
                # one, and forward the enrichment flag verbatim so the scorer
                # can refuse rows that were never really enriched.
                if row["description_full"]:
                    candidate = candidate.model_copy(
                        update={"description": row["description_full"]}
                    )
                # Backlog rows age out here, using first_seen_at when the
                # source never gave us a posted_at (14% of the corpus).
                # Without the fallback those rows are immortal: a failed
                # scoring call drops the status back to SCRAPED, the next run
                # picks it up again, and the queue refills itself forever.
                # Runs 286-296 show exactly that, up to 200 attempts per run
                # against 0-48 genuinely new postings.
                is_stale, age_reason = too_old_for_market(
                    candidate, config.max_market_age_days,
                    first_seen_at=row["first_seen_at"],
                )
                if is_stale:
                    update_status(conn, row["id"], JobStatus.FILTERED,
                                  reason=age_reason, discard_reason=age_reason)
                    continue
                desc_scraped = bool(row["description_scraped"])
                to_score[row["id"]] = (candidate, desc_scraped)
            except Exception as e:
                errors.append({"source": row["source"], "error": f"decode: {e}"})

        # Guard against re-scoring rows that already reached a terminal
        # status. Without this, a still-listed posting that was previously
        # marked listing_expired (or apply_submitted / employer_received /
        # rejected / etc.) gets clobbered back to SCORED the next time the
        # scraper finds it on the source board. `INSERT OR IGNORE` in
        # upsert_new keeps the seen_jobs row stable, but the in-memory
        # JobPosting still flows through enrichment → to_score → the
        # unconditional `update_status(JobStatus.SCORED, ...)` at the end
        # of the scoring loop. Skipping these IDs at the source preserves
        # the downstream state.
        if to_score:
            placeholders = ",".join("?" * len(to_score))
            existing = dict(conn.execute(
                f"SELECT id, status FROM seen_jobs WHERE id IN ({placeholders})",
                list(to_score.keys()),
            ).fetchall())
            n_terminal_skipped = 0
            for jid in list(to_score.keys()):
                if existing.get(jid) in TERMINAL_STATUSES:
                    del to_score[jid]
                    n_terminal_skipped += 1
            if n_terminal_skipped:
                log.info("scoring_skip_terminal", count=n_terminal_skipped)

        to_generate: list[tuple[JobPosting, int, str]] = []
        score_candidates = list(to_score.values())[: config.max_jobs_per_run]
        # Live telemetry for the dashboards: queue composition (fresh finds
        # vs backlog), a rolling feed of landed scores, and failure reasons.
        # The dict is mutated in place and snapshotted into metadata_json on
        # every progress write.
        fresh_ids = {j.id for j in enrichment.enriched_jobs if j is not None}
        n_from_this_run = sum(1 for j, _ in score_candidates if j.id in fresh_ids)
        scoring_meta: dict[str, Any] = {
            "stage_started_at": datetime.now(timezone.utc).isoformat(),
            "from_this_run": n_from_this_run,
            "backlog": len(score_candidates) - n_from_this_run,
            "ticker": [],     # newest last, capped at 24
            "failures": [],   # newest last, capped at 8
            "n_strong": 0,
            "strong_threshold": config.digest.generate_docs_above_score,
        }

        def _tick(job: JobPosting, score: int) -> None:
            scoring_meta["ticker"].append({"c": job.company, "s": score})
            del scoring_meta["ticker"][:-24]
            if score >= scoring_meta["strong_threshold"]:
                scoring_meta["n_strong"] += 1

        def _tick_failure(job: JobPosting, why: str) -> None:
            scoring_meta["failures"].append({"c": job.company, "e": why[:80]})
            del scoring_meta["failures"][:-8]

        update_run_stage_progress(
            conn, run_id, "scoring",
            total=len(score_candidates), started=0, completed=0, failed=0,
            current_index=0, current_label=None,
            metadata=scoring_meta,
        )

        # --- Concurrent prefetch of the LLM scores -------------------------
        # The LLM call is the entire cost of this stage: 7.0s per posting
        # measured on run 297, 1408s of a 2023s run, and the calls are fully
        # independent (no shared context, no history, one posting per call).
        # We therefore prefetch them through a small thread pool and keep
        # every DB write on the main thread in the loop below, which leaves
        # the persistence logic and its ordering untouched.
        #
        # The free gates are re-evaluated in the loop. They are pure regex
        # work, so running them twice costs microseconds and is far safer
        # than restructuring the persistence code around a future map.
        prefetched: dict[str, Any] = {}
        workers = max(1, config.score_concurrency)
        if workers > 1 and score_candidates:
            eligible: list[tuple[JobPosting, bool]] = []
            for cand_job, cand_scraped in score_candidates:
                if too_old_for_market(cand_job, config.max_market_age_days)[0]:
                    continue
                if not passes_heuristic(cand_job, profile)[0]:
                    continue
                if cand_job.source in (config.freelance_sources or []):
                    skip, _ = posting_below_hourly_floor(
                        cand_job.description, config.freelance_hourly_floor_eur)
                else:
                    skip, _ = posting_below_salary_floor(
                        cand_job.description, config.salary_floor_eur_year)
                if skip:
                    continue
                eligible.append((cand_job, cand_scraped))

            def _score_one(item: tuple[JobPosting, bool]) -> tuple[str, Any]:
                pf_job, pf_scraped = item
                try:
                    return pf_job.id, llm_score(
                        pf_job, profile, secrets,
                        description_scraped=pf_scraped,
                        run_id=run_id, phase="score_base",
                    )
                except BaseException as exc:  # re-raised on the main thread
                    return pf_job.id, exc

            if eligible:
                log.info("scoring_prefetch", candidates=len(eligible), workers=workers)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for pf_id, outcome in pool.map(_score_one, eligible):
                        prefetched[pf_id] = outcome

        # Circuit breaker state: a process-level fault (expired CLI login,
        # rate limit, unreachable backend) is identical for every candidate,
        # so rediscovering it 200 times only burns the run budget.
        consecutive_failures = 0
        last_failure_kind: str | None = None

        for idx, (job, desc_scraped) in enumerate(score_candidates, start=1):
            if stopped := _continue_or_stop():
                return stopped
            update_run_stage_progress(
                conn, run_id, "scoring",
                total=len(score_candidates), started=idx, current_index=idx,
                current_item_id=job.id,
                current_label=f"{job.title} @ {job.company}",
                metadata=scoring_meta,
            )
            # Second market-age checkpoint. The pre-enrichment gate above
            # catches rows on their way in; this one catches rows that were
            # already enriched on an earlier run and have since gone stale
            # while sitting in the scoring queue.
            is_stale, age_reason = too_old_for_market(job, config.max_market_age_days)
            if is_stale:
                update_status(conn, job.id, JobStatus.FILTERED,
                              reason=age_reason, discard_reason=age_reason)
                n_filtered += 1
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    skipped=n_filtered,
                    metadata=scoring_meta,
                )
                # Stable bucket key: the per-row reason carries the exact age,
                # which would otherwise fragment the blocker histogram.
                blocker_counts["too old on the market"] += 1
                continue
            ok, reason = passes_heuristic(job, profile)
            if not ok:
                # No score is assigned here: heuristic filtering happens *before*
                # the LLM runs, and PRD §7.5 reserves the `score` column for
                # actual LLM output. Leaving it NULL preserves the invariant
                # that "score IS NOT NULL ⇒ preconditions passed".
                # Persist the heuristic rejection cause to discard_reason so the
                # dashboard's Scoring Reason column shows WHY the row was dropped
                # without making the user open the row to read score_reason.
                update_status(conn, job.id, JobStatus.FILTERED, reason=reason,
                              discard_reason=f"heuristic: {reason}")
                n_filtered += 1
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    skipped=n_filtered,
                    metadata=scoring_meta,
                )
                blocker_counts[reason or "filtered by heuristic"] += 1
                continue
            # Salary-floor filter: drop a posting before the LLM scoring
            # call when its pay is clearly below the candidate's floor.
            # Freelance sources (freelancermap) quote hourly/daily rates,
            # not an annual salary, so they're held to the hourly floor;
            # everything else uses the annual floor. Postings that state no
            # pay pass through untouched. Done pre-LLM to save spend.
            if job.source in (config.freelance_sources or []):
                below_floor, floor_reason = posting_below_hourly_floor(
                    job.description, config.freelance_hourly_floor_eur,
                )
            else:
                below_floor, floor_reason = posting_below_salary_floor(
                    job.description, config.salary_floor_eur_year,
                )
            if below_floor:
                update_status(conn, job.id, JobStatus.FILTERED,
                              reason=floor_reason, discard_reason=floor_reason)
                n_filtered += 1
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    skipped=n_filtered,
                    metadata=scoring_meta,
                )
                blocker_counts["salary below floor"] += 1
                continue
            try:
                staged = prefetched.pop(job.id, None)
                if isinstance(staged, BaseException):
                    raise staged
                result = staged if staged is not None else llm_score(
                    job, profile, secrets,
                    description_scraped=desc_scraped,
                    run_id=run_id,
                    phase="score_base",
                )
            except CannotScore as e:
                # PRD §7.5 FR-SCO-01: refuse to score, persist the reason so
                # the digest can surface it instead of a misleading number.
                reason = e.reason
                if reason.startswith("no_body"):
                    new_status = JobStatus.CANNOT_SCORE_NO_BODY
                elif reason.startswith("no_primary_cv"):
                    new_status = JobStatus.CANNOT_SCORE_NO_PRIMARY_CV
                elif reason.startswith("no_base_cv"):
                    new_status = JobStatus.CANNOT_SCORE_NO_BASE_CV
                else:
                    new_status = JobStatus.CANNOT_SCORE_NO_BODY
                update_status(conn, job.id, new_status, score=None, reason=reason)
                n_cannot_score += 1
                blocker_counts[f"cannot_score: {reason}"] += 1
                _tick_failure(job, reason)
                cannot_score_entries.append({
                    "job": job.model_dump(mode="json"),
                    "status": new_status.value,
                    "reason": reason,
                })
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    failed=n_cannot_score + n_score_failed,
                    metadata=scoring_meta,
                )
                continue
            except Exception as e:
                log.exception("score_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"score: {e}"})
                n_score_failed += 1
                err_label = f"scoring error: {type(e).__name__}"
                blocker_counts[err_label] += 1
                _tick_failure(job, err_label)
                # No score recorded: the LLM call failed, so per PRD §7.5
                # there is no trustworthy number. Status drops back to
                # SCRAPED so the next run retries.
                update_status(conn, job.id, JobStatus.SCRAPED, reason=err_label)
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    failed=n_cannot_score + n_score_failed,
                    metadata=scoring_meta,
                )
                # Circuit breaker. Identical back-to-back failures mean the
                # backend is down, not that these particular postings are
                # bad, so stop instead of spending the rest of the budget
                # rediscovering it. Remaining candidates keep their SCRAPED
                # status and are picked up by the next run.
                if last_failure_kind == err_label:
                    consecutive_failures += 1
                else:
                    last_failure_kind, consecutive_failures = err_label, 1
                breaker = config.score_failure_breaker
                if breaker > 0 and consecutive_failures >= breaker:
                    remaining = len(score_candidates) - idx
                    log.error("scoring_circuit_breaker_tripped",
                              kind=err_label, consecutive=consecutive_failures,
                              remaining=remaining)
                    errors.append({
                        "source": "pipeline",
                        "error": (
                            f"scoring stopped after {consecutive_failures} consecutive "
                            f"{err_label}; {remaining} candidate(s) left untouched"
                        ),
                    })
                    blocker_counts["scoring stopped: backend failing"] += 1
                    break
                continue
            consecutive_failures, last_failure_kind = 0, None
            if result.score < config.score_threshold:
                update_status(conn, job.id, JobStatus.BELOW_THRESHOLD,
                              score=result.score, reason=result.reason,
                              breakdown=result.breakdown,
                              discard_reason=result.discard_reason)
                n_below_threshold += 1
                score_values.append(result.score)
                _tick(job, result.score)
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold,
                    failed=n_cannot_score + n_score_failed,
                    metadata=scoring_meta,
                )
                continue
            update_status(conn, job.id, JobStatus.SCORED,
                          score=result.score, reason=result.reason,
                          breakdown=result.breakdown,
                          discard_reason=result.discard_reason)
            n_scored += 1
            score_values.append(result.score)
            to_generate.append((job, result.score, result.reason))
            _tick(job, result.score)
            update_run_stage_progress(
                conn, run_id, "scoring",
                completed=n_scored + n_below_threshold,
                failed=n_cannot_score + n_score_failed,
                metadata=scoring_meta,
            )

        # 3.5) Housekeep: probe every live shortlist row's apply URL and
        # demote dead postings to listing_expired BEFORE Stage 3 wastes
        # generation cost on a role that's been pulled. The probe is the
        # same one the apply runner uses (HEAD + redirect-to-generic
        # detection), just batched. Demoted rows are dropped from
        # to_generate so they never reach the generation loop.
        try:
            # `score_threshold` is the DIGEST cut and is set to 0 in this
            # deployment, so passing it here made housekeeping HEAD-probe
            # the entire scored corpus on every run: ~929 outbound requests
            # taking 41-95s, worst observed 473s, five times a day. The rows
            # that matter are the ones we might still apply to, so probe
            # against the generation gate instead.
            hk_min_score = max(
                config.score_threshold,
                config.digest.generate_docs_above_score,
            )
            hk_report = housekeep_shortlist(conn, min_score=hk_min_score)
            if hk_report.marked_expired:
                expired_ids = {r["id"] for r in hk_report.expired_rows}
                to_generate = [t for t in to_generate if t[0].id not in expired_ids]
                log.info(
                    "housekeep_marked_expired",
                    scanned=hk_report.scanned,
                    marked=hk_report.marked_expired,
                )
        except Exception as e:
            log.warning("housekeep_failed", error=str(e))

        # 4) Generate, only the top-N highest-scoring postings get tailored
        # CV + cover letter. Lower-ranked shortlist entries still flow through
        # the loop so they appear in the digest/dashboard, but with docs
        # skipped (the `score < generate_docs_above_score` branch handles
        # that). User controls run frequency; there is no daily cap. The
        # cap is configurable via config.digest.generate_top_n (default 5).
        to_generate.sort(key=lambda triple: triple[1], reverse=True)
        top_n = config.digest.generate_top_n
        if top_n > 0 and len(to_generate) > top_n:
            tailored_ids = {triple[0].id for triple in to_generate[:top_n]}
        else:
            tailored_ids = {triple[0].id for triple in to_generate}
        update_run_stage_progress(
            conn, run_id, "generation",
            total=len(to_generate), started=0, completed=0, failed=0,
            current_index=0, current_label=None,
            metadata={"stage_started_at": datetime.now(timezone.utc).isoformat()},
        )
        generation_skipped = 0
        generation_failed = 0
        for gen_idx, (job, score, reason) in enumerate(to_generate, start=1):
            if stopped := _continue_or_stop():
                return stopped
            update_run_stage_progress(
                conn, run_id, "generation",
                total=len(to_generate), started=gen_idx, current_index=gen_idx,
                current_item_id=job.id,
                current_label=f"{job.title} @ {job.company}",
            )
            # PRD §7.7 FR-APP-01: derive the application channel per match so
            # the digest + dashboard can show '📧 email / 🔗 Greenhouse / etc.'
            # apply_email lives only in seen_jobs (enrichment column), so we
            # do one tiny SELECT per match, cheap and avoids threading the
            # enrichment result through the pipeline.
            apply_email_row = conn.execute(
                "SELECT apply_email FROM seen_jobs WHERE id = ?", (job.id,),
            ).fetchone()
            apply_email = apply_email_row["apply_email"] if apply_email_row else None
            apply_url = str(job.apply_url) if job.apply_url else (str(job.url) if job.url else None)
            channel = apply_channel(apply_email=apply_email, apply_url=apply_url)
            ats_name = apply_channel_ats_name(apply_url) if channel == "form" else None

            entry: dict[str, Any] = {
                "job": job.model_dump(mode="json"),
                "score": score,
                "reason": reason,
                "output_dir": None,
                "cover_letter_html": "",
                "apply_status": None,
                "apply_email": apply_email,
                "apply_url": apply_url,
                "apply_channel": channel,
                "apply_channel_ats_name": ats_name,
            }

            if score < config.digest.generate_docs_above_score or job.id not in tailored_ids:
                matches.append(entry)
                generation_skipped += 1
                update_run_stage_progress(
                    conn, run_id, "generation",
                    completed=n_generated,
                    skipped=generation_skipped,
                    failed=generation_failed,
                )
                continue

            # Idempotency: reuse an existing CV + cover letter from a prior
            # run instead of paying the LLM to regenerate identical docs.
            # The output_dir column holds the last-generated location;
            # if cv.md + cover_letter.md are still on disk we reuse them.
            # `regenerate_existing_docs` forces a fresh build (e.g. after
            # the base CV or prompts change). This is the fix for daily
            # runs re-spending on already-done profiles.
            prior_dir_row = conn.execute(
                "SELECT output_dir, score_tailored FROM seen_jobs WHERE id = ?",
                (job.id,),
            ).fetchone()
            prior_dir = prior_dir_row["output_dir"] if prior_dir_row else None
            reused_docs = (
                None if config.regenerate_existing_docs
                else load_existing_docs(prior_dir)
            )

            if reused_docs is not None:
                docs = reused_docs
                update_status(conn, job.id, JobStatus.GENERATED, output_dir=docs.output_dir)
                generation_skipped += 1
                log.info("generation_reused_existing", job_id=job.id, dir=docs.output_dir)
                entry.update({
                    "output_dir": docs.output_dir,
                    "cover_letter_html": docs.cover_letter_html,
                })
                # Carry forward the tailored score from the prior run; no
                # need to pay for a rescore of unchanged docs.
                if prior_dir_row and prior_dir_row["score_tailored"] is not None:
                    entry["score_tailored"] = prior_dir_row["score_tailored"]
                    entry["score_delta"] = prior_dir_row["score_tailored"] - score
                update_run_stage_progress(
                    conn, run_id, "generation",
                    completed=n_generated, skipped=generation_skipped,
                    failed=generation_failed,
                )
                # Fall through to the auto-apply block with the reused docs.
                _skip_tailored_rescore = True
            else:
                _skip_tailored_rescore = False
                try:
                    # Prefer the unified opus-style application package so the
                    # email channel attaches a single polished PDF. CV + CL PDFs
                    # are still produced as ATS form-upload fallbacks.
                    docs = generate_application_package(
                        job, profile, base_cv, secrets, config, run_id=run_id,
                    )
                    update_status(conn, job.id, JobStatus.GENERATED, output_dir=docs.output_dir)
                    n_generated += 1
                    update_run_stage_progress(
                        conn, run_id, "generation",
                        completed=n_generated,
                    )
                except Exception as e:
                    log.exception("generate_failed", job_id=job.id)
                    errors.append({"source": job.source, "error": f"generate: {e}"})
                    generation_failed += 1
                    update_run_stage_progress(
                        conn, run_id, "generation",
                        completed=n_generated,
                        failed=generation_failed,
                        skipped=generation_skipped,
                    )
                    continue

            if not reused_docs:
                entry.update({
                    "output_dir": docs.output_dir,
                    "cover_letter_html": docs.cover_letter_html,
                })

            # 4b) Rescore the posting using the tailored CV + cover letter
            # so the dashboard can show "did tailoring lift the fit?", a
            # measurement-only call. Persisted to a parallel column;
            # the original `score` is unchanged. A failure here is logged
            # but does NOT abort the application step that follows.
            # Skipped when we reused existing docs (the tailored score is
            # already on file and the docs are unchanged).
            if not _skip_tailored_rescore:
                try:
                    if stopped := _continue_or_stop():
                        return stopped
                    tailored = llm_score_tailored(
                        job, profile, secrets,
                        tailored_cv_md=docs.cv_md,
                        tailored_cover_letter_md=docs.cover_letter_md,
                        run_id=run_id,
                        phase="tailored_rescore",
                    )
                    update_score_tailored(conn, job.id, tailored.score, tailored.reason)
                    entry["score_tailored"] = tailored.score
                    entry["tailored_reason"] = tailored.reason
                    entry["score_delta"] = tailored.score - score
                except Exception as e:
                    log.warning("score_tailored_failed", job_id=job.id, error=str(e))

            # 5) Auto-apply (opt-in per source)
            src_cfg = config.sources.get(job.source)
            if src_cfg and src_cfg.auto_submit and n_applied < config.apply.per_run_limit:
                # Never re-apply to a job that already has a real submitted
                # application on file, bot OR manual mark. This is the
                # primary foot-gun guard; without it, every run would
                # re-send to the same employer.
                already_applied = jobs_with_submitted_application(conn)
                if job.id in already_applied:
                    log.info("apply_skip_already_applied", job_id=job.id,
                             title=job.title, company=job.company)
                    entry["apply_status"] = "skipped_already_applied"
                    matches.append(entry)
                    continue
                # Make sure apply_email (extracted at enrichment time, looked
                # up above for the digest) rides with the JobPosting so the
                # runner can route to the email channel without re-querying.
                if not job.apply_email and apply_email:
                    job.apply_email = apply_email
                try:
                    res = apply_to_job(job, profile, docs, secrets, config)
                    record_application(conn, job.id, res)
                    update_status(conn, job.id, res.status)
                    entry["apply_status"] = (
                        "submitted" if res.submitted
                        else "dry_run" if res.dry_run
                        else "needs_review" if res.status == JobStatus.APPLY_NEEDS_REVIEW
                        else "failed"
                    )
                    if res.submitted:
                        n_applied += 1
                except Exception as e:
                    log.exception("apply_failed", job_id=job.id)
                    entry["apply_status"] = "failed"
                    errors.append({"source": job.source, "error": f"apply: {e}"})

            matches.append(entry)

        # 6) Notify
        matches = sorted(matches, key=lambda entry: entry["score"], reverse=True)
        matches = matches[: config.digest.max_per_email]
        try:
            send_digest(secrets, matches, errors, started,
                        cannot_score=cannot_score_entries)
        except Exception as e:
            log.exception("digest_send_failed")
            errors.append({"source": "notify", "error": str(e)})

        score_stats = {
            "count": len(score_values),
            "avg": round(sum(score_values) / len(score_values), 1) if score_values else 0,
            "min": min(score_values) if score_values else None,
            "max": max(score_values) if score_values else None,
            "threshold": config.score_threshold,
        }
        diagnostics = {
            "stages": {
                "fetched": n_fetched,
                "new": n_new,
                "duplicates_or_seen_before": max(0, n_fetched - n_new),
                "enriched": n_enriched,
                "enrichment_failed": n_enrichment_failed,
                "stale_postings": n_stale_postings,
                "filtered": n_filtered,
                "cannot_score": n_cannot_score,
                "scored": n_scored,
                "below_threshold": n_below_threshold,
                "score_failed": n_score_failed,
                "generated": n_generated,
                "applied": n_applied,
            },
            "per_source_fetched": dict(per_source_fetched),
            "per_source_new": dict(per_source_new),
            "fetched_ids": list(dict.fromkeys(fetched_ids)),
            "score_stats": score_stats,
            "top_blockers": [
                {"reason": reason, "count": count}
                for reason, count in blocker_counts.most_common(8)
            ],
            # Distinct error MESSAGES, deduplicated with a count. Only the
            # exception type used to survive into the summary, so runs
            # 287-296 recorded "scoring error: LlmError" 131-200 times with
            # no way to tell a rate limit from a timeout from a non-zero
            # exit. Deduplicating keeps this small even when a run fails
            # wholesale, which is exactly when it is worth reading.
            "error_samples": [
                {"error": msg, "count": count}
                for msg, count in Counter(
                    str(e.get("error", ""))[:400] for e in errors
                ).most_common(6)
            ],
        }

        finish_run(conn, run_id,
                   n_fetched=n_fetched, n_new=n_new, n_generated=n_generated,
                   n_applied=n_applied, n_errors=len(errors),
                   summary={"matches": len(matches), **diagnostics})

    return {
        "run_id": run_id,
        "n_fetched": n_fetched, "n_new": n_new,
        "n_generated": n_generated, "n_applied": n_applied,
        "n_errors": len(errors),
        "diagnostics": diagnostics,
    }


def run_with_failure_alerts(config: Config, secrets: Secrets) -> dict[str, Any]:
    """Wrap run_once: any uncaught exception → failure email + re-raise."""
    try:
        return run_once(config, secrets)
    except Exception as e:
        send_failure_alert(secrets, str(e), traceback.format_exc())
        raise


def daily_digest(config: Config, secrets: Secrets) -> None:
    """Send a digest of everything generated in the last 24h. Used by the daily cron."""
    from datetime import timedelta
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    with connect() as conn:
        rows = jobs_by_status(conn, JobStatus.GENERATED, since=since)

    matches = []
    for r in rows:
        channel = apply_channel(r)
        ats_name = apply_channel_ats_name(r["url"] if "url" in r.keys() else None) if channel == "form" else None
        matches.append({
            "job": {"title": r["title"], "company": r["company"],
                    "location": None, "url": r["url"], "source": r["source"]},
            "score": r["score"], "reason": r["score_reason"] or "",
            "output_dir": r["output_dir"], "cover_letter_html": "",
            "apply_status": None,
            "apply_email": r["apply_email"] if "apply_email" in r.keys() else None,
            "apply_url": r["url"],
            "apply_channel": channel,
            "apply_channel_ats_name": ats_name,
        })
    send_digest(secrets, matches, [], datetime.now(tz=timezone.utc))
