"""/api/runs/stop: kill switch reachable from the published dashboard.

The local Flask dashboard already had pause/resume/stop keyed by run id, but
the static Pages site cannot know the id, so there was no way to stop a run
from the surface the user actually looks at. A 90-minute run with no brake is
a design defect, not a missing nicety.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.state import connect, run_control_state, start_run

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


def test_stop_requests_control_state_for_the_newest_run(client):
    c, db = client
    with connect(db) as conn:
        old = start_run(conn)
        conn.execute("UPDATE runs SET finished_at = '2026-08-10T10:00:00+00:00'"
                     " WHERE id = ?", (old,))
        live = start_run(conn)

    resp = c.post("/api/runs/stop")
    body = resp.get_json()
    assert resp.status_code == 200
    # "stopping", not "stopped": the run unwinds at its next checkpoint.
    assert body == {"ok": True, "status": "stopping", "run_id": live}
    with connect(db) as conn:
        assert run_control_state(conn, live)["requested_state"] == "stopped"
        # The row is closed too, so a run whose process is already wedged can
        # be cleared from the published page (run 347 sat unfinished 32h).
        row = conn.execute("SELECT finished_at, summary_json FROM runs"
                           " WHERE id = ?", (live,)).fetchone()
        assert row["finished_at"] is not None
        assert "stopped" in (row["summary_json"] or "")


def test_stop_with_nothing_running_is_a_clean_409(client):
    c, _ = client
    resp = c.post("/api/runs/stop")
    assert resp.status_code == 409
    assert resp.get_json()["status"] == "no_active_run"


def test_finished_runs_are_never_targeted(client):
    c, db = client
    with connect(db) as conn:
        done = start_run(conn)
        conn.execute("UPDATE runs SET finished_at = '2026-08-10T10:00:00+00:00'"
                     " WHERE id = ?", (done,))
    assert c.post("/api/runs/stop").status_code == 409


def test_preflight_is_answered_for_the_pages_origin(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(dashboard, "_pages_origin",
                        lambda: "https://hilbertp.github.io")
    resp = c.open("/api/runs/stop", method="OPTIONS",
                  headers={"Origin": "https://hilbertp.github.io"})
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "https://hilbertp.github.io"
    # Chromium needs this for a public page to reach localhost.
    assert resp.headers["Access-Control-Allow-Private-Network"] == "true"


def test_other_origins_get_no_cors_grant(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(dashboard, "_pages_origin",
                        lambda: "https://hilbertp.github.io")
    resp = c.post("/api/runs/stop", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_a_zombie_row_is_not_stoppable(client):
    """The bug this pairs with: "newest unfinished" is not "running".

    The runs table carries rows whose process was killed without closing them
    (274, 291, 294). Targeting the newest unfinished row made the kill switch
    report "stopping run 291" while nothing was running, mutating July history
    and contradicting the panel beside it.
    """
    c, db = client
    with connect(db) as conn:
        zombie = start_run(conn)
        conn.execute("UPDATE runs SET started_at = '2026-07-30T10:00:00+00:00'"
                     " WHERE id = ?", (zombie,))

    resp = c.post("/api/runs/stop")
    assert resp.status_code == 409
    assert resp.get_json()["status"] == "no_active_run"
    with connect(db) as conn:
        # Untouched: no finished_at invented, no stop reason written.
        row = conn.execute("SELECT finished_at FROM runs WHERE id = ?",
                           (zombie,)).fetchone()
        assert row["finished_at"] is None


def test_stop_and_active_agree_on_what_is_running(client):
    """One definition of "live", shared by both endpoints."""
    c, db = client
    with connect(db) as conn:
        stale = start_run(conn)
        conn.execute("UPDATE runs SET started_at = '2026-07-30T10:00:00+00:00'"
                     " WHERE id = ?", (stale,))
    assert c.get("/api/runs/active").get_json()["active"] is False
    assert c.post("/api/runs/stop").status_code == 409
