"""Web dashboard for job-bot pipeline monitoring."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

from .models import JobStatus
from .state import connect

_TEMPLATES_DIR = Path(__file__).with_name("templates")
app = Flask(__name__, template_folder=str(_TEMPLATES_DIR))


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


@app.route("/")
def index():
    """Dashboard home page."""
    with connect() as conn:
        # Get status counts
        status_counts = {}
        for st in JobStatus:
            cur = conn.execute("SELECT COUNT(*) FROM seen_jobs WHERE status = ?", (st.value,))
            status_counts[st.value] = cur.fetchone()[0]
        
        # Get total jobs
        cur = conn.execute("SELECT COUNT(*) FROM seen_jobs")
        total_jobs = cur.fetchone()[0]
        
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
                "n_fetched": r[2],
                "n_new": r[3],
                "n_generated": r[4],
                "n_applied": r[5],
                "n_errors": r[6],
            }
            for r in cur.fetchall()
        ]
        
        # Get last 24h applications
        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM applications
            WHERE attempted_at >= ?
            """,
            (since.isoformat(),),
        )
        applied_24h = cur.fetchone()[0]

    applied_total = status_counts.get(JobStatus.APPLY_SUBMITTED.value, 0)
    
    return render_template("index.html", 
                          status_counts=status_counts,
                          total_jobs=total_jobs,
                          applied_total=applied_total,
                          applied_24h=applied_24h,
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
                "n_fetched": r[2],
                "n_new": r[3],
                "n_generated": r[4],
                "n_applied": r[5],
                "n_errors": r[6],
            }
            for r in cur.fetchall()
        ]
    return jsonify(runs)


@app.route("/runs/<int:run_id>")
def run_detail_page(run_id: int):
    """Run detail page with diagnostics and blockers."""
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

    summary = {}
    if row[8]:
        try:
            summary = json.loads(row[8])
        except json.JSONDecodeError:
            summary = {}

    diagnostics = summary.get("stages", {}) if isinstance(summary, dict) else {}
    score_stats = summary.get("score_stats", {}) if isinstance(summary, dict) else {}
    blockers = summary.get("top_blockers", []) if isinstance(summary, dict) else []

    run_data = {
        "id": row[0],
        "started_at": row[1],
        "finished_at": row[2],
        "n_fetched": row[3],
        "n_new": row[4],
        "n_generated": row[5],
        "n_applied": row[6],
        "n_errors": row[7],
    }
    return render_template(
        "run_detail.html",
        run=run_data,
        stages=diagnostics,
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


@app.route("/api/latest-run-portal-hits")
def api_latest_run_portal_hits():
    """Per-portal hit counts for the latest run.

    Reads `per_source_fetched` from the run's summary_json (gross fetch count
    per portal — pre-dedup). Falls back to aggregating jobs whose
    first_seen_at >= run.started_at if the summary is missing the field
    (older runs predating the per-source tracking change).
    """
    with connect() as conn:
        cur = conn.execute(
            "SELECT id, started_at, summary_json FROM runs ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return jsonify({
                "run_id": None,
                "started_at": None,
                "per_portal": {},
                "per_portal_description": {},
                "total": 0,
                "total_with_description": 0,
                "percent_with_description": 0.0,
            })
        run_id, started_at, summary_json = row[0], row[1], row[2]

        per_portal: dict[str, int] = {}
        try:
            summary = json.loads(summary_json or "{}")
        except json.JSONDecodeError:
            summary = {}
        if isinstance(summary, dict) and isinstance(summary.get("per_source_fetched"), dict):
            per_portal = {k: int(v) for k, v in summary["per_source_fetched"].items()}
        else:
            cur = conn.execute(
                """
                SELECT source, COUNT(*) FROM seen_jobs
                WHERE first_seen_at >= ?
                GROUP BY source
                """,
                (started_at,),
            )
            per_portal = {r[0]: r[1] for r in cur.fetchall()}

        fetched_ids = summary.get("fetched_ids") if isinstance(summary, dict) else None
        per_portal_desc: dict[str, dict[str, float | int]] = {}

        if isinstance(fetched_ids, list) and fetched_ids:
            placeholders = ",".join("?" * len(fetched_ids))
            cur = conn.execute(
                f"""
                SELECT source,
                       COUNT(*) AS total,
                       SUM(CASE
                               WHEN description_full IS NOT NULL
                                AND LENGTH(TRIM(description_full)) > 0
                               THEN 1
                               ELSE 0
                           END) AS with_description
                FROM seen_jobs
                WHERE id IN ({placeholders})
                GROUP BY source
                """,
                tuple(fetched_ids),
            )
            for source, total, with_description in cur.fetchall():
                total_i = int(total or 0)
                with_desc_i = int(with_description or 0)
                pct = (with_desc_i / total_i * 100.0) if total_i else 0.0
                per_portal_desc[source] = {
                    "total": total_i,
                    "with_description": with_desc_i,
                    "percent_with_description": round(pct, 1),
                }

    return jsonify({
        "run_id": run_id,
        "started_at": started_at,
        "per_portal": per_portal,
        "per_portal_description": per_portal_desc,
        "total": sum(per_portal.values()),
        "total_with_description": sum(
            int(v.get("with_description", 0))
            for v in per_portal_desc.values()
            if isinstance(v, dict)
        ),
        "percent_with_description": round(
            (
                sum(
                    int(v.get("with_description", 0))
                    for v in per_portal_desc.values()
                    if isinstance(v, dict)
                )
                /
                max(
                    1,
                    sum(
                        int(v.get("total", 0))
                        for v in per_portal_desc.values()
                        if isinstance(v, dict)
                    ),
                )
            )
            * 100.0,
            1,
        ) if per_portal_desc else 0.0,
    })


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
                SELECT title, company, source, status, score, score_reason, url, raw_json
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
                SELECT title, company, source, status, score, score_reason, url, raw_json
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
                SELECT title, company, source, status, score, score_reason, url, raw_json
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

            jobs.append({
                "title": r[0],
                "company": r[1],
                "source": r[2],
                "status": r[3],
                "score": r[4],
                "reason": r[5],
                "url": r[6],
                "expected_salary": _extract_expected_salary(r[0] or "", description),
                "seniority_required": _extract_seniority_required(r[0] or "", description),
            })
    
    return jsonify(jobs)


def run(host: str = "127.0.0.1", port: int = 5001, debug: bool = False) -> None:
    """Start the dashboard server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run(debug=True)
