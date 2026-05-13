"""Stage 2 PO/PM Shortlist exposes per-row description_scraped state.

The user needs an at-a-glance signal in the Stage 2 panel for whether each
listing's full body was scraped (and thus actually scored against the CV).
The signal is two columns on the API and one cell on the table:

- description_scraped: True / False / None (None = predates enrichment)
- description_word_count: int when scraped, else None.
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


def _seed_run_with_scraped_and_unscraped(db: Path) -> int:
    jobs = [
        JobPosting(
            id="scraped_one", source="stepstone", title="Product Manager", company="A",
            url="https://example.com/jobs/scraped_one",  # type: ignore
            apply_url="https://example.com/jobs/scraped_one",  # type: ignore
            description="snippet",
        ),
        JobPosting(
            id="no_body", source="stepstone", title="Product Owner", company="B",
            url="https://example.com/jobs/no_body",  # type: ignore
            apply_url="https://example.com/jobs/no_body",  # type: ignore
            description="snippet",
        ),
    ]
    with connect(db) as conn:
        run_id = start_run(conn)
        upsert_new(conn, jobs)
        update_enrichment(
            conn, "scraped_one",
            description_full=" ".join(["responsibility"] * 240),
            description_scraped=True,
            description_word_count=240,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_enrichment(
            conn, "no_body",
            description_full="",
            description_scraped=False,
            description_word_count=0,
            seniority=None,
            salary_text=None,
            apply_email=None,
        )
        finish_run(
            conn, run_id,
            n_fetched=2, n_new=2,
            summary={
                "per_source_fetched": {"stepstone": 2},
                "fetched_ids": [j.id for j in jobs],
            },
        )
    return run_id


def test_latest_run_jobs_includes_description_scraped(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_run_with_scraped_and_unscraped(db)

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/latest-run-jobs").get_json()

    by_id = {j["title"]: j for j in payload}
    assert by_id["Product Manager"]["description_scraped"] is True
    assert by_id["Product Manager"]["description_word_count"] == 240
    assert by_id["Product Owner"]["description_scraped"] is False
    assert by_id["Product Owner"]["description_word_count"] == 0


def test_stage2_table_renders_description_scraped_column(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_run_with_scraped_and_unscraped(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)

    # Column header in the Stage 2 table
    assert "Description Scraped" in html
    # JS renderer is hooked up
    assert "descriptionScrapedCell(job)" in html
    # The renderer reads the two fields we just added to the API
    assert "job.description_scraped === true" in html
    assert "job.description_word_count" in html
    # Stage 2 has 10 columns once Company lands; loading/empty states span them.
    assert 'colspan="10"' in html


def test_stage2_table_renders_company_column(
    tmp_path: Path, monkeypatch,
) -> None:
    """Product journey stage 2: the employer must be visible alongside the
    job title at the scrape stage. Without this, the user has to follow
    the link to find out who is hiring."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_run_with_scraped_and_unscraped(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)

    # Column header + sort key
    assert ">Company<" in html
    assert 'data-stage1-sort="company"' in html
    # Row template reads job.company
    assert "${job.company || ''}" in html

    # The API ships company per row so the front-end has something to render.
    payload = client.get("/api/latest-run-jobs").get_json()
    companies = {j["company"] for j in payload}
    assert {"A", "B"}.issubset(companies)
