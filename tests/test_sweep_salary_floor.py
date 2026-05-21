"""Retroactive salary-floor sweep: demote already-scored rows whose stated
pay is below the floor, so the current match list reflects a floor that
was added after they were scored.

Pins:
  - permanent rows use the annual floor; freelance_sources use the hourly floor
  - rows with no stated pay are left alone
  - terminal-status rows (applied/expired) are never touched
  - --dry-run reports without writing
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from jobbot.models import JobPosting, JobStatus
from jobbot.state import connect, upsert_new


def _seed(db, rows):
    with connect(db) as conn:
        upsert_new(conn, [
            JobPosting(id=r["id"], source=r["source"], title="PM", company="Co",
                       url=f"https://example.com/{r['id']}", description="x")
            for r in rows
        ])
        for r in rows:
            conn.execute(
                "UPDATE seen_jobs SET status=?, score=?, description_full=? WHERE id=?",
                (r["status"], r.get("score", 80), r.get("body", ""), r["id"]),
            )


def _run_sweep(monkeypatch, db, dry_run=False):
    """Invoke cmd_sweep_salary_floor with a config carrying both floors."""
    import jobbot.cli as cli
    from jobbot.config import Config

    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    cfg = Config(
        salary_floor_eur_year=90000,
        freelance_sources=["freelancermap"],
        freelance_hourly_floor_eur=80,
    )
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    args = type("A", (), {"dry_run": dry_run})()
    cli.cmd_sweep_salary_floor(args)


def _status(db, jid):
    with connect(db) as conn:
        return conn.execute("SELECT status FROM seen_jobs WHERE id=?", (jid,)).fetchone()["status"]


def test_demotes_permanent_below_annual_floor(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "low", "source": "dailyremote", "status": "scored", "score": 80,
         "body": "Great role. Compensation: EUR 70,000 - 80,000 per year."},
        {"id": "ok", "source": "dailyremote", "status": "scored", "score": 85,
         "body": "Great role. Compensation: EUR 100,000 - 120,000 per year."},
    ])
    _run_sweep(monkeypatch, db)
    assert _status(db, "low") == JobStatus.FILTERED.value
    assert _status(db, "ok") == "scored"


def test_demotes_freelance_below_hourly_floor(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "fl_low", "source": "freelancermap", "status": "scored", "score": 75,
         "body": "Product Owner Projekt. Rate: 40 €/Std remote."},
        {"id": "fl_ok", "source": "freelancermap", "status": "scored", "score": 78,
         "body": "Product Owner Projekt. Rate: 95 €/Std remote."},
    ])
    _run_sweep(monkeypatch, db)
    assert _status(db, "fl_low") == JobStatus.FILTERED.value
    assert _status(db, "fl_ok") == "scored"


def test_no_stated_pay_left_alone(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "nopay", "source": "dailyremote", "status": "scored", "score": 80,
         "body": "Senior PM, remote, great team. Salary on application."},
    ])
    _run_sweep(monkeypatch, db)
    assert _status(db, "nopay") == "scored"


def test_terminal_rows_never_touched(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "applied", "source": "dailyremote", "status": "apply_submitted",
         "score": 80, "body": "Comp: EUR 50,000 per year."},
        {"id": "expired", "source": "dailyremote", "status": "listing_expired",
         "score": 80, "body": "Comp: EUR 50,000 per year."},
    ])
    _run_sweep(monkeypatch, db)
    assert _status(db, "applied") == "apply_submitted"
    assert _status(db, "expired") == "listing_expired"


def test_dry_run_does_not_write(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "low", "source": "dailyremote", "status": "scored", "score": 80,
         "body": "Comp: EUR 60,000 per year."},
    ])
    _run_sweep(monkeypatch, db, dry_run=True)
    assert _status(db, "low") == "scored"  # untouched in dry-run
