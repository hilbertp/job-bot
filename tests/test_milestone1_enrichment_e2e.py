"""Milestone 1 enrichment gate tests (test-first).

These are intentionally strict regression gates for PRD Milestone 1:
- StepStone/Xing/WWR must implement non-stub fetch_detail
- Pipeline must enrich newly scraped jobs before LLM scoring

Run this file before claiming Milestone 1 enrichment completion.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from jobbot.config import Config, DigestConfig, Secrets, SourceConfig
from jobbot.models import JobPosting, ScoreResult
from jobbot.profile import Profile


def test_required_scrapers_have_non_stub_fetch_detail():
    """Milestone 1 requires fetch_detail for StepStone, Xing, and WWR."""
    from jobbot.scrapers.stepstone import StepstoneScraper
    from jobbot.scrapers.weworkremotely import WeWorkRemotelyScraper
    from jobbot.scrapers.xing import XingScraper

    required = [
        ("stepstone", StepstoneScraper),
        ("xing", XingScraper),
        ("weworkremotely", WeWorkRemotelyScraper),
    ]

    for source_name, scraper_cls in required:
        src = inspect.getsource(scraper_cls.fetch_detail)
        assert "NotImplementedError" not in src, (
            f"{source_name}.fetch_detail is still a stub; Milestone 1 not complete"
        )


class _FakeScraper:
    source = "fake"

    def __init__(self) -> None:
        self.fetch_detail_calls = 0

    def fetch(self, _query):
        return [
            JobPosting(
                id="fake_1",
                source="fake",
                title="Senior Product Manager",
                company="ACME",
                url="https://example.com/jobs/1",
                apply_url="https://example.com/jobs/1",
                description="short listing snippet",
            )
        ]

    def fetch_detail(self, job: JobPosting):
        self.fetch_detail_calls += 1
        long_body = " ".join(["responsibility"] * 140)  # 140 words
        return job.model_copy(update={"description": long_body})


def test_pipeline_enriches_new_jobs_before_scoring(tmp_path: Path, monkeypatch):
    """PRD FR-ENR-02/03: scoring should receive enriched full body (>=100 words)."""
    import jobbot.pipeline as pipeline

    fake_scraper = _FakeScraper()
    scored_descriptions: list[str] = []

    # Keep run_once deterministic and offline.
    monkeypatch.setattr("jobbot.state.DB_PATH", tmp_path / "jobbot_test.db")
    monkeypatch.setattr(pipeline, "REGISTRY", {"fake": fake_scraper})
    monkeypatch.setattr(
        pipeline,
        "load_profile",
        lambda: Profile(
            personal={"full_name": "Test", "email": "test@example.com"},
            preferences={"remote": True},
            deal_breakers={"keywords": [], "industries": [], "on_site_only": False},
            must_have_skills=[],
        ),
    )
    monkeypatch.setattr(pipeline, "load_base_cv", lambda: "")
    monkeypatch.setattr(pipeline, "passes_heuristic", lambda _job, _profile: (True, ""))
    monkeypatch.setattr(pipeline, "send_digest", lambda *_args, **_kwargs: None)

    def _fake_llm_score(job, _profile, _secrets):
        scored_descriptions.append(job.description)
        return ScoreResult(score=10, reason="below threshold")

    monkeypatch.setattr(pipeline, "llm_score", _fake_llm_score)

    config = Config(
        score_threshold=70,
        max_jobs_per_run=10,
        digest=DigestConfig(generate_docs_above_score=90, max_per_email=100),
        sources={
            "fake": SourceConfig(enabled=True, auto_submit=False, queries=[{"q": "pm"}])
        },
    )
    secrets = Secrets(
        anthropic_api_key="x",
        gmail_address="x@example.com",
        gmail_app_password="x",
        notify_to="x@example.com",
    )

    pipeline.run_once(config, secrets)

    assert fake_scraper.fetch_detail_calls == 1, (
        "Pipeline did not call fetch_detail on newly scraped jobs"
    )
    assert scored_descriptions, "Expected at least one scoring call"
    assert len(scored_descriptions[0].split()) >= 100, (
        "Scoring ran without enriched full body (expected >=100 words)"
    )
