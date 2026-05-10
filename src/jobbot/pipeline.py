"""Pipeline orchestrator: scrape → score → generate → (apply) → notify."""
from __future__ import annotations

import traceback
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import structlog

from .applier import apply_to_job
from .config import Config, Secrets
from .enrichment.runner import enrich_new_postings
from .generators import generate_documents
from .models import JobPosting, JobStatus
from .notify import send_digest, send_failure_alert
from .profile import Profile, load_base_cv, load_profile
from .scoring import llm_score, passes_heuristic
from .scrapers import REGISTRY
from .state import (
    connect, finish_run, jobs_by_status, record_application,
    start_run, update_status, upsert_new,
)

log = structlog.get_logger()


def run_once(config: Config, secrets: Secrets) -> dict[str, Any]:
    """Single end-to-end pipeline pass. Returns a summary dict."""
    profile = load_profile()
    base_cv = load_base_cv()
    started = datetime.now(tz=timezone.utc)

    matches: list[dict] = []
    errors: list[dict] = []
    n_fetched = n_new = n_generated = n_applied = 0
    n_enriched = n_enrichment_failed = 0
    n_filtered = n_scored = n_below_threshold = n_score_failed = 0
    blocker_counts: Counter[str] = Counter()
    score_values: list[int] = []
    per_source_fetched: Counter[str] = Counter()
    per_source_new: Counter[str] = Counter()
    fetched_ids: list[str] = []

    with connect() as conn:
        run_id = start_run(conn)

        # 1) Scrape
        all_new: list[JobPosting] = []
        all_fetched_by_id: dict[str, JobPosting] = {}
        for name, src_cfg in config.sources.items():
            if not src_cfg.enabled:
                continue
            scraper = REGISTRY.get(name)
            if scraper is None:
                errors.append({"source": name, "error": "no scraper registered"})
                continue
            for query in src_cfg.queries:
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
                except Exception as e:
                    log.exception("scraper_failed", source=name, query=query)
                    errors.append({"source": name, "error": f"{type(e).__name__}: {e}"})

        # 2) Enrich all fetched postings so every match in this run has a
        # persisted description payload (new and previously seen entries).
        enrichment = enrich_new_postings(list(all_fetched_by_id.values()), conn, registry=REGISTRY)
        n_enriched = enrichment.n_succeeded
        n_enrichment_failed = enrichment.n_failed

        # 3) Score (heuristic → LLM)
        # Retry pending scraped jobs from previous runs as well, so transient
        # LLM/network failures do not leave jobs stuck in "scraped" forever.
        to_score: dict[str, JobPosting] = {j.id: j for j in enrichment.enriched_jobs}
        for row in jobs_by_status(conn, JobStatus.SCRAPED):
            if row["id"] in to_score:
                continue
            try:
                candidate = JobPosting.model_validate_json(row["raw_json"])
                if len((candidate.description or "").split()) >= 100:
                    to_score[row["id"]] = candidate
            except Exception as e:
                errors.append({"source": row["source"], "error": f"decode: {e}"})

        to_generate: list[tuple[JobPosting, int, str]] = []
        for job in list(to_score.values())[: config.max_jobs_per_run]:
            ok, reason = passes_heuristic(job, profile)
            if not ok:
                update_status(conn, job.id, JobStatus.FILTERED, score=0, reason=reason)
                n_filtered += 1
                blocker_counts[reason or "filtered by heuristic"] += 1
                continue
            try:
                result = llm_score(job, profile, secrets)
            except Exception as e:
                log.exception("score_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"score: {e}"})
                n_score_failed += 1
                err_label = f"scoring error: {type(e).__name__}"
                blocker_counts[err_label] += 1
                update_status(conn, job.id, JobStatus.SCRAPED, score=0, reason=err_label)
                continue
            if result.score < config.score_threshold:
                update_status(conn, job.id, JobStatus.BELOW_THRESHOLD,
                              score=result.score, reason=result.reason)
                n_below_threshold += 1
                score_values.append(result.score)
                continue
            update_status(conn, job.id, JobStatus.SCORED,
                          score=result.score, reason=result.reason)
            n_scored += 1
            score_values.append(result.score)
            to_generate.append((job, result.score, result.reason))

        # 4) Generate
        for job, score, reason in to_generate:
            entry: dict[str, Any] = {
                "job": job.model_dump(mode="json"),
                "score": score,
                "reason": reason,
                "output_dir": None,
                "cover_letter_html": "",
                "apply_status": None,
            }

            if score < config.digest.generate_docs_above_score:
                matches.append(entry)
                continue

            try:
                docs = generate_documents(job, profile, base_cv, secrets, config)
                update_status(conn, job.id, JobStatus.GENERATED, output_dir=docs.output_dir)
                n_generated += 1
            except Exception as e:
                log.exception("generate_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"generate: {e}"})
                continue

            entry.update({
                "output_dir": docs.output_dir,
                "cover_letter_html": docs.cover_letter_html,
            })

            # 5) Auto-apply (opt-in per source)
            src_cfg = config.sources.get(job.source)
            if src_cfg and src_cfg.auto_submit and n_applied < config.apply.per_run_limit:
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
            send_digest(secrets, matches, errors, started)
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

    matches = [{
        "job": {"title": r["title"], "company": r["company"],
                "location": None, "url": r["url"], "source": r["source"]},
        "score": r["score"], "reason": r["score_reason"] or "",
        "output_dir": r["output_dir"], "cover_letter_html": "",
        "apply_status": None,
    } for r in rows]
    send_digest(secrets, matches, [], datetime.now(tz=timezone.utc))
