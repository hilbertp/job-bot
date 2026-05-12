"""Live acceptance test for PRD Milestone 1 enrichment quality.

This test intentionally uses real scrapers and real network calls.
It is opt-in because it is slow/flaky by nature and depends on source uptime.

Enable with:
    JOBBOT_RUN_LIVE_ENRICHMENT_ACCEPTANCE=1

What it validates:
1) Trigger a fresh pipeline run (real scrape + enrichment).
2) Read rows inserted in this run from SQLite.
3) Per enabled source, assert at least 80% have enriched descriptions
   (description_scraped=1 and description_word_count >= 100).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from jobbot.config import Config, DigestConfig, Secrets, SourceConfig
from jobbot.pipeline import run_once
from jobbot.state import connect

LIVE_ENV_FLAG = "JOBBOT_RUN_LIVE_ENRICHMENT_ACCEPTANCE"
MIN_SUCCESS_RATE = 0.80


@pytest.mark.e2e
@pytest.mark.live
@pytest.mark.integration
def test_live_enrichment_acceptance_80_percent(tmp_path: Path, monkeypatch):
    if os.getenv(LIVE_ENV_FLAG) != "1":
        pytest.skip(f"set {LIVE_ENV_FLAG}=1 to run live acceptance test")

    # Isolate this live test into a temporary DB.
    db_path = tmp_path / "jobbot_live_acceptance.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db_path)

    # Avoid external side-effects and API spend; this acceptance test is about scrape+enrichment.
    monkeypatch.setattr("jobbot.pipeline.send_digest", lambda *_args, **_kwargs: None)

    config = Config(
        score_threshold=100,
        max_jobs_per_run=0,
        digest=DigestConfig(generate_docs_above_score=101, max_per_email=100),
        sources={
            "stepstone": SourceConfig(
                enabled=True,
                auto_submit=False,
                queries=[{"q": "product manager", "l": "Deutschland"}],
            ),
            "xing": SourceConfig(
                enabled=True,
                auto_submit=False,
                queries=[{"q": "product manager"}],
            ),
            "weworkremotely": SourceConfig(
                enabled=True,
                auto_submit=False,
                queries=[{"category": "remote-programming-jobs"}],
            ),
        },
    )

    secrets = Secrets(
        anthropic_api_key="test",
        gmail_address="test@example.com",
        gmail_app_password="test",
        notify_to="test@example.com",
    )

    started = datetime.now(tz=timezone.utc)
    run_once(config, secrets)

    with connect(db_path) as conn:
        for source_name, src_cfg in config.sources.items():
            if not src_cfg.enabled:
                continue

            total = conn.execute(
                "SELECT COUNT(*) FROM seen_jobs WHERE source = ? AND first_seen_at >= ?",
                (source_name, started.isoformat()),
            ).fetchone()[0]

            assert total > 0, (
                f"{source_name}: no jobs were scraped in this run; cannot evaluate acceptance"
            )

            enriched = conn.execute(
                "SELECT COUNT(*) FROM seen_jobs "
                "WHERE source = ? AND first_seen_at >= ? "
                "AND description_scraped = 1 AND description_word_count >= 100",
                (source_name, started.isoformat()),
            ).fetchone()[0]

            success_rate = enriched / total
            assert success_rate >= MIN_SUCCESS_RATE, (
                f"{source_name}: enrichment success {enriched}/{total} "
                f"({success_rate:.1%}) < required {MIN_SUCCESS_RATE:.0%}"
            )
