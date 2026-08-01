"""/api/runs/active: live progress feed for the static site's panel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.state import connect, start_run, update_run_stage_progress

dashboard = _load_legacy_dashboard_module()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    import jobbot.state as state
    db = tmp_path / "test.db"
    monkeypatch.setattr(state, "DB_PATH", db)
    monkeypatch.setattr(dashboard, "DB_PATH", db, raising=False)
    monkeypatch.setattr(dashboard, "connect", lambda: connect(db), raising=False)
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c, db


def test_no_runs_reports_inactive(client):
    c, _ = client
    data = c.get("/api/runs/active").get_json()
    assert data == {"active": False, "last_run": None}


def test_idle_reports_last_finished_run(client):
    """Idle panel keeps the previous run on screen: the endpoint must hand
    over the newest FINISHED run, stages and telemetry included."""
    c, db = client
    telemetry = {"found": 333, "already_seen": 320, "new": 13}
    with connect(db) as conn:
        run_id = start_run(conn)
        update_run_stage_progress(conn, run_id, "enrichment", total=85,
                                  completed=1, failed=84, metadata=telemetry)
        conn.execute(
            "UPDATE runs SET finished_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
    data = c.get("/api/runs/active").get_json()
    assert data["active"] is False
    last = data["last_run"]
    assert last["id"] == run_id
    assert last["finished_at"]
    stage = next(s for s in last["stages"] if s["stage"] == "enrichment")
    assert stage["failed"] == 84
    assert stage["metadata"] == telemetry


def test_fresh_unfinished_run_reports_stages(client):
    c, db = client
    telemetry = {
        "stage_started_at": "2026-07-31T13:00:00+00:00",
        "from_this_run": 14, "backlog": 186,
        "ticker": [{"c": "Acme", "s": 87}, {"c": "Beta", "s": 55}],
        "failures": [{"c": "Gamma", "e": "no body"}],
        "n_strong": 1, "strong_threshold": 80,
    }
    with connect(db) as conn:
        run_id = start_run(conn)
        update_run_stage_progress(conn, run_id, "scoring", total=200,
                                  completed=42, failed=3,
                                  current_label="Acme, Senior PM",
                                  metadata=telemetry)
    data = c.get("/api/runs/active").get_json()
    assert data["active"] is True
    assert data["run"]["id"] == run_id
    stage = next(s for s in data["run"]["stages"] if s["stage"] == "scoring")
    assert stage["total"] == 200
    assert stage["completed"] == 42
    assert stage["failed"] == 3
    assert stage["current_label"] == "Acme, Senior PM"
    # Telemetry the static panel renders: queue split, ticker, failures.
    assert stage["metadata"] == telemetry
    assert data["run"]["last_activity"]


def test_stale_unfinished_run_reports_inactive(client):
    c, db = client
    old = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    with connect(db) as conn:
        run_id = start_run(conn)
        conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (old, run_id))
    data = c.get("/api/runs/active").get_json()
    assert data["active"] is False
    assert data["stale_run_id"] == run_id


def test_active_endpoint_gets_cors_for_pages_origin(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(dashboard, "_pages_origin",
                        lambda: "https://hilbertp.github.io")
    resp = c.get("/api/runs/active",
                 headers={"Origin": "https://hilbertp.github.io"})
    assert resp.headers["Access-Control-Allow-Origin"] == "https://hilbertp.github.io"
