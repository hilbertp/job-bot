"""E2E regression tests framed by the four user journeys.

See `docs/test_coverage_gaps.md` for the gap analysis that drove these. All
tests run offline: a `FakeScraper` produces synthetic postings, and the LLM
calls (`llm_score`, `llm_score_tailored`, `generate_documents`,
`send_digest`) are monkeypatched. No network IO, no Anthropic API key
needed beyond the dummy value in the Secrets fixture.

Journey 4 (sent/received/waiting/rejected/interview) is intentionally
absent — the backend isn't built yet (see the gap doc).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from jobbot.config import (
    Config, DigestConfig, EnrichmentConfig, Secrets, SourceConfig,
)
from jobbot.models import GeneratedDocs, JobPosting, JobStatus, ScoreResult
from jobbot.profile import Profile


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

class FakeScraper:
    """Single-job scraper. fetch() returns one snippet posting; fetch_detail()
    enriches it past MIN_BODY_WORDS so the scorer is reachable."""

    source = "fake"

    def __init__(self, job_id: str = "fake_1", title: str = "Senior Product Manager") -> None:
        self.fetch_detail_calls = 0
        self._job_id = job_id
        self._title = title

    def fetch(self, _query):
        return [
            JobPosting(
                id=self._job_id,
                source="fake",
                title=self._title,
                company="ACME",
                url=f"https://example.com/jobs/{self._job_id}",  # type: ignore
                apply_url=f"https://example.com/jobs/{self._job_id}",  # type: ignore
                description="short listing snippet",
            )
        ]

    def fetch_detail(self, job):
        self.fetch_detail_calls += 1
        long_body = " ".join(["responsibility"] * 240)  # >= MIN_BODY_WORDS (200)
        return job.model_copy(update={"description": long_body})


def _make_profile() -> Profile:
    return Profile(
        personal={"full_name": "Test", "email": "test@example.com"},
        preferences={"remote": True},
        deal_breakers={"keywords": [], "industries": [], "on_site_only": False},
        must_have_skills=[],
    )


def _make_secrets() -> Secrets:
    return Secrets(
        anthropic_api_key="dummy",
        gmail_address="x@example.com",
        gmail_app_password="x",
        notify_to="x@example.com",
    )


def _make_config(
    *,
    score_threshold: int = 70,
    generate_above: int = 90,
) -> Config:
    return Config(
        score_threshold=score_threshold,
        max_jobs_per_run=10,
        digest=DigestConfig(generate_docs_above_score=generate_above, max_per_email=100),
        enrichment=EnrichmentConfig(per_run_cap=10),
        sources={
            "fake": SourceConfig(enabled=True, auto_submit=False, queries=[{"q": "pm"}])
        },
    )


def _stub_pipeline(monkeypatch, pipeline, *, fake_scraper, llm_score_result, profile=None):
    """Apply the common offline monkeypatches and return for assertion."""
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": fake_scraper})
    monkeypatch.setattr(pipeline, "load_profile", lambda: profile or _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda _job, _profile: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline, "llm_score", lambda *_a, **_kw: llm_score_result)


# =============================================================================
# Journey 1 — "What happened to my last run?"
# =============================================================================

def test_pipeline_writes_complete_run_row_after_run(tmp_path: Path, monkeypatch) -> None:
    """run_once must insert a runs row with all counters and a summary_json
    that has the keys the dashboard reads (`stages`, `per_source_fetched`,
    `per_source_new`, `score_stats`, `top_blockers`)."""
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(),
        llm_score_result=ScoreResult(score=42, reason="below threshold"),
    )

    pipeline.run_once(_make_config(), _make_secrets())

    with connect(db) as conn:
        row = conn.execute(
            "SELECT id, started_at, finished_at, n_fetched, n_new, "
            "n_generated, n_applied, n_errors, summary_json "
            "FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row is not None, "run_once did not insert a runs row"
    assert row["n_fetched"] == 1
    assert row["n_new"] == 1
    assert row["finished_at"] is not None, "finish_run did not set finished_at"

    summary = json.loads(row["summary_json"] or "{}")
    for key in ("stages", "per_source_fetched", "per_source_new",
                "score_stats", "top_blockers"):
        assert key in summary, f"summary_json missing key: {key}"
    assert summary["per_source_fetched"] == {"fake": 1}
    assert summary["per_source_new"] == {"fake": 1}


def test_api_runs_returns_recent_runs_in_descending_order(tmp_path: Path, monkeypatch) -> None:
    """The dashboard's /api/runs is contract-shaped: a JSON list of objects with
    id / timestamp / n_fetched / n_new / n_generated / n_applied / n_errors."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(job_id="r1"),
        llm_score_result=ScoreResult(score=10, reason="low"),
    )
    pipeline.run_once(_make_config(), _make_secrets())
    # Bump REGISTRY to a fresh scraper id so the second run dedups cleanly.
    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(job_id="r2"),
        llm_score_result=ScoreResult(score=10, reason="low"),
    )
    pipeline.run_once(_make_config(), _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.get_json()
    assert isinstance(runs, list)
    assert len(runs) >= 2, "expected the two runs we just kicked off"
    expected_keys = {"id", "timestamp", "n_fetched", "n_new",
                     "n_generated", "n_applied", "n_errors"}
    assert expected_keys.issubset(runs[0].keys())
    # Most recent first.
    assert runs[0]["id"] >= runs[1]["id"]


def test_run_detail_page_renders_for_existing_run(tmp_path: Path, monkeypatch) -> None:
    """/runs/<id> returns 200 and the template renders for a real run row."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(job_id="rd1"),
        llm_score_result=ScoreResult(score=10, reason="low"),
    )
    pipeline.run_once(_make_config(), _make_secrets())

    with connect(db) as conn:
        run_id = conn.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchone()["id"]

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200, resp.data


def test_run_detail_page_404s_for_unknown_run() -> None:
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/runs/999999")
    assert resp.status_code == 404


@pytest.mark.xfail(
    strict=True,
    reason="Dashboard re-run control is not implemented yet",
)
def test_dashboard_home_exposes_rerun_control(tmp_path: Path, monkeypatch) -> None:
    """The dashboard should let the user trigger a new pipeline run without
    leaving the browser."""
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot.db")
    client = _load_legacy_dashboard_module().app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Run pipeline" in html
    assert 'data-testid="run-pipeline"' in html
    assert "/api/runs/trigger" in html


# =============================================================================
# Journey 2 — match scores, filter reasons, body coverage, cannot_score
# =============================================================================

def test_heuristic_filter_persists_filtered_status_with_reason(
    tmp_path: Path, monkeypatch,
) -> None:
    """When passes_heuristic returns (False, reason), the row ends up with
    status='filtered' and score_reason=<reason>."""
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="filt_1")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline, "passes_heuristic",
        lambda _job, _profile: (False, "deal-breaker keyword: synthetic"),
    )
    # llm_score should never be called when heuristic rejects.
    monkeypatch.setattr(
        pipeline, "llm_score",
        lambda *_a, **_kw: pytest.fail("llm_score must not run when heuristic rejects"),
    )

    pipeline.run_once(_make_config(), _make_secrets())

    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score_reason FROM seen_jobs WHERE id='filt_1'"
        ).fetchone()
    assert row["status"] == JobStatus.FILTERED.value
    assert row["score_reason"] == "deal-breaker keyword: synthetic"


def test_cannot_score_no_body_persists_correct_status(tmp_path: Path, monkeypatch) -> None:
    """When llm_score raises CannotScore('no_body: ...'), the row's status
    becomes cannot_score:no_body and no numeric score is written."""
    import jobbot.pipeline as pipeline
    from jobbot.scoring import CannotScore
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="cs_1")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)

    def _refuse(*_a, **_kw):
        raise CannotScore("no_body: 12 words, need 200")

    monkeypatch.setattr(pipeline, "llm_score", _refuse)

    pipeline.run_once(_make_config(), _make_secrets())

    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score, score_reason FROM seen_jobs WHERE id='cs_1'"
        ).fetchone()
    assert row["status"] == JobStatus.CANNOT_SCORE_NO_BODY.value
    # The score column keeps the upsert_new default (0); STATUS is the
    # source of truth for cannot_score rows. /api/shortlist filters by
    # `score >= min_score` (min 70), so a 0 here is functionally invisible
    # to numeric consumers. The reason text captures why.
    assert row["status"] != JobStatus.SCORED.value
    assert row["score_reason"].startswith("no_body")


def test_api_pipeline_funnel_returns_expected_keys(tmp_path: Path, monkeypatch) -> None:
    """/api/pipeline-funnel must return run_id + per-stage attrition counts."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(job_id="fnl_1"),
        llm_score_result=ScoreResult(score=10, reason="low"),
    )
    pipeline.run_once(_make_config(), _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/pipeline-funnel")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("run_id", "fetched", "filtered", "below_threshold",
                "scored", "generated"):
        assert key in data, f"funnel response missing key: {key}"
    assert data["fetched"] == 1


def test_api_positions_returns_scores_statuses_and_filter_reasons(
    tmp_path: Path, monkeypatch,
) -> None:
    """/api/positions is the Stage-2 table contract: every row carries enough
    context to answer score, filter/cannot-score status, and why."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    _stub_pipeline(
        monkeypatch, pipeline,
        fake_scraper=FakeScraper(job_id="pos_1"),
        llm_score_result=ScoreResult(score=41, reason="missing B2B SaaS context"),
    )
    pipeline.run_once(_make_config(), _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    rows = resp.get_json()
    target = next(row for row in rows if row["id"] == "pos_1")
    expected_keys = {
        "id", "title", "company", "source", "status", "score",
        "score_reason", "url", "first_seen_at",
    }
    assert expected_keys.issubset(target.keys())
    assert target["status"] == JobStatus.BELOW_THRESHOLD.value
    assert target["score"] == 41
    assert target["score_reason"] == "missing B2B SaaS context"


def test_latest_run_portal_hits_exposes_description_coverage_by_source(
    tmp_path: Path, monkeypatch,
) -> None:
    """/api/latest-run-portal-hits exposes per-source body coverage for the
    latest run, using fetched_ids from summary_json rather than all DB rows."""
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    from jobbot.models import JobPosting
    from jobbot.state import connect, finish_run, start_run, update_enrichment, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    jobs = [
        JobPosting(
            id="body_full",
            source="fake",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/body_full",  # type: ignore
            apply_url="https://example.com/jobs/body_full",  # type: ignore
            description="snippet",
        ),
        JobPosting(
            id="body_missing",
            source="fake",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/body_missing",  # type: ignore
            apply_url="https://example.com/jobs/body_missing",  # type: ignore
            description="snippet",
        ),
    ]
    with connect(db) as conn:
        run_id = start_run(conn)
        upsert_new(conn, jobs)
        update_enrichment(
            conn,
            "body_full",
            description_full=" ".join(["responsibility"] * 240),
            description_scraped=True,
            description_word_count=240,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        finish_run(
            conn,
            run_id,
            n_fetched=2,
            n_new=2,
            summary={
                "per_source_fetched": {"fake": 2},
                "per_source_new": {"fake": 2},
                "fetched_ids": ["body_full", "body_missing"],
            },
        )

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/latest-run-portal-hits")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["run_id"] == run_id
    assert payload["per_portal"] == {"fake": 2}
    assert payload["total"] == 2
    assert payload["total_with_description"] == 1
    assert payload["percent_with_description"] == 50.0
    assert payload["per_portal_description"]["fake"] == {
        "total": 2,
        "with_description": 1,
        "percent_with_description": 50.0,
    }


@pytest.mark.xfail(
    strict=True,
    reason="Body coverage should require description_word_count >= 200, not just non-empty text",
)
def test_latest_run_portal_hits_body_coverage_uses_minimum_word_count(
    tmp_path: Path, monkeypatch,
) -> None:
    """User-facing body coverage means usable job-body coverage: postings with
    description_word_count >= 200 by source."""
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    from jobbot.models import JobPosting
    from jobbot.state import connect, finish_run, start_run, update_enrichment, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    jobs = [
        JobPosting(
            id="body_usable",
            source="fake",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/body_usable",  # type: ignore
            apply_url="https://example.com/jobs/body_usable",  # type: ignore
            description="snippet",
        ),
        JobPosting(
            id="body_too_short",
            source="fake",
            title="Senior PM",
            company="Acme",
            url="https://example.com/jobs/body_too_short",  # type: ignore
            apply_url="https://example.com/jobs/body_too_short",  # type: ignore
            description="snippet",
        ),
    ]
    with connect(db) as conn:
        run_id = start_run(conn)
        upsert_new(conn, jobs)
        update_enrichment(
            conn,
            "body_usable",
            description_full=" ".join(["responsibility"] * 240),
            description_scraped=True,
            description_word_count=240,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        update_enrichment(
            conn,
            "body_too_short",
            description_full=" ".join(["thin"] * 24),
            description_scraped=True,
            description_word_count=24,
            seniority="Senior",
            salary_text=None,
            apply_email=None,
        )
        finish_run(
            conn,
            run_id,
            n_fetched=2,
            n_new=2,
            summary={
                "per_source_fetched": {"fake": 2},
                "per_source_new": {"fake": 2},
                "fetched_ids": ["body_usable", "body_too_short"],
            },
        )

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/latest-run-portal-hits")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["run_id"] == run_id
    assert payload["total_with_description"] == 1
    assert payload["percent_with_description"] == 50.0
    assert payload["per_portal_description"]["fake"] == {
        "total": 2,
        "with_description": 1,
        "percent_with_description": 50.0,
    }


def test_digest_template_renders_cannot_score_section_when_provided() -> None:
    """The digest Jinja template must render a 'Cannot score' section
    separately from numeric matches when cannot_score entries are passed."""
    template_dir = (
        Path(__file__).resolve().parent.parent
        / "src" / "jobbot" / "notify" / "templates"
    )
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("digest.html.j2")
    html = tmpl.render(
        matches=[], errors=[], n=0,
        run_started=datetime.now(tz=timezone.utc),
        cannot_score=[{
            "job": {"title": "Senior PM", "company": "Acme",
                    "location": "Berlin", "url": "https://example.com/jobs/1",
                    "source": "linkedin"},
            "status": "cannot_score:no_body",
            "reason": "no_body: description has 24 words, need >= 200",
        }],
    )
    assert "Cannot score" in html
    assert "cannot_score:no_body" in html
    assert "no_body: description has 24 words" in html


# =============================================================================
# Journey 3 — tailored CV + cover letter, score before vs after
# =============================================================================

def _fake_generate_documents(job, profile, base_cv, secrets, config):
    """A generate_documents stub that writes minimal real artifacts to disk so
    the /shortlist/<id>/<file> route has something to serve."""
    out_root = Path(config.output_dir).resolve() / "test-run" / job.id
    out_root.mkdir(parents=True, exist_ok=True)
    cv_md = f"# CV (tailored for {job.company})\n\nReordered bullets.\n"
    cl_md = f"Dear {job.company} team,\n\nI'm a strong fit because...\n"
    (out_root / "cv.md").write_text(cv_md)
    (out_root / "cover_letter.md").write_text(cl_md)
    (out_root / "cv.html").write_text(f"<html><body><h1>{job.company}</h1></body></html>")
    (out_root / "cover_letter.html").write_text("<html><body>Dear team</body></html>")
    return GeneratedDocs(
        cv_md=cv_md, cv_html="<html></html>",
        cover_letter_md=cl_md, cover_letter_html="<html></html>",
        output_dir=str(out_root),
        cv_pdf=None,
        cover_letter_pdf=None,
    )


def test_generate_documents_writes_complete_tailored_bundle(
    tmp_path: Path, monkeypatch,
) -> None:
    """The real generator must create every expected per-job artifact when the
    PDF renderer succeeds: md/html/pdf for both CV and cover letter."""
    import sys
    from datetime import date
    from types import SimpleNamespace

    import jobbot.generators.pipeline as generator

    class FakeHTML:
        def __init__(self, *, string: str) -> None:
            self.string = string

        def write_pdf(self, target: str) -> None:
            Path(target).write_bytes(b"%PDF-1.4\n% fake test pdf\n")

    rendered_docs = iter([
        "# Tailored CV\n\n- Product leadership for Acme.\n",
        "# Cover Letter\n\nDear Acme team,\n",
    ])
    monkeypatch.setattr(generator, "_call_sonnet", lambda *_args, **_kwargs: next(rendered_docs))
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))

    config = _make_config()
    config.output_dir = str(tmp_path / "output")
    job = JobPosting(
        id="bundle_1",
        source="fake",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/bundle_1",  # type: ignore
        apply_url="https://example.com/jobs/bundle_1",  # type: ignore
        description=" ".join(["responsibility"] * 240),
    )

    docs = generator.generate_documents(
        job, _make_profile(), "Base CV", _make_secrets(), config,
    )

    out = Path(docs.output_dir)
    expected_files = {
        "cv.md", "cv.html", "cv.pdf",
        "cover_letter.md", "cover_letter.html", "cover_letter.pdf",
    }
    assert {path.name for path in out.iterdir()} >= expected_files
    assert out.parent.name == date.today().isoformat()
    assert docs.cv_pdf == str(out / "cv.pdf")
    assert docs.cover_letter_pdf == str(out / "cover_letter.pdf")
    assert (out / "cv.md").read_text().startswith("# Tailored CV")
    assert (out / "cover_letter.md").read_text().startswith("# Cover Letter")
    assert "<html" in (out / "cv.html").read_text()
    assert (out / "cv.pdf").read_bytes().startswith(b"%PDF")
    assert (out / "cover_letter.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.xfail(
    strict=True,
    reason="PDF render failures are still swallowed instead of surfaced as incomplete artifacts",
)
def test_generate_documents_does_not_silently_drop_pdf_artifacts(
    tmp_path: Path, monkeypatch,
) -> None:
    """If PDF rendering fails, the generator should make that visible to the
    test suite instead of returning a partially generated bundle silently."""
    import sys
    from types import SimpleNamespace

    import jobbot.generators.pipeline as generator

    class BrokenHTML:
        def __init__(self, *, string: str) -> None:
            self.string = string

        def write_pdf(self, target: str) -> None:
            raise RuntimeError(f"cannot render {target}")

    rendered_docs = iter([
        "# Tailored CV\n\n- Product leadership for Acme.\n",
        "# Cover Letter\n\nDear Acme team,\n",
    ])
    monkeypatch.setattr(generator, "_call_sonnet", lambda *_args, **_kwargs: next(rendered_docs))
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=BrokenHTML))

    config = _make_config()
    config.output_dir = str(tmp_path / "output")
    config.cv_pdf_path = ""
    job = JobPosting(
        id="bundle_pdf_failure",
        source="fake",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/bundle_pdf_failure",  # type: ignore
        apply_url="https://example.com/jobs/bundle_pdf_failure",  # type: ignore
        description=" ".join(["responsibility"] * 240),
    )

    docs = generator.generate_documents(
        job, _make_profile(), "Base CV", _make_secrets(), config,
    )

    assert docs.cv_pdf is not None
    assert docs.cover_letter_pdf is not None
    assert Path(docs.cv_pdf).exists()
    assert Path(docs.cover_letter_pdf).exists()


def test_pipeline_writes_both_score_and_score_tailored_when_generation_runs(
    tmp_path: Path, monkeypatch,
) -> None:
    """End-to-end: scored ≥ generate-threshold → generate_documents runs →
    llm_score_tailored runs → DB row has BOTH score and score_tailored."""
    import jobbot.pipeline as pipeline
    from jobbot.state import connect

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="gen_1")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline, "llm_score",
        lambda *_a, **_kw: ScoreResult(score=85, reason="base good fit"),
    )
    monkeypatch.setattr(
        pipeline, "llm_score_tailored",
        lambda *_a, **_kw: ScoreResult(score=93, reason="tailored lift"),
    )

    # Redirect generation output into the tmp dir so we don't pollute output/.
    config = _make_config(generate_above=80)
    config.output_dir = str(tmp_path / "out")
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)

    pipeline.run_once(config, _make_secrets())

    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score, score_tailored, score_reason, "
            "       score_tailored_reason, output_dir "
            "FROM seen_jobs WHERE id='gen_1'"
        ).fetchone()
    assert row["status"] in (JobStatus.GENERATED.value, JobStatus.SCORED.value), row["status"]
    assert row["score"] == 85, "base score must be persisted"
    assert row["score_tailored"] == 93, "tailored score must be persisted"
    assert row["score_tailored_reason"].startswith("tailored")
    assert row["output_dir"], "output_dir must be set after generation"


def test_api_shortlist_exposes_tailored_score_fields(tmp_path: Path, monkeypatch) -> None:
    """/api/shortlist returns score, score_tailored, score_delta, tailored_reason."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="sl_1")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline, "llm_score",
        lambda *_a, **_kw: ScoreResult(score=85, reason="base"),
    )
    monkeypatch.setattr(
        pipeline, "llm_score_tailored",
        lambda *_a, **_kw: ScoreResult(score=93, reason="tailored"),
    )
    config = _make_config(generate_above=80)
    config.output_dir = str(tmp_path / "out")
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)

    pipeline.run_once(config, _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/api/shortlist?min_score=70")
    assert resp.status_code == 200
    payload = resp.get_json()
    jobs = payload["jobs"]
    target = next(j for j in jobs if j["id"] == "sl_1")
    assert target["score"] == 85
    assert target["score_tailored"] == 93
    assert target["score_delta"] == 8
    assert target["tailored_reason"].startswith("tailored")
    assert target["cv_html_url"] == "/shortlist/sl_1/cv.html"
    assert target["cover_letter_html_url"] == "/shortlist/sl_1/cover_letter.html"


def test_dashboard_does_not_present_base_score_as_tailored_rescore(
    tmp_path: Path, monkeypatch,
) -> None:
    """If Stage-3 generation succeeds but the tailored rescore has not run,
    the dashboard must say so. Showing only the base-CV score makes it look
    like the tailored CV+CL was rescored when it was not."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="rescore_pending")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline,
        "llm_score",
        lambda *_a, **_kw: ScoreResult(score=85, reason="base CV says strong fit"),
    )

    def _tailored_rescore_not_live(*_args, **_kwargs):
        raise RuntimeError("tailored rescorer unavailable")

    monkeypatch.setattr(pipeline, "llm_score_tailored", _tailored_rescore_not_live)
    config = _make_config(generate_above=80)
    config.output_dir = str(tmp_path / "out")
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)

    pipeline.run_once(config, _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    payload = client.get("/api/shortlist?min_score=70").get_json()
    target = next(j for j in payload["jobs"] if j["id"] == "rescore_pending")
    assert target["score"] == 85
    assert target["score_tailored"] is None
    assert target["score_delta"] is None
    assert target["tailored_reason"] == ""

    html = client.get("/").get_data(as_text=True)
    assert "score_tailored" in html
    assert "score_delta" in html
    assert "base score (primary CV)" in html
    assert "tailored rescore pending" in html.lower()
    assert "Reason (tailored CV + CL)" in html


def test_shortlist_doc_route_serves_existing_html(tmp_path: Path, monkeypatch) -> None:
    """GET /shortlist/<id>/cv.html returns 200 with the HTML body when the
    job has an output_dir and the file exists on disk."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="doc_1")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline, "llm_score",
        lambda *_a, **_kw: ScoreResult(score=85, reason="base"),
    )
    monkeypatch.setattr(
        pipeline, "llm_score_tailored",
        lambda *_a, **_kw: ScoreResult(score=93, reason="tailored"),
    )
    config = _make_config(generate_above=80)
    config.output_dir = str(tmp_path / "out")
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)

    pipeline.run_once(config, _make_secrets())

    client = _load_legacy_dashboard_module().app.test_client()
    resp = client.get("/shortlist/doc_1/cv.html")
    assert resp.status_code == 200
    assert b"<h1>ACME</h1>" in resp.data


def test_shortlist_doc_route_rejects_filenames_outside_allowlist(
    tmp_path: Path, monkeypatch,
) -> None:
    """Filenames not in the {cv.html, cover_letter.html, cv.md, cover_letter.md}
    allowlist must 404, even if the file would exist on disk."""
    import jobbot.pipeline as pipeline
    from jobbot.dashboard.server import _load_legacy_dashboard_module

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": FakeScraper(job_id="doc_2")})
    monkeypatch.setattr(pipeline, "load_profile", lambda: _make_profile())
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        pipeline, "llm_score",
        lambda *_a, **_kw: ScoreResult(score=85, reason="base"),
    )
    monkeypatch.setattr(
        pipeline, "llm_score_tailored",
        lambda *_a, **_kw: ScoreResult(score=93, reason="tailored"),
    )
    config = _make_config(generate_above=80)
    config.output_dir = str(tmp_path / "out")
    monkeypatch.setattr(pipeline, "generate_documents", _fake_generate_documents)

    pipeline.run_once(config, _make_secrets())

    # Plant a "secret" file alongside the legit artifacts to prove the
    # allowlist (not the filesystem) is what stops the request.
    secret = tmp_path / "out" / "test-run" / "doc_2" / "secrets.txt"
    secret.write_text("totally not a CV")

    client = _load_legacy_dashboard_module().app.test_client()
    assert client.get("/shortlist/doc_2/secrets.txt").status_code == 404
    assert client.get("/shortlist/doc_2/.env").status_code == 404


def test_shortlist_doc_route_404s_for_unknown_job() -> None:
    from jobbot.dashboard.server import _load_legacy_dashboard_module
    client = _load_legacy_dashboard_module().app.test_client()
    assert client.get("/shortlist/no_such_job/cv.html").status_code == 404
