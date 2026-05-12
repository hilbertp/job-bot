"""The Outbound Pipeline panel:
  1. Must be the LAST panel on the dashboard (after Recent Runs).
  2. Must be collapsible like the other panels (data-collapsible-panel).
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from jobbot.dashboard.server import _load_legacy_dashboard_module


def _dashboard_html(tmp_path: Path, monkeypatch) -> str:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    client = _load_legacy_dashboard_module().app.test_client()
    return client.get("/").get_data(as_text=True)


def test_outbound_pipeline_is_the_last_panel_on_the_dashboard(
    tmp_path: Path, monkeypatch,
) -> None:
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")
    panel_ids = [s.get("id") for s in soup.select("section[id]")]
    # We expect (in order): stage1, stage2, stage3, stage4, recent-runs, outbound
    assert "outbound-pipeline-panel" in panel_ids
    assert panel_ids[-1] == "outbound-pipeline-panel", (
        f"Outbound Pipeline should be the last panel; got order: {panel_ids}"
    )
    # And it must come AFTER Recent Runs specifically
    assert panel_ids.index("outbound-pipeline-panel") > panel_ids.index("recent-runs-panel")


def test_outbound_pipeline_is_collapsible(tmp_path: Path, monkeypatch) -> None:
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find(id="outbound-pipeline-panel")
    assert panel is not None
    assert panel.has_attr("data-collapsible-panel"), (
        "panel must carry data-collapsible-panel so the dashboard's "
        "collapsible-panel JS picks it up"
    )
    # Header carries the click affordance + aria-controls hook
    header = panel.find(attrs={"data-panel-header": True})
    assert header is not None
    assert header.get("aria-controls") == "outbound-pipeline-panel-body"
    # Body starts hidden (matches the other panels' default-collapsed state)
    body = panel.find(id="outbound-pipeline-panel-body")
    assert body is not None
    assert "hidden" in (body.get("class") or [])
    assert body.has_attr("data-panel-body")
