"""Pipeline orchestrator: scrape → score → generate → (apply) → notify."""
from __future__ import annotations

import traceback
import inspect
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import structlog

from .applier import apply_to_job
from .config import Config, Secrets
from .enrichment.runner import enrich_new_postings
from .generators import generate_application_package, generate_documents
from .models import JobPosting, JobStatus
from .notify import send_digest, send_failure_alert
from .profile import Profile, load_base_cv, load_profile
from .scoring import CannotScore, llm_score, llm_score_tailored, passes_heuristic
from .scrapers import REGISTRY
from .state import (
    apply_channel, apply_channel_ats_name, connect, finish_run, jobs_by_status,
    jobs_needing_enrichment, mark_run_stopped, record_application, start_run,
    update_score_tailored, update_run_stage_progress, update_status, upsert_new,
    wait_while_paused,
)

log = structlog.get_logger()


def run_once(config: Config, secrets: Secrets) -> dict[str, Any]:
    """Single end-to-end pipeline pass. Returns a summary dict."""
    profile = load_profile()
    base_cv = load_base_cv()
    started = datetime.now(tz=timezone.utc)

    matches: list[dict] = []
    cannot_score_entries: list[dict] = []
    errors: list[dict] = []
    n_fetched = n_new = n_generated = n_applied = 0
    n_enriched = n_enrichment_failed = 0
    n_filtered = n_scored = n_below_threshold = n_score_failed = 0
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
        update_run_stage_progress(
            conn, run_id, "scrape",
            total=len(scrape_queries), started=0, completed=0, failed=0, skipped=0,
            current_index=0, current_item_id=None, current_label=None,
        )
        scrape_index = 0
        scrape_failed = 0
        for name, src_cfg in config.sources.items():
            if not src_cfg.enabled:
                continue
            scraper = REGISTRY.get(name)
            if scraper is None:
                errors.append({"source": name, "error": "no scraper registered"})
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
                    metadata={
                        "hits_so_far": n_fetched,
                        "new_so_far": n_new,
                    },
                )
                try:
                    fetched = scraper.fetch(query)
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

        # 2) Enrich postings missing a body fetch: every freshly-scraped job
        # in this run, plus every seen_jobs row where description_scraped IS
        # NULL (scraped before enrichment was wired in — dedup would otherwise
        # exclude them forever). Capped per run to keep first-launch bounded.
        to_enrich_by_id: dict[str, JobPosting] = dict(all_fetched_by_id)
        for stale in jobs_needing_enrichment(conn):
            to_enrich_by_id.setdefault(stale.id, stale)
        cap = config.enrichment.per_run_cap
        to_enrich = list(to_enrich_by_id.values())[:cap]
        enrichment = enrich_new_postings(to_enrich, conn, registry=REGISTRY, run_id=run_id)
        n_enriched = enrichment.n_succeeded
        n_enrichment_failed = enrichment.n_failed

        # 3) Score (heuristic → LLM)
        # Retry pending scraped jobs from previous runs as well, so transient
        # LLM/network failures do not leave jobs stuck in "scraped" forever.
        # `to_score` values are (job, description_scraped) — the flag must be
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
                desc_scraped = bool(row["description_scraped"])
                to_score[row["id"]] = (candidate, desc_scraped)
            except Exception as e:
                errors.append({"source": row["source"], "error": f"decode: {e}"})

        to_generate: list[tuple[JobPosting, int, str]] = []
        score_candidates = list(to_score.values())[: config.max_jobs_per_run]
        update_run_stage_progress(
            conn, run_id, "scoring",
            total=len(score_candidates), started=0, completed=0, failed=0,
            current_index=0, current_label=None,
        )
        for idx, (job, desc_scraped) in enumerate(score_candidates, start=1):
            if stopped := _continue_or_stop():
                return stopped
            update_run_stage_progress(
                conn, run_id, "scoring",
                total=len(score_candidates), started=idx, current_index=idx,
                current_item_id=job.id,
                current_label=f"{job.title} @ {job.company}",
            )
            ok, reason = passes_heuristic(job, profile)
            if not ok:
                # No score is assigned here: heuristic filtering happens *before*
                # the LLM runs, and PRD §7.5 reserves the `score` column for
                # actual LLM output. Leaving it NULL preserves the invariant
                # that "score IS NOT NULL ⇒ preconditions passed".
                update_status(conn, job.id, JobStatus.FILTERED, reason=reason)
                n_filtered += 1
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold + n_filtered + n_cannot_score,
                    skipped=n_filtered,
                )
                blocker_counts[reason or "filtered by heuristic"] += 1
                continue
            try:
                result = llm_score(
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
                cannot_score_entries.append({
                    "job": job.model_dump(mode="json"),
                    "status": new_status.value,
                    "reason": reason,
                })
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold + n_filtered + n_cannot_score,
                    failed=n_cannot_score + n_score_failed,
                )
                continue
            except Exception as e:
                log.exception("score_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"score: {e}"})
                n_score_failed += 1
                err_label = f"scoring error: {type(e).__name__}"
                blocker_counts[err_label] += 1
                # No score recorded: the LLM call failed, so per PRD §7.5
                # there is no trustworthy number. Status drops back to
                # SCRAPED so the next run retries.
                update_status(conn, job.id, JobStatus.SCRAPED, reason=err_label)
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold + n_filtered + n_cannot_score,
                    failed=n_cannot_score + n_score_failed,
                )
                continue
            if result.score < config.score_threshold:
                update_status(conn, job.id, JobStatus.BELOW_THRESHOLD,
                              score=result.score, reason=result.reason)
                n_below_threshold += 1
                score_values.append(result.score)
                update_run_stage_progress(
                    conn, run_id, "scoring",
                    completed=n_scored + n_below_threshold + n_filtered + n_cannot_score,
                    failed=n_cannot_score + n_score_failed,
                )
                continue
            update_status(conn, job.id, JobStatus.SCORED,
                          score=result.score, reason=result.reason)
            n_scored += 1
            score_values.append(result.score)
            to_generate.append((job, result.score, result.reason))
            update_run_stage_progress(
                conn, run_id, "scoring",
                completed=n_scored + n_below_threshold + n_filtered + n_cannot_score,
                failed=n_cannot_score + n_score_failed,
            )

        # 4) Generate
        update_run_stage_progress(
            conn, run_id, "generation",
            total=len(to_generate), started=0, completed=0, failed=0,
            current_index=0, current_label=None,
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
            # do one tiny SELECT per match — cheap and avoids threading the
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

            if score < config.digest.generate_docs_above_score:
                matches.append(entry)
                generation_skipped += 1
                update_run_stage_progress(
                    conn, run_id, "generation",
                    completed=n_generated,
                    skipped=generation_skipped,
                    failed=generation_failed,
                )
                continue

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

            entry.update({
                "output_dir": docs.output_dir,
                "cover_letter_html": docs.cover_letter_html,
            })

            # 4b) Rescore the posting using the tailored CV + cover letter
            # so the dashboard can show "did tailoring lift the fit?" — a
            # measurement-only call. Persisted to a parallel column;
            # the original `score` is unchanged. A failure here is logged
            # but does NOT abort the application step that follows.
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
