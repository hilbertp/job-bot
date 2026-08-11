"""Abandoned run rows get closed instead of haunting the dashboard forever."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jobbot.state import (
    connect, reap_abandoned_runs, run_control_state, start_run,
    update_run_stage_progress,
)


def _db(tmp_path: Path) -> Path:
    return tmp_path / "reaper.db"


def test_overtaken_row_is_closed_at_its_last_sign_of_life(tmp_path: Path):
    """Backdated, not stamped now: run 274 was killed on 2026-07-23 and
    closing it on 2026-08-11 would invent a nineteen-day run in the history."""
    db = _db(tmp_path)
    with connect(db) as conn:
        zombie = start_run(conn)
        update_run_stage_progress(conn, zombie, "scrape", total=29, completed=5)
        last_seen = conn.execute(
            "SELECT updated_at FROM run_stage_progress WHERE run_id = ?",
            (zombie,),
        ).fetchone()[0]
        start_run(conn)  # a later run: proof the zombie's process is gone

        assert reap_abandoned_runs(conn) == [zombie]

        row = conn.execute(
            "SELECT finished_at, summary_json FROM runs WHERE id = ?", (zombie,)
        ).fetchone()
        assert row["finished_at"] == last_seen
        assert json.loads(row["summary_json"]) == {"abandoned": True}
        assert run_control_state(conn, zombie)["requested_state"] == "stopped"


def test_newest_open_row_is_left_alone(tmp_path: Path):
    """A slow run with nothing behind it may still be alive; only the pipeline,
    holding the file lock, is allowed to declare that one dead."""
    db = _db(tmp_path)
    with connect(db) as conn:
        old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
        run_id = start_run(conn)
        conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (old, run_id))

        assert reap_abandoned_runs(conn) == []
        assert conn.execute(
            "SELECT finished_at FROM runs WHERE id = ?", (run_id,)
        ).fetchone()[0] is None

        # Under the lock every open row is a corpse.
        assert reap_abandoned_runs(conn, superseded_only=False) == [run_id]
        assert conn.execute(
            "SELECT finished_at FROM runs WHERE id = ?", (run_id,)
        ).fetchone()[0] == old


def test_finished_runs_are_untouched(tmp_path: Path):
    db = _db(tmp_path)
    with connect(db) as conn:
        done = start_run(conn)
        stamp = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE runs SET finished_at = ? WHERE id = ?", (stamp, done))

        assert reap_abandoned_runs(conn, superseded_only=False) == []
        assert conn.execute(
            "SELECT finished_at FROM runs WHERE id = ?", (done,)
        ).fetchone()[0] == stamp
