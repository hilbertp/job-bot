"""Backfill flow for `jobbot enrich --backfill`.

Pins six contracts that the pre-enrichment-cleanup pass depends on:

  1. Rows with description_scraped IS NULL are picked up and enriched.
  2. Rows that already meet the 200-word floor are left untouched.
  3. freelance_de rows are terminal-marked cannot_score:source_unsupported
     and never call fetch_detail.
  4. --dry-run writes nothing (no enrichment, no status change).
  5. --source <name> only touches rows from that scraper.
  6. A fetch_detail exception leaves the row unchanged — the URL/error
     is logged but no `description_scraped=False` is persisted, so a
     later run can retry. (Distinct from the pipeline-time runner, which
     hard-locks the row at no_body on first miss.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from jobbot.enrichment.backfill import _PerSourceRateLimiter, run_backfill
from jobbot.models import JobPosting, JobStatus
from jobbot.state import (
    connect,
    jobs_needing_backfill,
    update_enrichment,
    upsert_new,
)


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------

class _FakeScraper:
    """Returns a long body, optionally raising or returning None."""

    def __init__(
        self, source: str, *, body_words: int = 240,
        raise_exc: Exception | None = None, return_none: bool = False,
    ) -> None:
        self.source = source
        self._body_words = body_words
        self._raise_exc = raise_exc
        self._return_none = return_none
        self.calls: list[str] = []  # job IDs we were asked to fetch

    def fetch_detail(self, job: JobPosting):
        self.calls.append(job.id)
        if self._raise_exc is not None:
            raise self._raise_exc
        if self._return_none:
            return None
        long_body = " ".join(["responsibility"] * self._body_words)
        return job.model_copy(update={"description": long_body})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Rate-limiter would otherwise sleep up to 1s per source per call."""
    monkeypatch.setattr("jobbot.enrichment.backfill.time.sleep", lambda _s: None)


def _seed(db: Path, *, job_id: str, source: str,
          word_count: int | None, scraped: bool | None) -> JobPosting:
    """Insert one row and optionally backdate its enrichment columns."""
    job = JobPosting(
        id=job_id,
        source=source,
        title="Senior PM",
        company="Acme",
        url=f"https://example.com/jobs/{job_id}",  # type: ignore[arg-type]
        apply_url=f"https://example.com/jobs/{job_id}",  # type: ignore[arg-type]
        description="short listing snippet",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
        if scraped is not None or word_count is not None:
            update_enrichment(
                conn, job_id,
                description_full="seed body",
                description_scraped=bool(scraped),
                description_word_count=word_count or 0,
                seniority=None, salary_text=None, apply_email=None,
            )
    return job


def _row(db: Path, job_id: str) -> dict:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, score_reason, description_scraped, "
            "description_word_count, description_full "
            "FROM seen_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_null_body_row_is_enriched(tmp_path: Path, monkeypatch) -> None:
    """A row with description_scraped IS NULL — the exact shape of the 101
    pre-enrichment rows in production — gets picked up and persisted."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="needs_body", source="linkedin",
          word_count=None, scraped=None)

    fake = _FakeScraper("linkedin", body_words=240)
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        assert [j.id for j in candidates] == ["needs_body"]

        report = run_backfill(candidates, conn, registry={"linkedin": fake})

    assert report.n_enriched == 1
    assert report.n_failed == 0
    assert fake.calls == ["needs_body"]

    row = _row(db, "needs_body")
    assert row["description_scraped"] == 1
    assert row["description_word_count"] >= 200
    assert "responsibility" in row["description_full"]


def test_already_meeting_threshold_is_skipped(tmp_path: Path, monkeypatch) -> None:
    """A row whose description_word_count is already >= MIN_BODY_WORDS is
    NOT a candidate. We never call its scraper, never overwrite its body."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="already_ok", source="linkedin",
          word_count=300, scraped=True)

    fake = _FakeScraper("linkedin")
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        assert candidates == []
        # Sanity: running on an empty list is a no-op.
        report = run_backfill(candidates, conn, registry={"linkedin": fake})

    assert report.n_attempted == 0
    assert fake.calls == []
    row = _row(db, "already_ok")
    assert row["description_word_count"] == 300
    assert row["description_full"] == "seed body"  # unchanged


def test_freelance_de_marked_source_unsupported(tmp_path: Path, monkeypatch) -> None:
    """freelance_de has no fetch_detail. A backfill on it is hopeless, so
    the runner terminal-marks the row and never invokes the scraper."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="fdee", source="freelance_de",
          word_count=None, scraped=None)

    # The scraper has a (stub) fetch_detail attribute, but UNSUPPORTED_SOURCES
    # short-circuits before we ever call it.
    fake = _FakeScraper("freelance_de")
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        report = run_backfill(candidates, conn, registry={"freelance_de": fake})

    assert report.n_unsupported == 1
    assert report.n_enriched == 0
    assert fake.calls == []  # never invoked
    row = _row(db, "fdee")
    assert row["status"] == JobStatus.CANNOT_SCORE_SOURCE_UNSUPPORTED.value

    # Subsequent backfills must NOT re-attempt this row.
    with connect(db) as conn:
        again = jobs_needing_backfill(conn, min_words=200, limit=10)
    assert [j.id for j in again] == []


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    """--dry-run still walks the candidate list and exercises the rate
    limiter, but persists no enrichment and changes no status."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="lnk", source="linkedin", word_count=None, scraped=None)
    _seed(db, job_id="fde", source="freelance_de", word_count=None, scraped=None)

    fake_lnk = _FakeScraper("linkedin")
    fake_fde = _FakeScraper("freelance_de")
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        report = run_backfill(
            candidates, conn,
            registry={"linkedin": fake_lnk, "freelance_de": fake_fde},
            dry_run=True,
        )

    # Real scrapers must not be called in dry-run.
    assert fake_lnk.calls == []
    assert fake_fde.calls == []
    assert report.n_attempted == 2
    # n_enriched counts the *would-enrich* rows in dry-run.
    assert report.n_enriched == 1
    assert report.n_unsupported == 1

    # No DB writes: linkedin row stays NULL, freelance_de row is NOT marked.
    lnk = _row(db, "lnk")
    fde = _row(db, "fde")
    assert lnk["description_scraped"] is None
    assert lnk["description_word_count"] is None
    assert fde["status"] == JobStatus.SCRAPED.value
    assert fde["description_scraped"] is None


def test_source_filter_only_touches_matching_rows(
    tmp_path: Path, monkeypatch,
) -> None:
    """--source linkedin must only call linkedin's fetch_detail. Stepstone
    rows are counted in n_skipped_filter and the stepstone scraper is
    never invoked."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="lnk1", source="linkedin", word_count=None, scraped=None)
    _seed(db, job_id="step1", source="stepstone", word_count=None, scraped=None)

    fake_lnk = _FakeScraper("linkedin")
    fake_step = _FakeScraper("stepstone")
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        report = run_backfill(
            candidates, conn,
            registry={"linkedin": fake_lnk, "stepstone": fake_step},
            source="linkedin",
        )

    assert fake_lnk.calls == ["lnk1"]
    assert fake_step.calls == []
    assert report.n_attempted == 1
    assert report.n_enriched == 1
    assert report.n_skipped_filter == 1

    # Stepstone row remains unenriched and a candidate for the next run.
    step_row = _row(db, "step1")
    assert step_row["description_scraped"] is None


def test_fetch_detail_exception_leaves_row_unchanged(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    """An exception from the scraper must NOT mark the row failed in the
    DB — that would lock it at cannot_score:no_body via the existing
    runner semantics. Instead, the row stays NULL so the next backfill
    can retry, and the error is logged to stderr with the URL."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, job_id="boom", source="linkedin",
          word_count=None, scraped=None)

    fake = _FakeScraper("linkedin", raise_exc=RuntimeError("captcha wall"))
    with connect(db) as conn:
        candidates = jobs_needing_backfill(conn, min_words=200, limit=10)
        report = run_backfill(candidates, conn, registry={"linkedin": fake})

    assert report.n_failed == 1
    assert report.n_enriched == 0
    assert fake.calls == ["boom"]

    row = _row(db, "boom")
    assert row["status"] == JobStatus.SCRAPED.value  # unchanged
    assert row["description_scraped"] is None       # untouched
    assert row["description_word_count"] is None    # untouched

    err = capsys.readouterr().err
    assert "boom" in err
    assert "example.com/jobs/boom" in err
    assert "captcha wall" in err

    # The row is still a backfill candidate next time.
    with connect(db) as conn:
        again = jobs_needing_backfill(conn, min_words=200, limit=10)
    assert [j.id for j in again] == ["boom"]


# ---------------------------------------------------------------------------
# Extra contract: the rate limiter actually paces calls.
# ---------------------------------------------------------------------------

def test_rate_limiter_paces_calls_per_source() -> None:
    """1 req/s/source: the second call to the same source within <1s waits.
    Cross-source calls are independent."""
    fake_clock = [100.0]
    slept: list[float] = []

    def _monotonic() -> float:
        return fake_clock[0]

    def _sleep(seconds: float) -> None:
        slept.append(seconds)
        fake_clock[0] += seconds

    limiter = _PerSourceRateLimiter(sleep=_sleep, monotonic=_monotonic)

    limiter.wait("linkedin")                          # no prior call → no sleep
    fake_clock[0] += 0.2                              # 0.2s elapse externally
    limiter.wait("linkedin")                          # < 1s gap → must sleep ~0.8s
    fake_clock[0] += 5.0
    limiter.wait("linkedin")                          # >= 1s gap → no extra sleep
    limiter.wait("stepstone")                         # different source → no sleep

    assert slept == pytest.approx([0.8])
