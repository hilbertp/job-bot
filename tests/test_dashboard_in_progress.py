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

from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting
from jobbot.state import (
    connect,
    finish_run,
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
