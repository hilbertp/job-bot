"""Pipeline orchestrator: scrape → score → generate → (apply) → notify."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any

import structlog

from .applier import apply_to_job
from .config import Config, Secrets
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

    with connect() as conn:
        run_id = start_run(conn)

        # 1) Scrape
        all_new: list[JobPosting] = []
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
                    n_fetched += len(fetched)
                    new = upsert_new(conn, fetched)
                    all_new.extend(new)
                    n_new += len(new)
                except Exception as e:
                    log.exception("scraper_failed", source=name, query=query)
                    errors.append({"source": name, "error": f"{type(e).__name__}: {e}"})

        # 2) Score (heuristic → LLM)
        # Retry pending scraped jobs from previous runs as well, so transient
        # LLM/network failures do not leave jobs stuck in "scraped" forever.
        to_score: dict[str, JobPosting] = {j.id: j for j in all_new}
        for row in jobs_by_status(conn, JobStatus.SCRAPED):
            if row["id"] in to_score:
                continue
            try:
                to_score[row["id"]] = JobPosting.model_validate_json(row["raw_json"])
            except Exception as e:
                errors.append({"source": row["source"], "error": f"decode: {e}"})

        to_generate: list[tuple[JobPosting, int, str]] = []
        for job in list(to_score.values())[: config.max_jobs_per_run]:
            ok, reason = passes_heuristic(job, profile)
            if not ok:
                update_status(conn, job.id, JobStatus.FILTERED, reason=reason)
                continue
            try:
                result = llm_score(job, profile, secrets)
            except Exception as e:
                log.exception("score_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"score: {e}"})
                continue
            if result.score < config.score_threshold:
                update_status(conn, job.id, JobStatus.BELOW_THRESHOLD,
                              score=result.score, reason=result.reason)
                continue
            update_status(conn, job.id, JobStatus.SCORED,
                          score=result.score, reason=result.reason)
            to_generate.append((job, result.score, result.reason))

        # 3) Generate
        for job, score, reason in to_generate:
            try:
                docs = generate_documents(job, profile, base_cv, secrets, config)
                update_status(conn, job.id, JobStatus.GENERATED, output_dir=docs.output_dir)
                n_generated += 1
            except Exception as e:
                log.exception("generate_failed", job_id=job.id)
                errors.append({"source": job.source, "error": f"generate: {e}"})
                continue

            entry: dict[str, Any] = {
                "job": job.model_dump(mode="json"),
                "score": score, "reason": reason,
                "output_dir": docs.output_dir,
                "cover_letter_html": docs.cover_letter_html,
                "apply_status": None,
            }

            # 4) Auto-apply (opt-in per source)
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

        # 5) Notify
        try:
            send_digest(secrets, matches, errors, started)
        except Exception as e:
            log.exception("digest_send_failed")
            errors.append({"source": "notify", "error": str(e)})

        finish_run(conn, run_id,
                   n_fetched=n_fetched, n_new=n_new, n_generated=n_generated,
                   n_applied=n_applied, n_errors=len(errors),
                   summary={"matches": len(matches)})

    return {
        "n_fetched": n_fetched, "n_new": n_new,
        "n_generated": n_generated, "n_applied": n_applied,
        "n_errors": len(errors),
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
