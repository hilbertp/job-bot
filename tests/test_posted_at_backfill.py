"""Backfill helpers + discovery endpoint for posting-date analytics.

`jobs_needing_posted_at_backfill` selects already-enriched JSON-LD-source
rows that still lack a posted_at; `set_posted_at` writes a recovered date
into raw_json without disturbing other fields. `/api/discovery` buckets
new prospects by posting date (posted_at, else first_seen_at proxy).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jobbot.models import JobPosting, JobStatus
from jobbot.state import (
    connect, jobs_needing_posted_at_backfill, set_posted_at, upsert_new,
)


def _seed(db, rows):
    with connect(db) as conn:
        upsert_new(conn, [
            JobPosting(
                id=r["id"], source=r["source"], title="PM", company="Co",
                url=f"https://example.com/{r['id']}",
                apply_url=f"https://example.com/{r['id']}",
                description="body " * 30,
            ) for r in rows
        ])
        for r in rows:
            conn.execute(
                "UPDATE seen_jobs SET status=?, score=?, description_scraped=?, "
                "first_seen_at=? WHERE id=?",
                (r.get("status", "scored"), r.get("score"),
                 int(r.get("scraped", 1)), r["first_seen_at"], r["id"]),
            )
            # Optionally pre-set posted_at in raw_json
            if r.get("posted_at"):
                row = conn.execute("SELECT raw_json FROM seen_jobs WHERE id=?", (r["id"],)).fetchone()
                payload = json.loads(row["raw_json"])
                payload["posted_at"] = r["posted_at"]
                conn.execute("UPDATE seen_jobs SET raw_json=? WHERE id=?",
                             (json.dumps(payload), r["id"]))


# ---------------------------------------------------------------------------
# jobs_needing_posted_at_backfill
# ---------------------------------------------------------------------------

def test_backfill_selects_only_jsonld_sources_without_date(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime.now(timezone.utc).isoformat()
    _seed(db, [
        {"id": "dr1", "source": "dailyremote", "first_seen_at": now},          # eligible
        {"id": "xi1", "source": "xing", "first_seen_at": now},                  # eligible
        {"id": "st1", "source": "stepstone", "first_seen_at": now},            # eligible
        {"id": "wwr1", "source": "weworkremotely", "first_seen_at": now},      # not in allow-list
        {"id": "dr2", "source": "dailyremote", "first_seen_at": now,
         "posted_at": "2026-05-01"},                                            # already has date
    ])
    with connect(db) as conn:
        jobs = jobs_needing_posted_at_backfill(
            conn, ("dailyremote", "xing", "stepstone"), limit=50)
    ids = {j.id for j in jobs}
    assert ids == {"dr1", "xi1", "st1"}, f"unexpected selection: {ids}"
    assert "wwr1" not in ids       # RSS source excluded by allow-list
    assert "dr2" not in ids        # already has posted_at


def test_backfill_skips_unenriched_rows(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime.now(timezone.utc).isoformat()
    _seed(db, [
        {"id": "dr1", "source": "dailyremote", "first_seen_at": now, "scraped": 1},
        {"id": "dr2", "source": "dailyremote", "first_seen_at": now, "scraped": 0},
    ])
    with connect(db) as conn:
        jobs = jobs_needing_posted_at_backfill(conn, ("dailyremote",), limit=50)
    assert {j.id for j in jobs} == {"dr1"}


def test_backfill_respects_limit(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime.now(timezone.utc)
    _seed(db, [
        {"id": f"dr{i}", "source": "dailyremote",
         "first_seen_at": (now - timedelta(hours=i)).isoformat()}
        for i in range(10)
    ])
    with connect(db) as conn:
        jobs = jobs_needing_posted_at_backfill(conn, ("dailyremote",), limit=3)
    assert len(jobs) == 3


# ---------------------------------------------------------------------------
# set_posted_at
# ---------------------------------------------------------------------------

def test_set_posted_at_writes_into_raw_json(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime.now(timezone.utc).isoformat()
    _seed(db, [{"id": "dr1", "source": "dailyremote", "first_seen_at": now}])
    with connect(db) as conn:
        set_posted_at(conn, "dr1", "2026-05-10T00:00:00+00:00")
        conn.commit()
        row = conn.execute("SELECT raw_json FROM seen_jobs WHERE id='dr1'").fetchone()
    assert json.loads(row["raw_json"])["posted_at"] == "2026-05-10T00:00:00+00:00"


def test_set_posted_at_does_not_clobber_existing(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime.now(timezone.utc).isoformat()
    _seed(db, [{"id": "dr1", "source": "dailyremote", "first_seen_at": now,
                "posted_at": "2026-05-01"}])
    with connect(db) as conn:
        set_posted_at(conn, "dr1", "2026-05-10")  # should be ignored
        conn.commit()
        row = conn.execute("SELECT raw_json FROM seen_jobs WHERE id='dr1'").fetchone()
    assert json.loads(row["raw_json"])["posted_at"] == "2026-05-01"


# ---------------------------------------------------------------------------
# /api/discovery endpoint
# ---------------------------------------------------------------------------

def test_discovery_endpoint_buckets_by_posting_date(tmp_path, monkeypatch):
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    today = datetime.now(timezone.utc)
    d_today = today.date().isoformat()
    d_yest = (today - timedelta(days=1)).date().isoformat()
    _seed(db, [
        # posted today, real date, shortlisted
        {"id": "a", "source": "xing", "first_seen_at": today.isoformat(),
         "posted_at": today.isoformat(), "score": 85, "status": "scored"},
        # posted today, real date, NOT shortlisted (expired)
        {"id": "b", "source": "xing", "first_seen_at": today.isoformat(),
         "posted_at": today.isoformat(), "score": 80, "status": "listing_expired"},
        # no posted_at -> falls back to first_seen (yesterday), proxy
        {"id": "c", "source": "linkedin",
         "first_seen_at": (today - timedelta(days=1)).isoformat(),
         "score": 90, "status": "scored"},
    ])
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/discovery?days=7&weeks=4").get_json()

    by_day = {d["date"]: d for d in payload["per_day"]}
    assert by_day[d_today]["scanned"] == 2
    assert by_day[d_today]["matches"] == 1       # only 'a' (b is expired)
    assert by_day[d_today]["real_date_pct"] == 100  # both a,b have posted_at
    assert by_day[d_yest]["scanned"] == 1        # 'c' via first_seen proxy
    assert by_day[d_yest]["real_date_pct"] == 0  # proxy, no real posted_at
