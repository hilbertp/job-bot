"""Web dashboard for job-bot pipeline monitoring."""
from __future__ import annotations

import json
import re
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from .config import REPO_ROOT
from .models import JobStatus
from .state import (
    apply_channel, apply_channel_ats_name, connect, mark_run_stopped,
    usable_apply_route,
    llm_usage_summary, request_run_control, run_control_state,
    run_stage_progress,
)

EXPORT_STATUSES = ("scored", "below_threshold", "filtered", "generated", "scraped")

_TEMPLATES_DIR = Path(__file__).with_name("templates")
app = Flask(__name__, template_folder=str(_TEMPLATES_DIR))
_RUN_TRIGGER_LOCK = threading.Lock()
_RUN_TRIGGER_STATE: dict[str, str | int | None] = {
    "status": "idle",
    "run_id": None,
    "error": None,
}
_MIN_USABLE_DESCRIPTION_WORDS = 100


SALARY_PATTERNS = [
    re.compile(r"(?:EUR|USD|GBP|CHF|CAD|AUD|\$|€|£)\s?\d{2,3}(?:[\.,]\d{3})?(?:\s?[kK])?(?:\s?[-–to]{1,3}\s?(?:EUR|USD|GBP|CHF|CAD|AUD|\$|€|£)?\s?\d{2,3}(?:[\.,]\d{3})?(?:\s?[kK])?)?", re.IGNORECASE),
    re.compile(r"\d{2,3}(?:[\.,]\d{3})?\s?[kK]\s?(?:[-–to]{1,3})\s?\d{2,3}(?:[\.,]\d{3})?\s?[kK]", re.IGNORECASE),
]

SENIORITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bintern(ship)?\b", re.IGNORECASE), "Intern"),
    (re.compile(r"\bjunior\b|\bjr\.?\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\bmid\b|\bmid-level\b", re.IGNORECASE), "Mid"),
    (re.compile(r"\bsenior\b|\bsr\.?\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\bstaff\b", re.IGNORECASE), "Staff"),
    (re.compile(r"\bprincipal\b", re.IGNORECASE), "Principal"),
    (re.compile(r"\blead\b", re.IGNORECASE), "Lead"),
    (re.compile(r"\bhead\b", re.IGNORECASE), "Head"),
    (re.compile(r"\bdirector\b", re.IGNORECASE), "Director"),
    (re.compile(r"\bvp\b|\bvice president\b", re.IGNORECASE), "VP"),
]


_BREAKDOWN_TEXT_RE = re.compile(
    r"role\s*=\s*(\d+)\s*,\s*skills\s*=\s*(\d+)\s*,\s*location\s*=\s*(\d+)\s*,\s*seniority\s*=\s*(\d+)",
    re.IGNORECASE,
)


def _parse_score_breakdown(
    breakdown_json: str | None, reason_text: str | None,
) -> dict | None:
    """Return {role, skills, location, seniority} or None.

    Prefers the structured JSON column (new rows). Falls back to parsing
    the legacy "role=X, skills=Y, location=Z, seniority=W" prefix that
    used to be embedded in score_reason (old rows). Returns None when
    neither source has data, the dashboard shows "," in that case."""
    if breakdown_json:
        try:
            obj = json.loads(breakdown_json)
            if isinstance(obj, dict) and all(
                k in obj for k in ("role", "skills", "location", "seniority")
            ):
                return {
                    "role": int(obj["role"]),
                    "skills": int(obj["skills"]),
                    "location": int(obj["location"]),
                    "seniority": int(obj["seniority"]),
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    if reason_text:
        m = _BREAKDOWN_TEXT_RE.search(reason_text)
        if m:
            return {
                "role": int(m.group(1)),
                "skills": int(m.group(2)),
                "location": int(m.group(3)),
                "seniority": int(m.group(4)),
            }
    return None


def _extract_expected_salary(title: str, description: str) -> str:
    text = f"{title}\n{description}"
    for pattern in SALARY_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = " ".join(match.group(0).split())
            if re.search(r"[kK]|\d{1,3},\d{3}", candidate):
                return candidate
            nums = re.findall(r"\d+", candidate)
            if nums and int(nums[0]) >= 1000:
                return candidate
    return "not specified"


def _extract_seniority_required(title: str, description: str) -> str:
    text = f"{title}\n{description}"
    for pattern, label in SENIORITY_PATTERNS:
        if pattern.search(text):
            return label
    return "not specified"


# Funnel percentage thresholds. Red < 20%, amber 20-50%, green 50%+.
_RETENTION_AMBER_MIN = 20
_RETENTION_GREEN_MIN = 50


def _percentage_color(pct: float | None) -> str:
    """Bucket a funnel percentage into red / amber / green."""
    if pct is None:
        return "neutral"
    if pct < _RETENTION_AMBER_MIN:
        return "red"
    if pct < _RETENTION_GREEN_MIN:
        return "amber"
    return "green"


def _count_interviewed(conn) -> int:
    """Applications that reached interview proof.

    Rejections are proof level 5 but should not inflate the Interviewed card,
    so count the explicit interview status or level 4 only.
    """
    cur = conn.execute(
        "SELECT COUNT(*) FROM applications "
        "WHERE status = ? OR proof_level = 4",
        (JobStatus.INTERVIEW_INVITED.value,),
    )
    return cur.fetchone()[0]


def compute_funnel(conn) -> list[dict]:
    """Return the 4-stage outcome funnel for the top dashboard strip.

    The all-time `Total` card was dropped because the meaningful "what was
    scraped" number lives in the run-scoped Stage 1 panel; carrying both at
    the top of the page was confusing. Stages and their SQL:

      Suitable     seen_jobs.score >= 70                COUNT(*)
      Tailored     seen_jobs.output_dir IS NOT NULL     COUNT(*)
      Applied      applications.submitted = 1           COUNT(*)
      Interviewed  applications.proof_level >= 4        COUNT(*), M5

    Percentages are omitted: with no Total denominator there is no
    consistent base, and the absolute counts already convey the funnel
    shape.
    """
    suitable = conn.execute(
        "SELECT COUNT(*) FROM seen_jobs WHERE score >= 70"
    ).fetchone()[0]
    tailored = conn.execute(
        "SELECT COUNT(*) FROM seen_jobs WHERE output_dir IS NOT NULL"
    ).fetchone()[0]
    applied = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE submitted = 1"
    ).fetchone()[0]
    interviewed = _count_interviewed(conn)

    stages: list[tuple[str, int, str | None]] = [
        ("Suitable", suitable, None),
        ("Tailored", tailored, None),
        ("Applied", applied, None),
        ("Interviewed", interviewed, "M5"),
    ]

    return [
        {
            "label": label,
            "count": count,
            "pct_of_total": None,
            "percentage_color": _percentage_color(None),
            "pending_milestone": badge,
        }
        for label, count, badge in stages
    ]


def compute_activity_today(conn, *, now: datetime | None = None) -> dict:
    """Counts for the Recent Runs 'Activity today' subline.

    24-hour rolling window (consistent with the prior 'Last 24h' tile).
    `now` is injectable for deterministic tests.
    """
    now = now or datetime.now(tz=timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()

    posted = conn.execute(
        "SELECT COUNT(*) FROM seen_jobs WHERE first_seen_at >= ?", (since,),
    ).fetchone()[0]
    scored = conn.execute(
        "SELECT COUNT(*) FROM seen_jobs WHERE scored_at >= ?", (since,),
    ).fetchone()[0]
    applied = conn.execute(
        "SELECT COUNT(*) FROM applications "
        "WHERE submitted = 1 AND attempted_at >= ?", (since,),
    ).fetchone()[0]
    return {"posted": posted, "scored": scored, "applied": applied}


def compute_outcome_counts(conn) -> dict[str, int]:
    """Application outcome counts for the Stage 4 dashboard panel."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
    ).fetchall()
    by_status = {row["status"]: int(row["n"] or 0) for row in rows}
    waiting = (
        by_status.get(JobStatus.APPLY_SUBMITTED.value, 0)
        + by_status.get(JobStatus.WAITING_RESPONSE.value, 0)
    )
    return {
        "received": by_status.get(JobStatus.EMPLOYER_RECEIVED.value, 0),
        "waiting": waiting,
        "rejected": by_status.get(JobStatus.REJECTED.value, 0),
        "interview": by_status.get(JobStatus.INTERVIEW_INVITED.value, 0),
    }


@app.route("/")
def index():
    """Dashboard home page."""
    with connect() as conn:
        # Get status counts (kept for downstream consumers / per-stage panels)
        status_counts = {}
        for st in JobStatus:
            cur = conn.execute("SELECT COUNT(*) FROM seen_jobs WHERE status = ?", (st.value,))
            status_counts[st.value] = cur.fetchone()[0]

        # Get total jobs
        cur = conn.execute("SELECT COUNT(*) FROM seen_jobs")
        total_jobs = cur.fetchone()[0]

        # Total run count for the panel-header badge.
        total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

        # Get recent runs
        cur = conn.execute(
            """
            SELECT id, started_at, n_fetched, n_new, n_generated, n_applied, n_errors
            FROM runs
            ORDER BY started_at DESC
            LIMIT 5
            """
        )
        runs = [
            {
                "id": r[0],
                "timestamp": r[1],
                "timestamp_display": _format_readable_time(r[1]),
                "n_fetched": r[2],
                "n_new": r[3],
                "n_generated": r[4],
                "n_applied": r[5],
                "n_errors": r[6],
            }
            for r in cur.fetchall()
        ]

        funnel = compute_funnel(conn)
        activity_today = compute_activity_today(conn)
        outcome_counts = compute_outcome_counts(conn)

    applied_total = status_counts.get(JobStatus.APPLY_SUBMITTED.value, 0)

    return render_template("index.html",
                          status_counts=status_counts,
                          total_jobs=total_jobs,
                          total_runs=total_runs,
                          applied_total=applied_total,
                          funnel=funnel,
                          activity_today=activity_today,
                          outcome_counts=outcome_counts,
                          runs=runs)


@app.route("/api/jobs")
def api_jobs():
    """Get all jobs with optional filtering."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, company, source, status, score, score_reason, url
            FROM seen_jobs
            ORDER BY COALESCE(score, -1) DESC, first_seen_at DESC
            LIMIT 100
            """
        )
        jobs = [
            {
                "id": r[0],
                "title": r[1],
                "company": r[2],
                "location": r[3],
                "status": r[4],
                "score": r[5],
                "score_reason": r[6],
                "url": r[7],
            }
            for r in cur.fetchall()
        ]
    return jsonify(jobs)


@app.route("/api/positions")
def api_positions():
    """Get scraped positions with score and reason for dashboard table."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, company, source, status, score, score_reason, url, first_seen_at
            FROM seen_jobs
            ORDER BY first_seen_at DESC
            LIMIT 500
            """
        )
        rows = [
            {
                "id": r[0],
                "title": r[1],
                "company": r[2],
                "source": r[3],
                "status": r[4],
                "score": r[5] if r[5] is not None else 0,
                "score_reason": r[6] or "",
                "url": r[7],
                "first_seen_at": r[8],
            }
            for r in cur.fetchall()
        ]
    return jsonify(rows)


@app.route("/api/jobs/by-status/<status>")
def api_jobs_by_status(status: str):
    """Get jobs filtered by status."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, company, source, status, score, score_reason, url
            FROM seen_jobs
            WHERE status = ?
            ORDER BY COALESCE(score, -1) DESC, first_seen_at DESC
            LIMIT 50
            """,
            (status,),
        )
        jobs = [
            {
                "id": r[0],
                "title": r[1],
                "company": r[2],
                "location": r[3],
                "status": r[4],
                "score": r[5],
                "score_reason": r[6],
                "url": r[7],
            }
            for r in cur.fetchall()
        ]
    return jsonify(jobs)


@app.route("/api/runs")
def api_runs():
    """Get run history."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, started_at, n_fetched, n_new, n_generated, n_applied, n_errors
            FROM runs
            ORDER BY started_at DESC
            LIMIT 20
            """
        )
        runs = [
            {
                "id": r[0],
                "timestamp": r[1],
                "timestamp_display": _format_readable_time(r[1]),
                "n_fetched": r[2],
                "n_new": r[3],
                "n_generated": r[4],
                "n_applied": r[5],
                "n_errors": r[6],
            }
            for r in cur.fetchall()
        ]
    return jsonify(runs)


@app.route("/api/runs/trigger", methods=["POST"])
def api_trigger_run():
    """Start one pipeline run from the dashboard without blocking the request."""
    if not _RUN_TRIGGER_LOCK.acquire(blocking=False):
        return jsonify({
            "ok": False,
            "status": "already_running",
            "error": "pipeline run already in progress",
        }), 409

    _RUN_TRIGGER_STATE.update({"status": "running", "run_id": None, "error": None})

    def _worker() -> None:
        try:
            from .config import load_config, load_secrets
            from .pipeline import run_with_failure_alerts

            result = run_with_failure_alerts(load_config(), load_secrets())
            _RUN_TRIGGER_STATE.update({
                "status": "finished",
                "run_id": result.get("run_id"),
                "error": None,
            })
        except Exception:
            _RUN_TRIGGER_STATE.update({
                "status": "failed",
                "run_id": None,
                "error": traceback.format_exc(limit=3),
            })
        finally:
            _RUN_TRIGGER_LOCK.release()

    threading.Thread(target=_worker, name="jobbot-dashboard-run", daemon=True).start()
    return jsonify({"ok": True, "status": "started"}), 202


@app.route("/api/runs/<int:run_id>/control", methods=["POST"])
def api_run_control(run_id: int):
    """Cooperative run controls for the local dashboard.

    Pause/resume are picked up by pipeline checkpoint checks. Stop also marks
    the DB row finished so stale rows no longer look like active token spend.
    """
    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"pause", "resume", "stop"}:
        return jsonify({"ok": False, "error": "action must be pause, resume, or stop"}), 400

    with connect() as conn:
        row = conn.execute("SELECT id, finished_at FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            abort(404)
        if action == "pause":
            if row["finished_at"] is not None:
                return jsonify({"ok": False, "error": "run already finished"}), 409
            request_run_control(conn, run_id, "paused", reason="paused from dashboard")
        elif action == "resume":
            if row["finished_at"] is not None:
                return jsonify({"ok": False, "error": "run already finished"}), 409
            request_run_control(conn, run_id, "running", reason="resumed from dashboard")
        else:
            mark_run_stopped(conn, run_id, reason="stopped from dashboard")
        state = run_control_state(conn, run_id)

    return jsonify({"ok": True, "run_id": run_id, "action": action, **state})


@app.route("/runs/<int:run_id>")
def run_detail_page(run_id: int):
    """Run detail page with diagnostics and blockers.

    For an in-progress run (finished_at IS NULL) the summary_json doesn't
    exist yet, so the page falls back to counts derived live from `seen_jobs`
    rows whose first_seen_at falls inside the run window. The template
    auto-refreshes every 5s while the run is still active.
    """
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, started_at, finished_at, n_fetched, n_new, n_generated, n_applied, n_errors, summary_json
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        )
        row = cur.fetchone()
        if row is None:
            abort(404)

        summary: dict = {}
        if row[8]:
            try:
                parsed = json.loads(row[8])
                summary = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                summary = {}

        diagnostics = dict(summary.get("stages", {})) if isinstance(summary.get("stages"), dict) else {}
        score_stats = summary.get("score_stats", {}) if isinstance(summary.get("score_stats"), dict) else {}
        blockers = summary.get("top_blockers", []) if isinstance(summary.get("top_blockers"), list) else []
        control_state = run_control_state(conn, run_id)

        in_progress = row[2] is None
        if not in_progress and control_state.get("requested_state") != "stopped":
            control_state = {
                "requested_state": "finished",
                "reason": "run completed",
                "updated_at": row[2],
            }
        if in_progress:
            started_at = row[1]
            live_counts = conn.execute(
                """
                SELECT
                    COUNT(*) AS fetched,
                    SUM(CASE WHEN description_scraped = 1 THEN 1 ELSE 0 END) AS enriched,
                    SUM(CASE WHEN description_scraped = 0 THEN 1 ELSE 0 END) AS enrichment_failed,
                    SUM(CASE WHEN description_scraped IS NOT NULL THEN 1 ELSE 0 END) AS enrichment_attempted,
                    SUM(CASE WHEN status = 'scraped'         THEN 1 ELSE 0 END) AS scraped,
                    SUM(CASE WHEN status = 'filtered'        THEN 1 ELSE 0 END) AS filtered,
                    SUM(CASE WHEN status = 'scored'          THEN 1 ELSE 0 END) AS scored,
                    SUM(CASE WHEN status = 'below_threshold' THEN 1 ELSE 0 END) AS below,
                    SUM(CASE WHEN status = 'generated'       THEN 1 ELSE 0 END) AS generated
                FROM seen_jobs
                WHERE first_seen_at >= ?
                """,
                (started_at,),
            ).fetchone()
            if live_counts:
                fetched = int(live_counts[0] or 0)
                attempted = int(live_counts[3] or 0)
                diagnostics["fetched"] = fetched
                diagnostics["new"] = fetched
                diagnostics["enriched"] = int(live_counts[1] or 0)
                diagnostics["enrichment_failed"] = int(live_counts[2] or 0)
                diagnostics["enrichment_attempted"] = attempted
                diagnostics["enrichment_pending"] = max(0, fetched - attempted)
                diagnostics["filtered"] = int(live_counts[5] or 0)
                diagnostics["scored"] = int(live_counts[6] or 0)
                diagnostics["below_threshold"] = int(live_counts[7] or 0)
                diagnostics["generated"] = int(live_counts[8] or 0)

        portal_payload = _portal_payload_for_run(conn, (row[0], row[1], row[2], row[8]))
        progress_rows = run_stage_progress(conn, run_id)
        usage_summary = llm_usage_summary(conn, run_id)

    portal_rows = sorted(
        (
            {
                "source": source,
                "hits": hits,
                **(portal_payload["per_portal_description"].get(source) or {
                    "total": 0, "with_description": 0, "percent_with_description": 0.0,
                }),
                **(portal_payload["per_portal_enrichment"].get(source) or {
                    "enriched": 0, "no_description": 0, "attempted": 0, "pending": 0,
                }),
            }
            for source, hits in portal_payload["per_portal"].items()
        ),
        key=lambda r: r["hits"],
        reverse=True,
    )
    if not progress_rows:
        progress_rows = _fallback_run_progress(portal_payload, diagnostics)
    progress_rows = _decorate_progress_rows(progress_rows, in_progress=in_progress)
    current_stage = _infer_current_stage(portal_payload["total"], diagnostics) if in_progress else None

    run_data = {
        "id": row[0],
        "started_at": row[1],
        "started_at_display": _format_readable_time(row[1]),
        "finished_at": row[2],
        "finished_at_display": _format_readable_time(row[2]) if row[2] else ",",
        "n_fetched": row[3],
        "n_new": row[4],
        "n_generated": row[5],
        "n_applied": row[6],
        "n_errors": row[7],
        "elapsed_sec": portal_payload["elapsed_sec"],
    }
    return render_template(
        "run_detail.html",
        run=run_data,
        in_progress=in_progress,
        current_stage=current_stage,
        control_state=control_state,
        stages=diagnostics,
        progress_rows=progress_rows,
        llm_usage=usage_summary,
        portal_rows=portal_rows,
        portal_total=portal_payload["total"],
        portal_pct_with_description=portal_payload["percent_with_description"],
        enrichment_progress=portal_payload["enrichment_progress"],
        score_stats=score_stats,
        blockers=blockers,
    )


@app.route("/jobs")
def jobs_page():
    """Jobs listing page."""
    return render_template("jobs.html")


@app.route("/runs")
def runs_page():
    """Run history page."""
    return render_template("runs.html")


@app.route("/api/pipeline-funnel")
def api_pipeline_funnel():
    """Get pipeline funnel breakdown showing job attrition at each stage."""
    with connect() as conn:
        # Get latest run
        cur = conn.execute(
            "SELECT id, n_fetched, started_at FROM runs ORDER BY id DESC LIMIT 1"
        )
        latest_run = cur.fetchone()
        if not latest_run:
            return jsonify({"error": "No runs found"}), 404
        
        run_id, n_fetched, started_at = latest_run
        
        # Get status counts for jobs from this run
        cur = conn.execute(
            """
            SELECT status, COUNT(*) 
            FROM seen_jobs 
            WHERE first_seen_at >= ?
            GROUP BY status
            """,
            (started_at,)
        )
        status_counts = {row[0]: row[1] for row in cur.fetchall()}
    
    return jsonify({
        "run_id": run_id,
        "fetched": n_fetched,
        "filtered": status_counts.get("filtered", 0),
        "below_threshold": status_counts.get("below_threshold", 0),
        "scored": status_counts.get("scored", 0),
        "generated": status_counts.get("generated", 0),
    })


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _posted_days_ago(first_seen_iso: str | None, posted_at_iso: str | None) -> int | None:
    """Return integer days since the posting first appeared. Prefers
    the posting's own posted_at (more accurate when scrapers extract
    it); falls back to our first_seen_at (within 24h of real post date
    for daily-running scrapers).

    Returns None when neither timestamp is parseable, so the UI can
    render a "?" or omit the badge entirely."""
    candidate = posted_at_iso or first_seen_iso
    dt = _parse_iso(candidate) if candidate else None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(tz=timezone.utc) - dt
    return max(0, delta.days)


def _format_readable_time(ts: str | None) -> str:
    """Human display for ISO timestamps stored in the DB.

    The DB keeps UTC-ish ISO strings for machine use; dashboard labels should
    be compact and readable in the machine's local timezone.
    """
    dt = _parse_iso(ts)
    if dt is None:
        return ","
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone()
    label = f"{local_dt.strftime('%b')} {local_dt.day}, {local_dt.year} {local_dt:%H:%M}"
    tzname = local_dt.tzname()
    return f"{label} {tzname}" if tzname else label


def _decorate_progress_rows(rows: list[dict], *, in_progress: bool) -> list[dict]:
    out = []
    for row in rows:
        total = int(row.get("total") or 0)
        completed = int(row.get("completed") or 0)
        failed = int(row.get("failed") or 0)
        skipped = int(row.get("skipped") or 0)
        started = int(row.get("started") or 0)
        current_index = int(row.get("current_index") or 0)
        if (
            not in_progress
            and total
            and started >= total
            and completed + failed + skipped < total
        ):
            skipped = max(0, total - completed - failed)
        done = min(total, completed + failed + skipped) if total else completed + failed + skipped
        pct = round(done / total * 100.0, 1) if total else 0.0
        item_n = current_index or done
        decorated = dict(row)
        decorated.update({
            "skipped": skipped,
            "done": done,
            "pct": pct,
            "item_n": item_n,
            "display_total": total,
            "active": bool(in_progress and done < total),
        })
        out.append(decorated)
    return out


def _fallback_run_progress(portal_payload: dict, stages: dict) -> list[dict]:
    """Progress rows for runs that predate explicit progress instrumentation."""
    total = int(portal_payload.get("total") or stages.get("fetched") or 0)
    enrichment = portal_payload.get("enrichment_progress") or {}
    enriched = int(enrichment.get("enriched") or stages.get("enriched") or 0)
    no_desc = int(enrichment.get("no_description") or stages.get("enrichment_failed") or 0)
    enrichment_attempted = int(enrichment.get("attempted") or enriched + no_desc)
    scoring_done = (
        int(stages.get("scored", 0) or 0)
        + int(stages.get("below_threshold", 0) or 0)
        + int(stages.get("filtered", 0) or 0)
        + int(stages.get("cannot_score", 0) or 0)
        + int(stages.get("score_failed", 0) or 0)
    )
    return [
        {
            "stage": "scrape",
            "total": total,
            "started": total,
            "completed": total,
            "failed": 0,
            "skipped": 0,
            "current_index": total,
            "current_item_id": None,
            "current_label": None,
            "metadata": {"source": "derived from seen_jobs"},
        },
        {
            "stage": "enrichment",
            "total": total,
            "started": enrichment_attempted,
            "completed": enriched,
            "failed": no_desc,
            "skipped": 0,
            "current_index": enrichment_attempted,
            "current_item_id": None,
            "current_label": None,
            "metadata": {"source": "derived from description_scraped"},
        },
        {
            "stage": "scoring",
            "total": enriched,
            "started": scoring_done,
            "completed": int(stages.get("scored", 0) or 0) + int(stages.get("below_threshold", 0) or 0),
            "failed": int(stages.get("cannot_score", 0) or 0) + int(stages.get("score_failed", 0) or 0),
            "skipped": int(stages.get("filtered", 0) or 0),
            "current_index": scoring_done,
            "current_item_id": None,
            "current_label": None,
            "metadata": {"source": "derived from statuses"},
        },
        {
            "stage": "generation",
            "total": int(stages.get("scored", 0) or 0),
            "started": int(stages.get("generated", 0) or 0),
            "completed": int(stages.get("generated", 0) or 0),
            "failed": 0,
            "skipped": 0,
            "current_index": int(stages.get("generated", 0) or 0),
            "current_item_id": None,
            "current_label": None,
            "metadata": {"source": "derived from statuses"},
        },
    ]


def _description_counts_by_source(conn, *, ids: list[str] | None = None,
                                  since: str | None = None) -> dict[str, dict[str, float | int]]:
    """Group seen_jobs by source and count rows with non-empty descriptions.

    Either `ids` (an explicit id list, used when the run summary recorded
    fetched_ids) or `since` (a started_at timestamp, used for in-progress
    runs) must be provided. Returns the per-source breakdown shape the
    portal-hits API ships to the dashboard.
    """
    if ids:
        placeholders = ",".join("?" * len(ids))
        query = f"""
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN description_word_count IS NOT NULL
                             AND description_word_count >= ?
                            THEN 1 ELSE 0 END) AS with_description
            FROM seen_jobs
            WHERE id IN ({placeholders})
            GROUP BY source
        """
        rows = conn.execute(query, (_MIN_USABLE_DESCRIPTION_WORDS, *tuple(ids))).fetchall()
    elif since:
        rows = conn.execute(
            """
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN description_word_count IS NOT NULL
                             AND description_word_count >= ?
                            THEN 1 ELSE 0 END) AS with_description
            FROM seen_jobs
            WHERE first_seen_at >= ?
            GROUP BY source
            """,
            (_MIN_USABLE_DESCRIPTION_WORDS, since),
        ).fetchall()
    else:
        return {}

    out: dict[str, dict[str, float | int]] = {}
    for source, total, with_description in rows:
        total_i = int(total or 0)
        with_desc_i = int(with_description or 0)
        pct = (with_desc_i / total_i * 100.0) if total_i else 0.0
        out[source] = {
            "total": total_i,
            "with_description": with_desc_i,
            "percent_with_description": round(pct, 1),
        }
    return out


def _enrichment_progress_by_source(conn, *, ids: list[str] | None = None,
                                   since: str | None = None) -> dict[str, dict[str, int]]:
    """Per-source enrichment status for live run visibility.

    `description_scraped` is NULL while the detail-page fetch has not been
    attempted, 1 when a usable body was saved, and 0 when the detail page did
    not produce a usable description.
    """
    if ids:
        placeholders = ",".join("?" * len(ids))
        query = f"""
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN description_scraped = 1 THEN 1 ELSE 0 END) AS enriched,
                   SUM(CASE WHEN description_scraped = 0 THEN 1 ELSE 0 END) AS no_description,
                   SUM(CASE WHEN description_scraped IS NOT NULL THEN 1 ELSE 0 END) AS attempted
            FROM seen_jobs
            WHERE id IN ({placeholders})
            GROUP BY source
        """
        rows = conn.execute(query, tuple(ids)).fetchall()
    elif since:
        rows = conn.execute(
            """
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN description_scraped = 1 THEN 1 ELSE 0 END) AS enriched,
                   SUM(CASE WHEN description_scraped = 0 THEN 1 ELSE 0 END) AS no_description,
                   SUM(CASE WHEN description_scraped IS NOT NULL THEN 1 ELSE 0 END) AS attempted
            FROM seen_jobs
            WHERE first_seen_at >= ?
            GROUP BY source
            """,
            (since,),
        ).fetchall()
    else:
        return {}

    out: dict[str, dict[str, int]] = {}
    for source, total, enriched, no_description, attempted in rows:
        total_i = int(total or 0)
        attempted_i = int(attempted or 0)
        out[source] = {
            "total": total_i,
            "enriched": int(enriched or 0),
            "no_description": int(no_description or 0),
            "attempted": attempted_i,
            "pending": max(0, total_i - attempted_i),
        }
    return out


def _empty_portal_payload() -> dict:
    return {
        "run_id": None,
        "started_at": None,
        "finished_at": None,
        "in_progress": False,
        "elapsed_sec": 0,
        "per_portal": {},
        "per_portal_description": {},
        "per_portal_enrichment": {},
        "enrichment_progress": {
            "total": 0,
            "attempted": 0,
            "enriched": 0,
            "no_description": 0,
            "pending": 0,
            "percent_attempted": 0.0,
            "percent_enriched": 0.0,
        },
        "total": 0,
        "total_with_description": 0,
        "percent_with_description": 0.0,
    }


def _portal_payload_for_run(conn, run_row) -> dict:
    """Build the portal-hits payload for a runs-table row.

    Single source of truth shared by /api/latest-run-portal-hits and the
    server-rendered run-detail page. `run_row` is the tuple
    (id, started_at, finished_at, summary_json).
    """
    run_id, started_at, finished_at, summary_json = run_row
    in_progress = finished_at is None

    try:
        summary = json.loads(summary_json or "{}")
    except json.JSONDecodeError:
        summary = {}

    per_portal: dict[str, int] = {}
    if isinstance(summary, dict) and isinstance(summary.get("per_source_fetched"), dict):
        per_portal = {k: int(v) for k, v in summary["per_source_fetched"].items()}
    else:
        rows = conn.execute(
            """
            SELECT source, COUNT(*) FROM seen_jobs
            WHERE first_seen_at >= ?
            GROUP BY source
            """,
            (started_at,),
        ).fetchall()
        per_portal = {r[0]: r[1] for r in rows}

    fetched_ids = summary.get("fetched_ids") if isinstance(summary, dict) else None
    if isinstance(fetched_ids, list) and fetched_ids:
        per_portal_desc = _description_counts_by_source(conn, ids=fetched_ids)
        per_portal_enrichment = _enrichment_progress_by_source(conn, ids=fetched_ids)
    else:
        per_portal_desc = _description_counts_by_source(conn, since=started_at)
        per_portal_enrichment = _enrichment_progress_by_source(conn, since=started_at)

    started_dt = _parse_iso(started_at)
    finished_dt = _parse_iso(finished_at)
    if started_dt is not None:
        end_dt = finished_dt or datetime.now(started_dt.tzinfo)
        elapsed_sec = max(0, int((end_dt - started_dt).total_seconds()))
    else:
        elapsed_sec = 0

    total_with_desc = sum(
        int(v.get("with_description", 0))
        for v in per_portal_desc.values()
        if isinstance(v, dict)
    )
    total_desc_denom = sum(
        int(v.get("total", 0))
        for v in per_portal_desc.values()
        if isinstance(v, dict)
    )
    pct_with_desc = round(total_with_desc / total_desc_denom * 100.0, 1) if total_desc_denom else 0.0
    total_enrichment = sum(
        int(v.get("total", 0))
        for v in per_portal_enrichment.values()
        if isinstance(v, dict)
    )
    enrichment_attempted = sum(
        int(v.get("attempted", 0))
        for v in per_portal_enrichment.values()
        if isinstance(v, dict)
    )
    enrichment_enriched = sum(
        int(v.get("enriched", 0))
        for v in per_portal_enrichment.values()
        if isinstance(v, dict)
    )
    enrichment_no_description = sum(
        int(v.get("no_description", 0))
        for v in per_portal_enrichment.values()
        if isinstance(v, dict)
    )
    enrichment_pending = max(0, total_enrichment - enrichment_attempted)

    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "in_progress": in_progress,
        "elapsed_sec": elapsed_sec,
        "per_portal": per_portal,
        "per_portal_description": per_portal_desc,
        "per_portal_enrichment": per_portal_enrichment,
        "enrichment_progress": {
            "total": total_enrichment,
            "attempted": enrichment_attempted,
            "enriched": enrichment_enriched,
            "no_description": enrichment_no_description,
            "pending": enrichment_pending,
            "percent_attempted": round(enrichment_attempted / total_enrichment * 100.0, 1) if total_enrichment else 0.0,
            "percent_enriched": round(enrichment_enriched / total_enrichment * 100.0, 1) if total_enrichment else 0.0,
        },
        "total": sum(per_portal.values()),
        "total_with_description": total_with_desc,
        "percent_with_description": pct_with_desc,
    }


def _infer_current_stage(per_portal_total: int, stages: dict) -> str:
    """Best-effort label for the user: which pipeline step is the live run
    sitting in right now? Uses the same stage-count signals the
    pipeline writes to its summary, derived from seen_jobs when the
    summary hasn't been persisted yet.

    Order matters, pipeline.py runs them in this sequence and each step
    is gated by the previous one completing.
    """
    fetched = int(stages.get("fetched", per_portal_total) or 0)
    enriched = int(stages.get("enriched", 0) or 0)
    enrichment_failed = int(stages.get("enrichment_failed", 0) or 0)
    scored = int(stages.get("scored", 0) or 0)
    below = int(stages.get("below_threshold", 0) or 0)
    score_failed = int(stages.get("score_failed", 0) or 0)
    generated = int(stages.get("generated", 0) or 0)
    applied = int(stages.get("applied", 0) or 0)

    if fetched == 0:
        return "scraping"
    if enriched + enrichment_failed < fetched:
        return "enriching"
    if scored + below + score_failed < enriched:
        return "scoring"
    if generated == 0 and scored > 0:
        return "generating"
    if applied < generated:
        return "applying"
    return "finalising"


@app.route("/api/latest-run-portal-hits")
def api_latest_run_portal_hits():
    """Per-portal hit counts for one run.

    Defaults to the latest run; pass `?run_id=N` to scope to a specific run
    (used by the run-detail page so its live portal table reflects the run
    being viewed rather than whatever happens to be latest).

    Reads `per_source_fetched` from the run's summary_json when the run has
    finished and recorded its summary. For in-progress runs (or older rows
    that predate per_source_fetched), falls back to counting `seen_jobs`
    inserted since the run's `started_at`, keeping the table populated as
    the pipeline streams rows in. The response carries `in_progress` and
    `elapsed_sec` so the client can decide whether to keep polling.
    """
    from flask import request

    requested_id = request.args.get("run_id", type=int)
    with connect() as conn:
        if requested_id is not None:
            cur = conn.execute(
                """
                SELECT id, started_at, finished_at, summary_json
                FROM runs
                WHERE id = ?
                """,
                (requested_id,),
            )
        else:
            cur = conn.execute(
                """
                SELECT id, started_at, finished_at, summary_json
                FROM runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
        row = cur.fetchone()
        if not row:
            return jsonify(_empty_portal_payload())
        payload = _portal_payload_for_run(conn, row)

    return jsonify(payload)


@app.route("/api/shortlist")
def api_shortlist():
    """Stage-3 shortlist: jobs with score >= 70, with the tailored CV +
    cover letter inlined from disk so the dashboard can render them.

    Optional `?min_score=NN` overrides the 70 default.
    """
    from flask import request

    try:
        min_score = int(request.args.get("min_score", 70))
    except ValueError:
        min_score = 70

    with connect() as conn:
        cur = conn.execute(
            """
            SELECT s.id, s.title, s.company, s.source, s.status, s.score, s.score_reason,
                   s.url, s.output_dir, s.raw_json,
                   s.description_full, s.description_word_count,
                   s.seniority, s.salary_text, s.apply_email,
                   s.score_tailored, s.score_tailored_reason,
                   a.submitted, a.status, a.attempted_at, a.dry_run,
                   s.first_seen_at
            FROM seen_jobs s
            LEFT JOIN applications a ON a.job_id = s.id
            WHERE s.score IS NOT NULL AND s.score >= ?
            ORDER BY s.score DESC, s.first_seen_at DESC
            """,
            (min_score,),
        )
        rows = cur.fetchall()

    jobs = []
    for r in rows:
        description = r[10] or ""
        if not description and r[9]:
            try:
                payload = json.loads(r[9] or "{}")
                if isinstance(payload, dict):
                    description = str(payload.get("description", ""))
            except json.JSONDecodeError:
                description = ""

        cv_md = cover_letter_md = ""
        cv_html_path = cl_html_path = None
        cv_pdf_path = cl_pdf_path = None
        package_html_path = package_pdf_path = None
        if r[8]:
            out = Path(r[8])
            cv_md_path = out / "cv.md"
            cl_md_path = out / "cover_letter.md"
            if cv_md_path.exists():
                try:
                    cv_md = cv_md_path.read_text()
                except Exception:
                    cv_md = ""
            if cl_md_path.exists():
                try:
                    cover_letter_md = cl_md_path.read_text()
                except Exception:
                    cover_letter_md = ""
            if (out / "cv.html").exists():
                cv_html_path = str(out / "cv.html")
            if (out / "cover_letter.html").exists():
                cl_html_path = str(out / "cover_letter.html")
            if (out / "cv.pdf").exists():
                cv_pdf_path = str(out / "cv.pdf")
            if (out / "cover_letter.pdf").exists():
                cl_pdf_path = str(out / "cover_letter.pdf")
            if (out / "application_package.html").exists():
                package_html_path = str(out / "application_package.html")
            if (out / "application_package.pdf").exists():
                package_pdf_path = str(out / "application_package.pdf")

        score_base = r[5]
        score_tailored = r[15]
        score_delta = (
            (score_tailored - score_base)
            if (score_base is not None and score_tailored is not None)
            else None
        )
        # PRD §7.7 FR-APP-01 application channel, derived (no schema change).
        # Only `apply_url` (from raw_json) is considered, not the listing url
        # column, the spec is about how to *submit* an application, and the
        # listing URL is just the display page.
        apply_url_raw: str | None = None
        try:
            payload = json.loads(r[9] or "{}")
            if isinstance(payload, dict):
                apply_url_raw = payload.get("apply_url")
        except (json.JSONDecodeError, TypeError):
            apply_url_raw = None
        channel = apply_channel(apply_email=r[14], apply_url=apply_url_raw)
        ats_name = apply_channel_ats_name(apply_url_raw) if channel == "form" else None
        # Application state (LEFT JOIN, None if never attempted).
        # `submitted`=1 means a real send (or dry-run write of the .eml)
        # actually happened. `status` is the JobStatus name ('applied',
        # 'applied_dry_run', 'apply_needs_review', 'apply_failed', etc.).
        applied_submitted = bool(r[17]) if r[17] is not None else False
        application_status = r[18]
        applied_at = r[19]
        applied_dry_run = bool(r[20]) if r[20] is not None else False
        # `r[4]` = seen_jobs.status. LISTING_EXPIRED is set by the runner
        # (or a periodic check) when the apply_url no longer reaches a
        # job form, the role was pulled. Surface as a dedicated state
        # so the Stage 3 card shows an ⏱ pill, distinct from "applied"
        # / "needs review" / "failed".
        seen_status = r[4]
        applied_state = (
            "expired"            if seen_status == "listing_expired"
            else "applied"        if applied_submitted and not applied_dry_run
            else "dry_run"        if applied_submitted and applied_dry_run
            else "needs_review"   if application_status == "apply_needs_review"
            else "failed"         if application_status == "apply_failed"
            else None
        )
        jobs.append({
            "id": r[0],
            "title": r[1],
            "company": r[2],
            "source": r[3],
            "status": r[4],
            "score": score_base,
            "reason": r[6] or "",
            "url": r[7],
            "output_dir": r[8],
            "description": description,
            "description_word_count": r[11] or 0,
            "seniority": r[12] or _extract_seniority_required(r[1] or "", description),
            "salary_text": r[13] or _extract_expected_salary(r[1] or "", description),
            "apply_email": r[14],
            "apply_url": apply_url_raw,
            "apply_channel": channel,
            "apply_channel_ats_name": ats_name,
            # Resolved apply route: ('email', addr) | ('url', canonical) |
            # ('missing', reason). The Stage 3 card uses this to decide
            # whether to render a green "↗ open posting" chip OR a red
            # "⚠ no usable apply route, needs research" flag. Stops the
            # dashboard from misleading the user with paywalled aggregator
            # links (dailyremote / linkedin / xing). Per feedback memory
            # `feedback_no_paywalled_apply_links.md`.
            "apply_route_kind": usable_apply_route(r[14], apply_url_raw)[0],
            "apply_route_value": usable_apply_route(r[14], apply_url_raw)[1],
            "cv_md": cv_md,
            "cover_letter_md": cover_letter_md,
            "cv_html_url": f"/shortlist/{r[0]}/cv.html" if cv_html_path else None,
            "cover_letter_html_url": f"/shortlist/{r[0]}/cover_letter.html" if cl_html_path else None,
            "cv_pdf_url": f"/shortlist/{r[0]}/cv.pdf" if cv_pdf_path else None,
            "cover_letter_pdf_url": f"/shortlist/{r[0]}/cover_letter.pdf" if cl_pdf_path else None,
            # The polished, editorial application package, what gets
            # attached to the outbound email. Linking it from the Stage 3
            # card so the user can review the *final* artefact rather
            # than digging through output/ on disk.
            "package_html_url": f"/shortlist/{r[0]}/application_package.html" if package_html_path else None,
            "package_pdf_url": f"/shortlist/{r[0]}/application_package.pdf" if package_pdf_path else None,
            # Stage-3 rescore (tailored CV + CL substituted into the scoring prompt).
            # `score_tailored` is None until the rescore runs against this job.
            "score_tailored": score_tailored,
            "tailored_reason": r[16] or "",
            "score_delta": score_delta,
            # Application status, let the Stage 3 card show "applied"
            # so the user doesn't accidentally double-submit.
            "applied_state": applied_state,
            "applied_at": applied_at,
            # "Posted N days ago" badge in the Stage 3 card. We prefer
            # the posting's own posted_at (in raw_json) when present,
            # otherwise fall back to the first time WE saw it. Both are
            # approximations; first_seen_at is usually within 24h of
            # the real post date for daily scrapes.
            "posted_days_ago": _posted_days_ago(r[21], payload.get("posted_at")
                                                if isinstance(payload, dict) else None),
        })

    return jsonify({"min_score": min_score, "count": len(jobs), "jobs": jobs})


@app.route("/shortlist/<job_id>/<filename>")
def shortlist_doc(job_id: str, filename: str):
    """Serve a generated CV/cover-letter HTML for a shortlisted job.

    Locked down to the per-job output_dir recorded in seen_jobs and to a
    fixed allowlist of filenames so we can't be tricked into serving
    arbitrary files via path traversal.
    """
    if filename not in {
        "cv.html", "cover_letter.html", "cv.md", "cover_letter.md",
        "application_package.html", "application_package.pdf",
        "cv.pdf", "cover_letter.pdf",
    }:
        abort(404)
    with connect() as conn:
        cur = conn.execute("SELECT output_dir FROM seen_jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
    if not row or not row[0]:
        abort(404)
    out_dir = Path(row[0]).resolve()
    target = (out_dir / filename).resolve()
    try:
        target.relative_to(out_dir)
    except ValueError:
        abort(404)
    if not target.exists():
        abort(404)
    from flask import send_file
    if filename.endswith(".pdf"):
        mime = "application/pdf"
    elif filename.endswith(".html"):
        mime = "text/html"
    else:
        mime = "text/markdown"
    return send_file(str(target), mimetype=mime)


@app.route("/api/applications")
def api_applications():
    """One row per row in the applications table, for the Stage 4 panel's
    transparency view. Joins seen_jobs for title/company/score/output_dir
    and parses the per-job application.eml on disk for the exact subject
    that went out. Returns rows ordered most-recent-first."""
    from email import message_from_bytes
    from email.header import decode_header, make_header

    def _decode_header(raw: str | None) -> str | None:
        """RFC-2047-decode a header so non-ASCII (em-dashes, umlauts) come
        back as the original Unicode the user wrote, not =?utf-8?b?...?=."""
        if not raw:
            return raw
        try:
            return str(make_header(decode_header(raw))).strip()
        except Exception:
            return raw.strip()

    rows_out = []
    with connect() as conn:
        cur = conn.execute("""
            SELECT a.job_id, a.attempted_at, a.status AS app_status,
                   a.submitted, a.dry_run, a.proof_level, a.proof_evidence,
                   a.confirmation_url, a.error, a.last_response_at,
                   a.response_type, a.response_subject, a.response_snippet,
                   s.title, s.company, s.source, s.score, s.output_dir,
                   s.apply_email, s.url, s.status AS seen_status
            FROM applications a
            JOIN seen_jobs s ON s.id = a.job_id
            ORDER BY a.attempted_at DESC
        """)
        for r in cur.fetchall():
            try:
                evidence = json.loads(r["proof_evidence"] or "[]")
            except (json.JSONDecodeError, TypeError):
                evidence = []
            # `source` on proof_evidence entries: "application" = bot, anything
            # else (e.g. "manual") = human-marked. Default to "application"
            # for backwards compat with rows recorded before the channel tag.
            channel = "manual"
            for ev in evidence:
                if isinstance(ev, dict) and ev.get("source") == "application":
                    channel = "bot"
                    break

            # Pull the exact Subject line + recipient that went out from the
            # persisted .eml. Falls back to the seen_jobs.apply_email column
            # for rows where the .eml wasn't kept on disk.
            eml_path = None
            sent_subject = None
            sent_to = r["apply_email"]
            # Document links the user can click for post-send review.
            # Stage 4 needs these so the user can see EXACTLY what was
            # sent (matching the CV + CL + package attached to the email),
            # not the most-recent on-disk version of those files.
            cv_pdf_url = cl_pdf_url = package_pdf_url = None
            cv_html_url = cl_html_url = package_html_url = None
            if r["output_dir"]:
                out_dir = Path(r["output_dir"])
                p = out_dir / "application.eml"
                if p.exists():
                    eml_path = str(p)
                    try:
                        msg = message_from_bytes(p.read_bytes())
                        sent_subject = _decode_header(msg.get("Subject"))
                        eml_to = _decode_header(msg.get("To"))
                        if eml_to:
                            sent_to = eml_to
                    except Exception:
                        pass
                # Resolve doc links, same allowlist + path-traversal-safe
                # route as the shortlist endpoint uses (`/shortlist/<id>/<f>`).
                # Reusing that route keeps the surface area small.
                if (out_dir / "cv.pdf").exists():
                    cv_pdf_url = f"/shortlist/{r['job_id']}/cv.pdf"
                if (out_dir / "cover_letter.pdf").exists():
                    cl_pdf_url = f"/shortlist/{r['job_id']}/cover_letter.pdf"
                if (out_dir / "application_package.pdf").exists():
                    package_pdf_url = f"/shortlist/{r['job_id']}/application_package.pdf"
                if (out_dir / "cv.html").exists():
                    cv_html_url = f"/shortlist/{r['job_id']}/cv.html"
                if (out_dir / "cover_letter.html").exists():
                    cl_html_url = f"/shortlist/{r['job_id']}/cover_letter.html"
                if (out_dir / "application_package.html").exists():
                    package_html_url = f"/shortlist/{r['job_id']}/application_package.html"

            rows_out.append({
                "job_id": r["job_id"],
                "title": r["title"],
                "company": r["company"],
                "source": r["source"],
                "score": r["score"],
                "channel": channel,           # "bot" | "manual"
                "to": sent_to,
                "subject": sent_subject,
                "status": r["app_status"],
                "seen_status": r["seen_status"],
                "submitted": bool(r["submitted"]),
                "dry_run": bool(r["dry_run"]),
                "proof_level": r["proof_level"],
                "error": r["error"],
                "attempted_at": r["attempted_at"],
                "last_response_at": r["last_response_at"],
                "response_type": r["response_type"],
                "response_subject": r["response_subject"],
                "response_snippet": r["response_snippet"],
                "confirmation_url": r["confirmation_url"],
                "url": r["url"],
                "has_eml": eml_path is not None,
                # Don't expose the absolute path, the eml route gates it.
                # Doc links, let the user review what was actually sent.
                "cv_pdf_url": cv_pdf_url,
                "cl_pdf_url": cl_pdf_url,
                "package_pdf_url": package_pdf_url,
                "cv_html_url": cv_html_url,
                "cl_html_url": cl_html_url,
                "package_html_url": package_html_url,
            })
    return jsonify(rows_out)


@app.route("/api/applications/<job_id>/transition", methods=["POST"])
def api_application_transition(job_id: str):
    """CRM action endpoint: advance an application's state.

    Body: {"state": "received"|"replied"|"interview"|"rejected"|"bounced",
           "note": "optional free text"}
    The endpoint is intentionally idempotent w.r.t. each click, the
    transition is appended to proof_evidence with a timestamp, so an
    operator can mark "received" then later mark "replied" without
    losing the earlier signal.
    """
    from flask import request as flask_request
    from .state import VALID_APPLICATION_TRANSITIONS, transition_application

    payload = flask_request.get_json(silent=True) or {}
    state = (payload.get("state") or "").strip().lower()
    note = (payload.get("note") or "").strip() or None
    if state not in VALID_APPLICATION_TRANSITIONS:
        return jsonify({
            "ok": False,
            "error": f"unsupported state {state!r}",
            "allowed": list(VALID_APPLICATION_TRANSITIONS),
        }), 400

    try:
        with connect() as conn:
            transition_application(conn, job_id, new_state=state, note=note)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 404
    return jsonify({"ok": True, "job_id": job_id, "state": state})


@app.route("/api/jobs/<job_id>/rescore-with-feedback", methods=["POST"])
def api_rescore_with_feedback(job_id: str):
    """Stage-2 disagree-and-rescore endpoint (product vision stage 3).

    Body: {"feedback": "you missed that I have 5 years of Python"}

    Behavior:
      1. Reconstruct the JobPosting from `raw_json` in seen_jobs.
      2. Load profile + secrets fresh so any prior feedback is included.
      3. Call llm_score(..., user_feedback=<comment>), the scorer
         injects the comment into the prompt as an extra section.
      4. Persist the new score + the feedback text to seen_jobs
         (leaves the original `score` column untouched so the UI can
         render a true before/after).
      5. Append the feedback as a durable fact to `data/profile.yaml`
         under `user_facts` so ALL future scoring picks it up.

    Returns {ok, job_id, score_before, score_after, delta, reason}.
    """
    from flask import request as flask_request

    from .config import load_secrets
    from .models import JobPosting
    from .profile import append_user_fact, apply_profile_patch, load_profile
    from .scoring import (
        CannotScore, extract_profile_updates_from_feedback, llm_score,
    )
    from .state import update_user_feedback_rescore

    payload = flask_request.get_json(silent=True) or {}
    feedback = (payload.get("feedback") or "").strip()
    if not feedback:
        return jsonify({"ok": False, "error": "feedback is required"}), 400
    if len(feedback) > 4000:
        return jsonify({"ok": False, "error": "feedback exceeds 4000 chars"}), 400

    with connect() as conn:
        row = conn.execute(
            "SELECT raw_json, score, description_scraped FROM seen_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": f"unknown job {job_id!r}"}), 404
        raw_json = row["raw_json"]
        score_before = row["score"]
        description_scraped = bool(row["description_scraped"])

    if not raw_json:
        return jsonify({
            "ok": False,
            "error": "job has no raw_json, cannot reconstruct posting",
        }), 409

    try:
        job = JobPosting.model_validate_json(raw_json)
    except Exception as e:
        return jsonify({"ok": False, "error": f"raw_json invalid: {e}"}), 500

    try:
        profile = load_profile()
        secrets = load_secrets()
    except Exception as e:
        return jsonify({"ok": False, "error": f"config load failed: {e}"}), 500

    try:
        result = llm_score(
            job, profile, secrets,
            description_scraped=description_scraped,
            user_feedback=feedback,
            phase="score_user_feedback",
        )
    except CannotScore as e:
        return jsonify({"ok": False, "error": f"cannot_score: {e}"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": f"scorer failed: {e}"}), 500

    with connect() as conn:
        update_user_feedback_rescore(
            conn, job_id, feedback=feedback,
            score=result.score, reason=result.reason or "",
        )

    # Second LLM pass: distill the comment into structured profile updates
    # (skills, durable facts, preference flags). This is what makes the
    # feedback durable beyond this one job: future scoring runs will see
    # the canonicalized skill/fact, not just a raw quote.
    profile_updates: dict = {}
    extraction_error: str | None = None
    try:
        patch = extract_profile_updates_from_feedback(
            feedback, profile, secrets, job_id=job_id,
        )
        if patch:
            profile_updates = apply_profile_patch(patch)
    except Exception as e:
        extraction_error = str(e)

    # Fallback: if the extractor returned no structured user_facts AND the
    # apply step didn't add any facts, still keep the raw comment around in
    # user_facts as an audit trail (the previous behaviour).
    fact_persisted = bool(profile_updates.get("added_facts"))
    if not fact_persisted:
        try:
            append_user_fact(feedback)
            fact_persisted = True
        except Exception:
            fact_persisted = False

    delta = (result.score - score_before) if score_before is not None else None
    return jsonify({
        "ok": True,
        "job_id": job_id,
        "score_before": score_before,
        "score_after": result.score,
        "delta": delta,
        "reason": result.reason,
        "fact_persisted": fact_persisted,
        "profile_updates": profile_updates,
        "extraction_error": extraction_error,
    })


@app.route("/applications/<job_id>/application.eml")
def application_eml(job_id: str):
    """Serve the persisted .eml for a sent (or attempted) application, audit trail viewer. Path-traversal-safe: we look up the per-job
    output_dir from the DB and only serve the exact `application.eml`
    inside it. Browsers will offer the .eml as a download; recruiters
    never see this route."""
    with connect() as conn:
        cur = conn.execute(
            "SELECT output_dir FROM seen_jobs WHERE id = ?", (job_id,),
        )
        row = cur.fetchone()
    if not row or not row[0]:
        abort(404)
    out_dir = Path(row[0]).resolve()
    target = (out_dir / "application.eml").resolve()
    try:
        target.relative_to(out_dir)
    except ValueError:
        abort(404)
    if not target.exists():
        abort(404)
    from flask import send_file
    return send_file(str(target), mimetype="message/rfc822",
                     as_attachment=False, download_name="application.eml")


@app.route("/api/latest-run-jobs")
def api_latest_run_jobs():
    """Get all jobs scraped in the latest run, with stage-1 attributes.

    Uses `fetched_ids` from the run summary_json (every job touched in the run,
    including already-seen ones). Falls back to first_seen_at filter for runs
    predating that field, and finally to the most-recent N rows in seen_jobs.
    """
    with connect() as conn:
        cur = conn.execute(
            "SELECT n_fetched, started_at, summary_json FROM runs ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "No runs found"}), 404

        n_fetched, started_at, summary_json = row[0], row[1], row[2]

        try:
            summary = json.loads(summary_json or "{}")
        except json.JSONDecodeError:
            summary = {}
        fetched_ids = summary.get("fetched_ids") if isinstance(summary, dict) else None

        rows = []
        if isinstance(fetched_ids, list) and fetched_ids:
            placeholders = ",".join("?" * len(fetched_ids))
            cur = conn.execute(
                f"""
                SELECT title, company, source, status, score, score_reason, url, raw_json,
                       description_scraped, description_word_count, apply_email,
                       score_breakdown_json, discard_reason, id,
                       score_after_feedback, score_after_feedback_reason, user_feedback
                FROM seen_jobs
                WHERE id IN ({placeholders})
                ORDER BY source ASC, title ASC
                """,
                tuple(fetched_ids),
            )
            rows = cur.fetchall()

        if not rows:
            cur = conn.execute(
                """
                SELECT title, company, source, status, score, score_reason, url, raw_json,
                       description_scraped, description_word_count, apply_email,
                       score_breakdown_json, discard_reason, id,
                       score_after_feedback, score_after_feedback_reason, user_feedback
                FROM seen_jobs
                WHERE first_seen_at >= ?
                ORDER BY source ASC, title ASC
                """,
                (started_at,),
            )
            rows = cur.fetchall()

        if not rows:
            cur = conn.execute(
                """
                SELECT title, company, source, status, score, score_reason, url, raw_json,
                       description_scraped, description_word_count, apply_email,
                       score_breakdown_json, discard_reason, id,
                       score_after_feedback, score_after_feedback_reason, user_feedback
                FROM seen_jobs
                ORDER BY source ASC, title ASC
                LIMIT ?
                """,
                (max(n_fetched, 1),),
            )
            rows = cur.fetchall()

        jobs = []
        for r in rows:
            description = ""
            try:
                payload = json.loads(r[7] or "{}")
                if isinstance(payload, dict):
                    description = str(payload.get("description", ""))
            except json.JSONDecodeError:
                description = ""

            description_scraped_raw = r[8]
            description_scraped: bool | None
            if description_scraped_raw is None:
                description_scraped = None  # unknown, predates enrichment
            else:
                description_scraped = bool(description_scraped_raw)

            # PRD §7.7 FR-APP-01 application channel, derived (no schema change).
            # apply_url comes from raw_json only; the listing url column is for
            # viewing, not submitting.
            apply_url_raw: str | None = None
            try:
                payload_for_apply = json.loads(r[7] or "{}")
                if isinstance(payload_for_apply, dict):
                    apply_url_raw = payload_for_apply.get("apply_url")
            except (json.JSONDecodeError, TypeError):
                apply_url_raw = None
            channel = apply_channel(apply_email=r[10], apply_url=apply_url_raw)
            ats_name = apply_channel_ats_name(apply_url_raw) if channel == "form" else None

            # Structured per-axis breakdown for the Scoring Reason column.
            # New rows have score_breakdown_json populated; older rows only
            # have the "role=X, skills=Y, ..." prefix embedded in
            # score_reason, both paths produce the same dict.
            breakdown = _parse_score_breakdown(r[11], r[5])
            jobs.append({
                "id": r[13],
                "title": r[0],
                "company": r[1],
                "source": r[2],
                "status": r[3],
                "score": r[4],
                "reason": r[5],
                "url": r[6],
                "expected_salary": _extract_expected_salary(r[0] or "", description),
                "seniority_required": _extract_seniority_required(r[0] or "", description),
                "description_scraped": description_scraped,
                "description_word_count": r[9],
                "apply_email": r[10],
                "apply_url": apply_url_raw,
                "apply_channel": channel,
                "apply_channel_ats_name": ats_name,
                "score_breakdown": breakdown,
                "discard_reason": r[12],
                "score_after_feedback": r[14],
                "score_after_feedback_reason": r[15],
                "user_feedback": r[16],
            })
    
    return jsonify(jobs)


def _export_destination_dir() -> Path:
    """Where the Export JSON button writes its dump.

    Default is the user's macOS Downloads folder (~/Downloads) so exports
    don't pollute the repo and are immediately reachable from Finder /
    Quick Look. Override with the JOBBOT_EXPORT_DIR env var for tests or
    headless setups where ~/Downloads doesn't exist.
    """
    import os
    override = os.environ.get("JOBBOT_EXPORT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Downloads"


@app.route("/api/export/jobs", methods=["POST"])
def api_export_jobs():
    """Dump all jobs (with full descriptions) to ~/Downloads as JSON.
    Returns the absolute path written and a per-status breakdown."""
    placeholders = ",".join("?" * len(EXPORT_STATUSES))
    with connect() as conn:
        cur = conn.execute(
            f"SELECT id, source, url, title, company, status, score, score_reason, "
            f"description_full, description_word_count, seniority, salary_text, "
            f"first_seen_at, scored_at, enriched_at, raw_json "
            f"FROM seen_jobs WHERE status IN ({placeholders}) "
            f"ORDER BY (CASE WHEN status IN ('scored','generated') THEN 0 "
            f"WHEN status='below_threshold' THEN 1 ELSE 2 END), "
            f"score DESC NULLS LAST, first_seen_at DESC",
            EXPORT_STATUSES,
        )
        rows = cur.fetchall()

    jobs = []
    for r in rows:
        description = r["description_full"]
        if not description and r["raw_json"]:
            try:
                description = json.loads(r["raw_json"]).get("description", "")
            except json.JSONDecodeError:
                description = ""
        jobs.append({
            "id": r["id"],
            "source": r["source"],
            "url": r["url"],
            "title": r["title"],
            "company": r["company"],
            "status": r["status"],
            "score": r["score"],
            "score_reason": r["score_reason"],
            "seniority": r["seniority"],
            "salary_text": r["salary_text"],
            "description_word_count": r["description_word_count"],
            "first_seen_at": r["first_seen_at"],
            "scored_at": r["scored_at"],
            "enriched_at": r["enriched_at"],
            "description": description,
        })

    payload = {
        "n_jobs": len(jobs),
        "by_status": {s: sum(1 for j in jobs if j["status"] == s) for s in EXPORT_STATUSES},
        "jobs": jobs,
    }

    out_dir = _export_destination_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"jobs_export_{ts}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return jsonify({
        "ok": True,
        "path": str(out_path),
        "n_jobs": len(jobs),
        "by_status": payload["by_status"],
    })


def run(host: str = "127.0.0.1", port: int = 5001, debug: bool = False) -> None:
    """Start the dashboard server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run(debug=True)
