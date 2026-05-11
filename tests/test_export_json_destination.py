"""POST /api/export/jobs writes to the user's Downloads folder (or the
JOBBOT_EXPORT_DIR override for tests), not into the repo. Pinned so
nobody accidentally re-wires the dashboard's Export button to dump JSON
back into data/exports/ where git can pick it up.
"""
from __future__ import annotations

import json
from pathlib import Path

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting
from jobbot.state import connect, update_status, upsert_new
from jobbot.models import JobStatus


def _seed(db: Path) -> None:
    job = JobPosting(
        id="export_one",
        source="working_nomads",
        title="Senior PM",
        company="Acme",
        url="https://example.com/jobs/export_one",  # type: ignore
        apply_url="https://example.com/jobs/export_one",  # type: ignore
        description="snippet",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        update_status(conn, "export_one", JobStatus.SCORED, score=85, reason="fit")


def test_export_writes_to_jobbot_export_dir_override(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db)

    export_dir = tmp_path / "Downloads"
    monkeypatch.setenv("JOBBOT_EXPORT_DIR", str(export_dir))

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.post("/api/export/jobs")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    out_path = Path(body["path"])
    assert out_path.parent == export_dir
    assert out_path.exists()
    assert out_path.name.startswith("jobs_export_")
    assert out_path.suffix == ".json"

    payload = json.loads(out_path.read_text())
    assert payload["n_jobs"] == 1
    assert payload["jobs"][0]["id"] == "export_one"


def test_export_default_destination_is_user_downloads(
    tmp_path: Path, monkeypatch,
) -> None:
    """With no override, the helper resolves to ~/Downloads. We don't
    actually write here — just assert the resolution logic."""
    monkeypatch.delenv("JOBBOT_EXPORT_DIR", raising=False)
    dashboard = _load_legacy_dashboard_module()
    target = dashboard._export_destination_dir()
    assert target == Path.home() / "Downloads"


def test_export_does_not_write_into_repo_data_exports(
    tmp_path: Path, monkeypatch,
) -> None:
    """Regression guard: the legacy data/exports/ path must NOT be used.
    If anyone restores it, this test fails."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db)

    export_dir = tmp_path / "Downloads"
    monkeypatch.setenv("JOBBOT_EXPORT_DIR", str(export_dir))

    client = _load_legacy_dashboard_module().app.test_client()
    body = client.post("/api/export/jobs").get_json()
    assert "data/exports" not in body["path"]
    assert "data\\exports" not in body["path"]
