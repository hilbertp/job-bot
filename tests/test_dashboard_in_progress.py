"""Dashboard in-progress visibility:

- /api/latest-run-portal-hits returns description counts via the seen_jobs
  fallback while a run has no finished_at yet, so the dashboard isn't blank
  mid-run.
- The response carries in_progress + elapsed_sec so the client can poll.
- /runs/<id> renders an in-progress badge and the meta-refresh tag while the
  run is open, and falls back to seen_jobs-derived stage counts.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting
from jobbot.state import (
    connect,
    finish_run,
    request_run_control,
    start_run,
    update_enrichment,
    upsert_new,
)


def _seed_in_progress_run(db_path: Path) -> tuple[int, list[str]]:
    """Insert a run that has NOT been finished, with 2 jobs (one with body)."""
    jobs = [
        JobPosting(
            id="ip_full",
            source="working_nomads",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/ip_full",  # type: ignore
            apply_url="https://example.com/jobs/ip_full",  # type: ignore
            description="snippet",
        ),
        JobPosting(
            id="ip_missing",
            source="working_nomads",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/ip_missing",  # type: ignore
            apply_url="https://example.com/jobs/ip_missing",  # type: ignore
            description="snippet",
        ),
    ]
    with connect(db_path) as conn:
        run_id = start_run(conn)
        upsert_new(conn, jobs)
        update_enrichment(
            conn,
            "ip_full",
            description_full=" ".join(["responsibility"] * 240),
            description_scraped=True,
            description_word_count=240,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        # NOTE: deliberately no finish_run — leaves finished_at NULL.
    return run_id, [j.id for j in jobs]


def test_portal_hits_in_progress_uses_seen_jobs_fallback(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/latest-run-portal-hits").get_json()

    assert payload["run_id"] == run_id
    assert payload["in_progress"] is True
    assert payload["finished_at"] is None
    assert payload["elapsed_sec"] >= 0
    assert payload["per_portal"] == {"working_nomads": 2}
    assert payload["total"] == 2
    assert payload["per_portal_description"]["working_nomads"] == {
        "total": 2,
        "with_description": 1,
        "percent_with_description": 50.0,
    }
    assert payload["total_with_description"] == 1
    assert payload["percent_with_description"] == 50.0


def test_portal_hits_completed_run_still_uses_summary(tmp_path: Path, monkeypatch) -> None:
    """The new in-progress fallback must not regress finished runs — they
    keep reading per_source_fetched from summary_json verbatim."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, ids = _seed_in_progress_run(db)
    with connect(db) as conn:
        finish_run(
            conn,
            run_id,
            n_fetched=2,
            n_new=2,
            summary={
                "per_source_fetched": {"working_nomads": 2},
                "per_source_new": {"working_nomads": 2},
                "fetched_ids": ids,
            },
        )

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/latest-run-portal-hits").get_json()

    assert payload["in_progress"] is False
    assert payload["finished_at"] is not None
    assert payload["per_portal"] == {"working_nomads": 2}
    assert payload["percent_with_description"] == 50.0


def test_run_detail_page_marks_in_progress(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "in progress" in html
    assert 'http-equiv="refresh"' in html  # auto-refreshes itself
    # Live fallback stage counts come from seen_jobs since started_at.
    # The fixture inserted 2 jobs, one enriched → fetched=2, enriched=1.
    assert "<strong>2</strong>" in html
    assert "<strong>1</strong>" in html


def test_run_detail_page_exposes_pause_resume_stop_controls(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)

    assert 'data-run-controls' in html
    assert 'data-run-action="pause"' in html
    assert 'data-run-action="stop"' in html
    assert 'data-run-action="resume"' not in html
    assert f"/api/runs/${{runId}}/control" in html


def test_run_detail_page_paused_run_shows_play_and_stop_controls(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)
    with connect(db) as conn:
        request_run_control(conn, run_id, "paused", reason="test")

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)

    assert 'data-run-action="resume"' in html
    assert 'data-run-action="stop"' in html
    assert 'data-run-action="pause"' not in html


def test_run_control_stop_marks_stale_in_progress_run_finished(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.post(f"/api/runs/{run_id}/control", json={"action": "stop"})

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["requested_state"] == "stopped"
    with connect(db) as conn:
        row = conn.execute(
            "SELECT finished_at, summary_json FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    assert row["finished_at"] is not None
    assert '"stopped": true' in row["summary_json"]

    html = client.get(f"/runs/{run_id}").get_data(as_text=True)
    assert 'data-run-action="start"' in html
    assert 'data-run-action="pause"' not in html
    assert 'data-run-action="stop"' not in html


def test_run_detail_page_formats_run_times_and_shows_enrichment_progress(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)
    with connect(db) as conn:
        update_enrichment(
            conn,
            "ip_missing",
            description_full="snippet",
            description_scraped=False,
            description_word_count=1,
            seniority=None,
            salary_text=None,
            apply_email=None,
        )

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    assert "Started: 20" not in text  # no raw ISO block like 2026-05-12T...
    assert "Enrichment Attempted: 2" in text
    assert "No Description: 1" in text
    assert "Enrichment Pending: 0" in text
    assert "Enriched No Description Pending" in text


def test_run_detail_page_renders_live_portal_table(tmp_path: Path, monkeypatch) -> None:
    """Run-detail page server-renders the per-portal hits table so the user
    can see WHICH source is producing while the run is still streaming."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)

    assert "Hits per Portal" in html
    assert "working_nomads" in html
    # 1 of 2 enriched → 50.0% with description for working_nomads
    assert "50.0%" in html


def test_run_detail_page_shows_current_stage_label(tmp_path: Path, monkeypatch) -> None:
    """The in-progress run shows a 'Currently: <stage>' label inferred from
    DB counts. With 2 fetched + 1 enriched, the pipeline is still enriching."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)

    assert "Currently:" in html
    assert "<strong>enriching</strong>" in html


def test_run_detail_page_no_in_progress_artifacts_after_finish(
    tmp_path: Path, monkeypatch,
) -> None:
    """Finished runs do NOT auto-refresh and do NOT show the 'Currently:'
    label, but the portal table is still rendered from the summary."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, ids = _seed_in_progress_run(db)
    with connect(db) as conn:
        finish_run(
            conn, run_id,
            n_fetched=2, n_new=2,
            summary={
                "per_source_fetched": {"working_nomads": 2},
                "fetched_ids": ids,
                "stages": {"fetched": 2, "enriched": 1, "scored": 1, "generated": 0},
            },
        )

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get(f"/runs/{run_id}").get_data(as_text=True)
    assert 'http-equiv="refresh"' not in html
    assert "Currently:" not in html
    assert "control: finished" in html
    assert "data-run-action=\"pause\"" not in html
    assert "Current:" not in html
    assert "working_nomads" in html


def test_dashboard_home_exposes_live_run_progress_polling(
    tmp_path: Path, monkeypatch,
) -> None:
    """User journey: while a scrape run is still open, the dashboard home page
    must visibly show live progress and keep polling without a manual refresh."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, _ = _seed_in_progress_run(db)

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'id="run-banner"' in html
    assert 'id="run-banner-text"' in html
    assert 'id="run-banner-link"' in html
    assert "Run in progress" in html
    assert f'href="/runs/{run_id}"' in html  # recent-runs history still links to the run.

    assert "fetch('/api/latest-run-portal-hits')" in html
    assert "fetch('/api/latest-run-jobs')" in html
    assert "updateRunBanner(hits)" in html
    assert "hits.in_progress" in html
    assert "setInterval(loadStage1Data, LIVE_POLL_MS)" in html
    assert "clearInterval(livePollTimer)" in html
    assert "LIVE_POLL_MS = 5000" in html
    assert "`/runs/${hits.run_id}`" in html

    assert 'id="portal-counts-body"' in html
    assert 'id="portal-counts-total"' in html
    assert "% With Description" in html


def test_dashboard_stage1_panel_summarises_hits_and_portals(
    tmp_path: Path, monkeypatch,
) -> None:
    """User journey: in Stage 1, I can see at a glance how many hits the
    latest run produced and how many portals contributed — that's what
    belongs in the header, not when the run finished (that lives in
    Recent Runs)."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    run_id, ids = _seed_in_progress_run(db)
    with connect(db) as conn:
        finish_run(
            conn,
            run_id,
            n_fetched=2,
            n_new=2,
            summary={
                "per_source_fetched": {"working_nomads": 2},
                "per_source_new": {"working_nomads": 2},
                "fetched_ids": ids,
            },
        )

    client = _load_legacy_dashboard_module().app.test_client()

    payload = client.get("/api/latest-run-portal-hits").get_json()
    assert payload["run_id"] == run_id
    assert payload["in_progress"] is False

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # New header badges: hits + portals.
    assert "Stage 1: Hits per Portal" in html
    assert 'id="stage1-total-hits"' in html
    assert 'id="stage1-portals-count"' in html
    assert "Hits" in html
    assert "Portals" in html
    assert "updateStage1HeaderBadges" in html
    assert "hits.total" in html
    assert "hits.per_portal" in html


def test_dashboard_panels_start_collapsed_with_chevrons_and_expand_collapse_function(
    tmp_path: Path, monkeypatch,
) -> None:
    """User journey: each dashboard panel can be collapsed and expanded from
    its header via a chevron button, and starts collapsed on page load."""
    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")

    expected_panels = {
        "stage1-panel": "stage1-panel-body",
        "stage2-panel": "stage2-panel-body",
        "stage3-panel": "stage3-panel-body",
        "stage4-panel": "stage4-panel-body",
        "recent-runs-panel": "recent-runs-panel-body",
    }
    for panel_id, body_id in expected_panels.items():
        panel = soup.find(id=panel_id)
        assert panel is not None, f"missing dashboard panel: {panel_id}"
        assert panel.has_attr("data-collapsible-panel")

        body = panel.find(id=body_id)
        assert body is not None, f"{panel_id} missing collapsible body"
        assert body.has_attr("data-panel-body")
        assert "hidden" in (body.get("class") or [])

        toggle = panel.find(attrs={"data-panel-toggle": True})
        assert toggle is not None, f"{panel_id} missing expand/collapse button"
        assert toggle.get("aria-controls") == body_id
        assert toggle.get("aria-expanded") == "false"

        icon = toggle.find(attrs={"data-panel-toggle-icon": True})
        assert icon is not None, f"{panel_id} missing chevron icon"
        assert icon.get_text(strip=True) == "▸"

        header = panel.find(attrs={"data-panel-header": True})
        assert header is not None, f"{panel_id} missing clickable header"
        assert header.get("aria-expanded") == "false"

    assert "function initCollapsiblePanels()" in html
    assert "function setPanelExpanded(button, body, expanded)" in html
    assert "button.addEventListener('click'" in html
    assert "body.classList.toggle('hidden', !expanded)" in html
    assert "button.setAttribute('aria-expanded', String(expanded))" in html
    assert "icon.textContent = expanded ? '▾' : '▸'" in html


def test_dashboard_panel_headers_hover_across_full_collapsed_surface(
    tmp_path: Path, monkeypatch,
) -> None:
    """Regression: the mouse hover/click target must cover the full width
    and height of each collapsed panel header, not only the text row."""
    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")

    panel_ids = [
        "stage1-panel",
        "stage2-panel",
        "stage3-panel",
        "stage4-panel",
        "recent-runs-panel",
    ]
    for panel_id in panel_ids:
        panel = soup.find(id=panel_id)
        assert panel is not None, f"missing dashboard panel: {panel_id}"
        panel_classes = panel.get("class") or []

        # No container padding: otherwise the card edges become dead hover
        # space around the actual header. `overflow-hidden` lets the header
        # hover background fill cleanly to the rounded border.
        assert "overflow-hidden" in panel_classes
        assert not any(cls.startswith("p-") or cls.startswith("px-") or cls.startswith("py-")
                       for cls in panel_classes), panel_classes

        header = panel.find(attrs={"data-panel-header": True})
        assert header is not None, f"{panel_id} missing header"
        assert header.parent == panel
        assert header == panel.find(recursive=False)

        header_classes = header.get("class") or []
        assert "w-full" in header_classes
        assert "cursor-pointer" in header_classes
        assert "hover:bg-white/10" in header_classes
        assert "px-6" in header_classes
        assert "py-5" in header_classes

        # Margins do not receive hover/click background, so a header margin
        # would create a dead strip inside the collapsed panel's visible box.
        assert not any(
            cls.startswith(("m-", "mx-", "my-", "mt-", "mr-", "mb-", "ml-"))
            or cls.startswith(("-mx-", "-my-", "-mt-", "-mr-", "-mb-", "-ml-"))
            for cls in header_classes
        ), header_classes
