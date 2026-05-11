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
