"""End-to-end wiring of PRD §7.7 FR-APP-01 application channel through
the API surfaces (shortlist + latest-run-jobs), the Stage 2 dashboard
column, and the digest template.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from jobbot.dashboard.server import _load_legacy_dashboard_module
from jobbot.models import JobPosting, JobStatus
from jobbot.state import (
    connect,
    finish_run,
    start_run,
    update_enrichment,
    update_status,
    upsert_new,
)


def _seed_one_per_channel(db: Path) -> list[str]:
    """A row for each channel state so APIs/templates have material to render."""
    rows = [
        # email channel — apply_email set
        ("apply_email_only", "stepstone",
         "https://stepstone.de/jobs/1", None, "careers@acme.com"),
        # form channel — Greenhouse URL
        ("apply_form_greenhouse", "linkedin",
         "https://boards.greenhouse.io/acme/jobs/123",
         "https://boards.greenhouse.io/acme/jobs/123", None),
        # external channel — non-ATS URL
        ("apply_external", "weworkremotely",
         "https://acme.com/careers/pm", "https://acme.com/careers/pm", None),
        # manual — no email, no url
        ("apply_manual", "freelancermap", "https://freelancermap.de/p/4", None, None),
    ]
    with connect(db) as conn:
        run_id = start_run(conn)
        jobs = [
            JobPosting(
                id=jid, source=src, title="Senior PM", company="Acme",
                url=url,  # type: ignore
                apply_url=apply_url,  # type: ignore
                description="snippet",
            )
            for jid, src, url, apply_url, _ in rows
        ]
        upsert_new(conn, jobs)
        for jid, _, _, _, email in rows:
            update_enrichment(
                conn, jid,
                description_full=" ".join(["responsibility"] * 240),
                description_scraped=True,
                description_word_count=240,
                seniority="Senior",
                salary_text=None,
                apply_email=email,
            )
            update_status(conn, jid, JobStatus.SCORED, score=85, reason="fit")
        for jid in ["apply_email_only", "apply_form_greenhouse"]:
            update_status(conn, jid, JobStatus.GENERATED, output_dir=None)
        finish_run(
            conn, run_id,
            n_fetched=len(rows), n_new=len(rows),
            summary={
                "per_source_fetched": {r[1]: 1 for r in rows},
                "fetched_ids": [r[0] for r in rows],
            },
        )
    return [r[0] for r in rows]


def test_shortlist_api_includes_apply_channel(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_one_per_channel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/shortlist?min_score=0").get_json()
    by_id = {j["id"]: j for j in payload["jobs"]}

    assert by_id["apply_email_only"]["apply_channel"] == "email"
    assert by_id["apply_form_greenhouse"]["apply_channel"] == "form"
    assert by_id["apply_form_greenhouse"]["apply_channel_ats_name"] == "Greenhouse"
    assert by_id["apply_external"]["apply_channel"] == "external"
    assert by_id["apply_manual"]["apply_channel"] == "manual"


def test_latest_run_jobs_api_includes_apply_channel(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_one_per_channel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/latest-run-jobs").get_json()
    channels = {j["title"]: j.get("apply_channel") for j in payload}
    # All four rows share the title 'Senior PM' so channels are duplicated.
    # We care that at least one of each shows up in the response.
    found = {j["apply_channel"] for j in payload}
    assert {"email", "form", "external", "manual"}.issubset(found)
    assert any(j.get("apply_channel_ats_name") == "Greenhouse" for j in payload)


def test_stage2_template_renders_apply_via_column(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_one_per_channel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)

    assert "Apply via" in html
    assert "applyChannelCell(job)" in html
    # Click-to-sort wired on column headers
    assert 'data-stage1-sort="apply_channel"' in html
    assert "stage1SortRows" in html
    # 8 columns total
    assert 'colspan="8"' in html


def test_digest_template_renders_channel_pill_and_source_summary(tmp_path: Path) -> None:
    template_dir = Path(__file__).resolve().parents[1] / "src" / "jobbot" / "notify" / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("digest.html.j2")

    from datetime import datetime, timezone
    matches = [
        {"job": {"title": "PM A", "company": "Acme", "url": "https://acme.com", "source": "stepstone", "location": None},
         "score": 82, "reason": "fit", "output_dir": "/tmp/x", "cover_letter_html": "",
         "apply_status": None, "apply_email": "careers@acme.com", "apply_url": None,
         "apply_channel": "email", "apply_channel_ats_name": None},
        {"job": {"title": "PM B", "company": "Beta", "url": "https://gh.io/x", "source": "linkedin", "location": None},
         "score": 78, "reason": "fit", "output_dir": "/tmp/y", "cover_letter_html": "",
         "apply_status": None, "apply_email": None, "apply_url": "https://boards.greenhouse.io/x/123",
         "apply_channel": "form", "apply_channel_ats_name": "Greenhouse"},
        {"job": {"title": "PM C", "company": "Gamma", "url": "https://gamma.com/jobs/1", "source": "stepstone", "location": None},
         "score": 75, "reason": "fit", "output_dir": None, "cover_letter_html": "",
         "apply_status": None, "apply_email": None, "apply_url": None,
         "apply_channel": "manual", "apply_channel_ats_name": None},
    ]
    html = template.render(
        n=len(matches), matches=matches, errors=[],
        run_started=datetime.now(tz=timezone.utc),
        cannot_score=[],
    )

    # Channel pills next to score
    assert "📧 email" in html
    assert "🔗 Greenhouse" in html
    assert "✋ manual" in html
    # Per-source breakdown section
    assert "Per-source apply channels" in html
    assert "stepstone" in html
    assert "via email" in html
    assert "via form" in html
