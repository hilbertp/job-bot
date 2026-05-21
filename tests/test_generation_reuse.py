"""Idempotency: don't re-enrich / re-score / re-generate already-done rows.

User feedback 2026-05-21: "can we skip things that are already done?
seems like we are regenerating already done custom profiles. this leads
to long run times and more expensive runs!"

Two fixes:
  1. Enrichment input is new rows + rows missing a body, NOT every
     re-scraped row, so already-enriched rows don't get re-fetched (and
     don't flow back into scoring/generation).
  2. `load_existing_docs` lets the generation loop reuse a CV + cover
     letter already on disk instead of re-calling the LLM.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.generators import load_existing_docs


# ---------------------------------------------------------------------------
# load_existing_docs
# ---------------------------------------------------------------------------

def test_load_existing_docs_none_for_missing_dir():
    assert load_existing_docs(None) is None
    assert load_existing_docs("/no/such/dir") is None


def test_load_existing_docs_none_when_md_missing(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    (d / "cv.md").write_text("# CV")  # cover_letter.md missing
    assert load_existing_docs(str(d)) is None


def test_load_existing_docs_loads_when_present(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    (d / "cv.md").write_text("# CV body")
    (d / "cover_letter.md").write_text("Dear team")
    (d / "cv.html").write_text("<h1>CV</h1>")
    (d / "cover_letter.html").write_text("<p>Dear team</p>")
    (d / "cv.pdf").write_bytes(b"%PDF cv")
    (d / "cover_letter.pdf").write_bytes(b"%PDF cl")
    docs = load_existing_docs(str(d))
    assert docs is not None
    assert docs.cv_md == "# CV body"
    assert docs.cover_letter_md == "Dear team"
    assert docs.cv_pdf == str(d / "cv.pdf")
    assert docs.cover_letter_pdf == str(d / "cover_letter.pdf")


def test_load_existing_docs_pdf_none_when_absent(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    (d / "cv.md").write_text("# CV")
    (d / "cover_letter.md").write_text("Dear team")
    docs = load_existing_docs(str(d))
    assert docs is not None
    assert docs.cv_pdf is None
    assert docs.cover_letter_pdf is None


# ---------------------------------------------------------------------------
# pipeline: generation reuses existing docs instead of regenerating
# ---------------------------------------------------------------------------

import datetime as dt

from jobbot.config import (
    Config, DigestConfig, EnrichmentConfig, Secrets, SourceConfig,
)
from jobbot.models import GeneratedDocs, JobPosting, JobStatus, ScoreResult
from jobbot.profile import Profile
from jobbot.state import connect


class _Scraper:
    source = "fake"

    def __init__(self, job):
        self._job = job

    def fetch(self, _q):
        return [self._job]

    def fetch_detail(self, job):
        return job.model_copy(update={"description": "Full body. " * 60})


def _job():
    return JobPosting(
        id="reuse_1", source="fake", title="Product Manager", company="Acme",
        url="https://greenhouse.io/acme/jobs/1",
        apply_url="https://greenhouse.io/acme/jobs/1",
        posted_at=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=1),
        description="snippet",
    )


def _config(tmp_path, regenerate=False):
    return Config(
        sources={"fake": SourceConfig(enabled=True, queries=[{"q": "pm"}])},
        enrichment=EnrichmentConfig(),
        digest=DigestConfig(generate_top_n=5, generate_docs_above_score=70),
        score_threshold=70,
        output_dir=str(tmp_path / "out"),
        regenerate_existing_docs=regenerate,
    )


def _secrets():
    return Secrets(anthropic_api_key="x", gmail_address="a@b.com",
                   gmail_app_password="x", notify_to="a@b.com")


def _profile():
    return Profile(personal={"full_name": "T", "email": "t@example.com"}, preferences={})


def _install_stubs(monkeypatch, pipeline, job, gen_counter):
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": _Scraper(job)})
    monkeypatch.setattr(pipeline, "load_profile", _profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "Base CV")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline, "llm_score",
                        lambda *_a, **_kw: ScoreResult(score=88, reason="fit"))
    monkeypatch.setattr(pipeline, "llm_score_tailored",
                        lambda *_a, **_kw: ScoreResult(score=93, reason="lift"))
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(pipeline, "housekeep_shortlist",
                        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []))

    def _gen(job, profile, base_cv, secrets, config, **_kw):
        gen_counter.append(job.id)
        out = Path(config.output_dir) / "gen" / job.id
        out.mkdir(parents=True, exist_ok=True)
        (out / "cv.md").write_text("# CV")
        (out / "cover_letter.md").write_text("Dear Acme")
        (out / "cv.html").write_text("<h1>CV</h1>")
        (out / "cover_letter.html").write_text("<p>Dear Acme</p>")
        return GeneratedDocs(
            cv_md="# CV", cv_html="<h1>CV</h1>",
            cover_letter_md="Dear Acme", cover_letter_html="<p>Dear Acme</p>",
            output_dir=str(out), cv_pdf=None, cover_letter_pdf=None,
        )
    monkeypatch.setattr(pipeline, "generate_application_package", _gen)


def test_second_run_reuses_docs_no_regeneration(tmp_path, monkeypatch):
    import jobbot.pipeline as pipeline
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job = _job()
    gen_calls: list[str] = []
    _install_stubs(monkeypatch, pipeline, job, gen_calls)

    # Run 1: generates once.
    pipeline.run_once(_config(tmp_path), _secrets())
    assert gen_calls == ["reuse_1"], "first run should generate"

    # Run 2: same posting re-scraped. Must NOT regenerate.
    pipeline.run_once(_config(tmp_path), _secrets())
    assert gen_calls == ["reuse_1"], (
        f"second run regenerated already-done docs: {gen_calls}"
    )
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, output_dir FROM seen_jobs WHERE id='reuse_1'").fetchone()
    assert row["status"] == JobStatus.GENERATED.value
    assert row["output_dir"]


def _seed_scraped_with_docs(db, tmp_path):
    """Seed a SCRAPED row that already has docs on disk + an output_dir,
    so the SCRAPED-retry path scores it and it reaches the generation
    loop with existing docs, the scenario where reuse vs. regenerate
    actually applies."""
    from jobbot.state import connect, upsert_new
    out = Path(tmp_path) / "prior" / "reuse_1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cv.md").write_text("# CV prior")
    (out / "cover_letter.md").write_text("Dear Acme prior")
    (out / "cv.html").write_text("<h1>CV</h1>")
    (out / "cover_letter.html").write_text("<p>Dear</p>")
    job = _job()
    with connect(db) as conn:
        upsert_new(conn, [job])
        conn.execute(
            "UPDATE seen_jobs SET status=?, description_full=?, "
            "description_scraped=1, description_word_count=200, output_dir=? "
            "WHERE id=?",
            (JobStatus.SCRAPED.value, "Full body. " * 60, str(out), job.id),
        )
    return job, str(out)


def test_scraped_retry_reuses_existing_docs_by_default(tmp_path, monkeypatch):
    import jobbot.pipeline as pipeline
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job, _ = _seed_scraped_with_docs(db, tmp_path)
    gen_calls: list[str] = []
    # Scraper returns nothing new; the SCRAPED row drives generation.
    class _Empty:
        source = "fake"
        def fetch(self, _q): return []
        def fetch_detail(self, j): return j
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": _Empty()})
    monkeypatch.setattr(pipeline, "load_profile", _profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "Base CV")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline, "llm_score",
                        lambda *_a, **_kw: ScoreResult(score=88, reason="fit"))
    monkeypatch.setattr(pipeline, "llm_score_tailored",
                        lambda *_a, **_kw: ScoreResult(score=93, reason="lift"))
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(pipeline, "housekeep_shortlist",
                        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []))

    def _gen(job, *a, **k):
        gen_calls.append(job.id)
        raise AssertionError("should not regenerate when docs exist + reuse on")
    monkeypatch.setattr(pipeline, "generate_application_package", _gen)

    pipeline.run_once(_config(tmp_path), _secrets())
    assert gen_calls == [], "reuse-by-default should skip generate"


def test_scraped_retry_regenerates_when_flag_set(tmp_path, monkeypatch):
    import jobbot.pipeline as pipeline
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job, _ = _seed_scraped_with_docs(db, tmp_path)
    gen_calls: list[str] = []
    class _Empty:
        source = "fake"
        def fetch(self, _q): return []
        def fetch_detail(self, j): return j
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": _Empty()})
    monkeypatch.setattr(pipeline, "load_profile", _profile)
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "Base CV")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda *_a: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline, "llm_score",
                        lambda *_a, **_kw: ScoreResult(score=88, reason="fit"))
    monkeypatch.setattr(pipeline, "llm_score_tailored",
                        lambda *_a, **_kw: ScoreResult(score=93, reason="lift"))
    from jobbot.housekeep import HousekeepReport
    monkeypatch.setattr(pipeline, "housekeep_shortlist",
                        lambda *_a, **_kw: HousekeepReport(0, 0, 0, 0, 0, [], []))

    def _gen(job, profile, base_cv, secrets, config, **_kw):
        gen_calls.append(job.id)
        out = Path(config.output_dir) / "fresh" / job.id
        out.mkdir(parents=True, exist_ok=True)
        (out / "cv.md").write_text("# CV fresh")
        (out / "cover_letter.md").write_text("Dear Acme fresh")
        return GeneratedDocs(
            cv_md="# CV fresh", cv_html="<h1>x</h1>",
            cover_letter_md="Dear Acme fresh", cover_letter_html="<p>x</p>",
            output_dir=str(out), cv_pdf=None, cover_letter_pdf=None,
        )
    monkeypatch.setattr(pipeline, "generate_application_package", _gen)

    pipeline.run_once(_config(tmp_path, regenerate=True), _secrets())
    assert gen_calls == ["reuse_1"], (
        f"regenerate_existing_docs=True should rebuild: {gen_calls}"
    )
