"""Web dashboard for job-bot pipeline monitoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template

from .models import JobStatus
from .state import connect

app = Flask(__name__, template_folder="templates")


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
            SELECT started_at, n_fetched, n_new, n_generated, n_applied
            FROM runs
            ORDER BY started_at DESC
            LIMIT 5
            """
        )
        runs = [
            {
                "timestamp": r[0],
                "n_fetched": r[1],
                "n_new": r[2],
                "n_generated": r[3],
                "n_applied": r[4],
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
    
    return render_template("index.html", 
                          status_counts=status_counts,
                          total_jobs=total_jobs,
                          applied_24h=applied_24h,
                          runs=runs)


@app.route("/api/jobs")
def api_jobs():
    """Get all jobs with optional filtering."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, company, source, status, score, url
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
                "url": r[6],
            }
            for r in cur.fetchall()
        ]
    return jsonify(jobs)


@app.route("/api/jobs/by-status/<status>")
def api_jobs_by_status(status: str):
    """Get jobs filtered by status."""
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, company, source, status, score, url
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
                "url": r[6],
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
            SELECT started_at, n_fetched, n_new, n_generated, n_applied
            FROM runs
            ORDER BY started_at DESC
            LIMIT 20
            """
        )
        runs = [
            {
                "timestamp": r[0],
                "n_fetched": r[1],
                "n_new": r[2],
                "n_generated": r[3],
                "n_applied": r[4],
            }
            for r in cur.fetchall()
        ]
    return jsonify(runs)


@app.route("/jobs")
def jobs_page():
    """Jobs listing page."""
    return render_template("jobs.html")


@app.route("/runs")
def runs_page():
    """Run history page."""
    return render_template("runs.html")


def run(host: str = "127.0.0.1", port: int = 5001, debug: bool = False) -> None:
    """Start the dashboard server."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run(debug=True)
