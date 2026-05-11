"""Web dashboard for job-bot pipeline monitoring."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

from .config import REPO_ROOT
from .models import JobStatus
from .state import apply_channel, apply_channel_ats_name, connect

EXPORT_STATUSES = ("scored", "below_threshold", "filtered", "generated", "scraped")

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


# Funnel retention thresholds. The user's brief: red < 20%, amber 20-50%,
# green 50%+ — applied to the % retained from the PREVIOUS stage.
_RETENTION_AMBER_MIN = 20
_RETENTION_GREEN_MIN = 50


def _retention_color(pct: float | None) -> str:
    """Bucket retention % into red / amber / green per the brief."""
    if pct is None:
        return "neutral"
    if pct < _RETENTION_AMBER_MIN:
        return "red"
    if pct < _RETENTION_GREEN_MIN:
        return "amber"
    return "green"


def _count_interviewed(conn) -> int:
    """Applications that reached proof_level >= 4 (employer interview).

    The column ships in Milestone 5 (proof ladder); until then the query
    raises OperationalError on the missing column and we report 0. The
    template flags this card with an `M5` pill so the zero is read as
    expected, not a bug.
    """
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE proof_level >= 4"
        )
        return cur.fetchone()[0]
    except Exception:
        return 0


def compute_funnel(conn) -> list[dict]:
    """Return the 5-stage outcome funnel for the top dashboard strip.

    Each stage carries the absolute count and the percent retained from
    the previous stage (None for `total`, which has no predecessor).
    Stages and their SQL — the user's brief, with schema-mapped columns:

      Total        seen_jobs                            COUNT(*)
      Suitable     seen_jobs.score >= 70                COUNT(*)
      Tailored     seen_jobs.output_dir IS NOT NULL     COUNT(*)
      Applied      applications.submitted = 1           COUNT(*)
      Interviewed  applications.proof_level >= 4        COUNT(*) — M5

    `cannot_score:*` rows count toward Total but not toward Suitable,
    because `score IS NULL` for them — exactly what the user wants.
    """
    total = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
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
        ("Total", total, None),
        ("Suitable", suitable, None),
        ("Tailored", tailored, None),
        ("Applied", applied, None),
        ("Interviewed", interviewed, "M5"),
    ]

    out: list[dict] = []
    prev_count: int | None = None
    for label, count, badge in stages:
        if prev_count is None:
            retention_pct: float | None = None
        elif prev_count == 0:
            retention_pct = None
        else:
            retention_pct = round(100.0 * count / prev_count, 1)
        out.append({
            "label": label,
            "count": count,
            "retention_pct": retention_pct,
            "retention_color": _retention_color(retention_pct),
            "pending_milestone": badge,
        })
        prev_count = count
    return out


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

    applied_total = status_counts.get(JobStatus.APPLY_SUBMITTED.value, 0)

    return render_template("index.html",
                          status_counts=status_counts,
                          total_jobs=total_jobs,
                          total_runs=total_runs,
                          applied_total=applied_total,
                          funnel=funnel,
                          activity_today=activity_today,
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

        in_progress = row[2] is None
        if in_progress:
            started_at = row[1]
            live_counts = conn.execute(
                """
                SELECT
                    COUNT(*) AS fetched,
                    SUM(CASE WHEN description_full IS NOT NULL
                              AND LENGTH(TRIM(description_full)) > 0
                             THEN 1 ELSE 0 END) AS with_desc,
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
                diagnostics.setdefault("fetched", int(live_counts[0] or 0))
                diagnostics.setdefault("enriched", int(live_counts[1] or 0))
                diagnostics.setdefault("filtered", int(live_counts[3] or 0))
                diagnostics.setdefault("scored", int(live_counts[4] or 0))
                diagnostics.setdefault("below_threshold", int(live_counts[5] or 0))
                diagnostics.setdefault("generated", int(live_counts[6] or 0))

        portal_payload = _portal_payload_for_run(conn, (row[0], row[1], row[2], row[8]))

    portal_rows = sorted(
        (
            {
                "source": source,
                "hits": hits,
                **(portal_payload["per_portal_description"].get(source) or {
                    "total": 0, "with_description": 0, "percent_with_description": 0.0,
                }),
            }
            for source, hits in portal_payload["per_portal"].items()
        ),
        key=lambda r: r["hits"],
        reverse=True,
    )
    current_stage = _infer_current_stage(portal_payload["total"], diagnostics) if in_progress else None

    run_data = {
        "id": row[0],
        "started_at": row[1],
        "finished_at": row[2],
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
        stages=diagnostics,
        portal_rows=portal_rows,
        portal_total=portal_payload["total"],
        portal_pct_with_description=portal_payload["percent_with_description"],
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


def _description_counts_by_source(conn, *, ids: list[str] | None = None,
                                  since: str | None = None) -> dict[str, dict[str, float | int]]:
    """Group seen_jobs by source and count rows with non-empty descriptions.

    Either `ids` (an explicit id list — used when the run summary recorded
    fetched_ids) or `since` (a started_at timestamp — used for in-progress
    runs) must be provided. Returns the per-source breakdown shape the
    portal-hits API ships to the dashboard.
    """
    if ids:
        placeholders = ",".join("?" * len(ids))
        query = f"""
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN description_full IS NOT NULL
                             AND LENGTH(TRIM(description_full)) > 0
                            THEN 1 ELSE 0 END) AS with_description
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
                   SUM(CASE WHEN description_full IS NOT NULL
                             AND LENGTH(TRIM(description_full)) > 0
                            THEN 1 ELSE 0 END) AS with_description
            FROM seen_jobs
            WHERE first_seen_at >= ?
            GROUP BY source
            """,
            (since,),
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


def _empty_portal_payload() -> dict:
    return {
        "run_id": None,
        "started_at": None,
        "finished_at": None,
        "in_progress": False,
        "elapsed_sec": 0,
        "per_portal": {},
        "per_portal_description": {},
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
    else:
        per_portal_desc = _description_counts_by_source(conn, since=started_at)

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

    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "in_progress": in_progress,
        "elapsed_sec": elapsed_sec,
        "per_portal": per_portal,
        "per_portal_description": per_portal_desc,
        "total": sum(per_portal.values()),
        "total_with_description": total_with_desc,
        "percent_with_description": pct_with_desc,
    }


def _infer_current_stage(per_portal_total: int, stages: dict) -> str:
    """Best-effort label for the user: which pipeline step is the live run
    sitting in right now? Uses the same stage-count signals the
    pipeline writes to its summary, derived from seen_jobs when the
    summary hasn't been persisted yet.

    Order matters — pipeline.py runs them in this sequence and each step
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
    inserted since the run's `started_at` — keeping the table populated as
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
            SELECT id, title, company, source, status, score, score_reason,
                   url, output_dir, raw_json,
                   description_full, description_word_count,
                   seniority, salary_text, apply_email,
                   score_tailored, score_tailored_reason
            FROM seen_jobs
            WHERE score IS NOT NULL AND score >= ?
            ORDER BY score DESC, first_seen_at DESC
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

        score_base = r[5]
        score_tailored = r[15]
        score_delta = (
            (score_tailored - score_base)
            if (score_base is not None and score_tailored is not None)
            else None
        )
        # PRD §7.7 FR-APP-01 application channel — derived (no schema change).
        # Only `apply_url` (from raw_json) is considered, not the listing url
        # column — the spec is about how to *submit* an application, and the
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
            "cv_md": cv_md,
            "cover_letter_md": cover_letter_md,
            "cv_html_url": f"/shortlist/{r[0]}/cv.html" if cv_html_path else None,
            "cover_letter_html_url": f"/shortlist/{r[0]}/cover_letter.html" if cl_html_path else None,
            # Stage-3 rescore (tailored CV + CL substituted into the scoring prompt).
            # `score_tailored` is None until the rescore runs against this job.
            "score_tailored": score_tailored,
            "tailored_reason": r[16] or "",
            "score_delta": score_delta,
        })

    return jsonify({"min_score": min_score, "count": len(jobs), "jobs": jobs})


@app.route("/shortlist/<job_id>/<filename>")
def shortlist_doc(job_id: str, filename: str):
    """Serve a generated CV/cover-letter HTML for a shortlisted job.

    Locked down to the per-job output_dir recorded in seen_jobs and to a
    fixed allowlist of filenames so we can't be tricked into serving
    arbitrary files via path traversal.
    """
    if filename not in {"cv.html", "cover_letter.html", "cv.md", "cover_letter.md"}:
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
    mime = "text/html" if filename.endswith(".html") else "text/markdown"
    return send_file(str(target), mimetype=mime)


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
                       description_scraped, description_word_count, apply_email
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
                       description_scraped, description_word_count, apply_email
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
                       description_scraped, description_word_count, apply_email
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
                description_scraped = None  # unknown — predates enrichment
            else:
                description_scraped = bool(description_scraped_raw)

            # PRD §7.7 FR-APP-01 application channel — derived (no schema change).
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
                "description_scraped": description_scraped,
                "description_word_count": r[9],
                "apply_email": r[10],
                "apply_url": apply_url_raw,
                "apply_channel": channel,
                "apply_channel_ats_name": ats_name,
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
