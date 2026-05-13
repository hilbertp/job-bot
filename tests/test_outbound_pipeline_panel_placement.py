"""Stage 4 hosts the CRM (Outbound Pipeline) card view.

Earlier this lived as a separate `outbound-pipeline-panel` after Recent
Runs, which duplicated Stage 4's "Application Outcomes" surface — Stage 4
showed a read-only table while the CRM with state-transition buttons was
in a different panel further down. The user called this a regression.

Post-fix invariants pinned here:
  1. There is NO standalone `outbound-pipeline-panel` section.
  2. The CRM hooks (`outbound-pipeline-body`, `outbound-pipeline-count`,
     `[data-outbound-filters]`) live INSIDE `#stage4-panel`.
  3. The Stage 4 panel stays collapsible.
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


def test_no_standalone_outbound_pipeline_panel(
    tmp_path: Path, monkeypatch,
) -> None:
    """The duplicate panel must be gone. Its CRM features moved INTO
    Stage 4 so the user has one place to manage applications, not two."""
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")
    panel_ids = [s.get("id") for s in soup.select("section[id]")]
    assert "outbound-pipeline-panel" not in panel_ids, (
        "Outbound Pipeline panel should not exist as a standalone section "
        f"— Stage 4 is the canonical CRM host. Got: {panel_ids}"
    )


def test_crm_view_lives_inside_stage4(tmp_path: Path, monkeypatch) -> None:
    """The card-view DOM hooks must be inside Stage 4 so the existing
    loadOutboundPipeline() / renderOutboundCard() JS keeps working."""
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")
    stage4 = soup.find(id="stage4-panel")
    assert stage4 is not None, "Stage 4 panel must exist"

    # The three hooks the CRM JS reaches for must be Stage-4 descendants.
    for hook_id in ("outbound-pipeline-body", "outbound-pipeline-count",
                    "outbound-pipeline-empty"):
        el = stage4.find(id=hook_id)
        assert el is not None, (
            f"#{hook_id} must live inside #stage4-panel after the "
            f"Outbound Pipeline → Stage 4 merge"
        )

    # The filter chip row is identified by data-outbound-filters and must
    # also be inside Stage 4.
    filters = stage4.find(attrs={"data-outbound-filters": True})
    assert filters is not None, (
        "filter chips (`[data-outbound-filters]`) must live inside Stage 4"
    )
    # All six bucket filters + the "all" chip are present (one button per
    # filter value); the JS depends on them.
    filter_values = {b.get("data-filter")
                     for b in filters.find_all("button", attrs={"data-filter": True})}
    assert {"all", "waiting", "received", "replied",
            "interview", "rejected", "bounced"} <= filter_values


def test_stage4_panel_is_collapsible(tmp_path: Path, monkeypatch) -> None:
    """Stage 4 inherits the same collapsible-panel contract as the other
    sections (it always did, but pinning here in case a future refactor
    drops the data-collapsible-panel marker)."""
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.find(id="stage4-panel")
    assert panel is not None
    assert panel.has_attr("data-collapsible-panel")
    header = panel.find(attrs={"data-panel-header": True})
    assert header is not None
    assert header.get("aria-controls") == "stage4-panel-body"
    body = panel.find(id="stage4-panel-body")
    assert body is not None
    assert "hidden" in (body.get("class") or [])
    assert body.has_attr("data-panel-body")
