"""A posting the source has pulled must leave the retry queue for good.

`fetch_detail` returning None means "no usable body this time", which the
runner treats as transient: the row keeps `description_scraped = 0` and is
retried on later runs. That is correct for a 429 or a timeout, and wrong for
a listing that no longer exists. Measured on 2026-07-31, 37 of 100 detail
fetches failed per run, dominated by StepStone answering HTTP 410 and
LinkedIn redirecting to a generic search page with `trk=expired_jd_redirect`.
Those URLs will never produce a body, so every retry is pure waste.

Scrapers now raise `ListingGone` for that case and the runner marks the row
`listing_expired`, which is in TERMINAL_STATUSES and therefore leaves both
the enrichment and the scoring queue.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.enrichment.runner import enrich_new_postings
from jobbot.models import JobPosting, JobStatus, TERMINAL_STATUSES
from jobbot.scrapers.base import ListingGone
from jobbot.state import connect, jobs_needing_enrichment, upsert_new


def _job(job_id: str = "gone_1", source: str = "stepstone") -> JobPosting:
    return JobPosting(
        id=job_id, source=source,
        title="Product Owner", company="ACME",
        url=f"https://example.test/{job_id}",
        apply_url=f"https://example.test/{job_id}",
        description="listing card snippet, far too short to score",
    )


class _GoneScraper:
    """fetch_detail that reports the posting as withdrawn."""

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        raise ListingGone("stepstone returned HTTP 410")


class _TransientlyBrokenScraper:
    """fetch_detail that merely failed this time (rate limit, timeout)."""

    def fetch_detail(self, job: JobPosting) -> JobPosting | None:
        return None


def _status(db: Path, job_id: str) -> str:
    with connect(db) as conn:
        return conn.execute(
            "SELECT status FROM seen_jobs WHERE id = ?", (job_id,)
        ).fetchone()[0]


def test_listing_gone_marks_row_expired(tmp_path: Path) -> None:
    db = tmp_path / "jobbot.db"
    job = _job()
    with connect(db) as conn:
        upsert_new(conn, [job])
        report = enrich_new_postings(
            [job], conn, registry={"stepstone": _GoneScraper()},
        )

    assert report.n_expired == 1
    # A withdrawn listing is not an enrichment failure; counting it as one
    # would make the per-source health table blame the scraper.
    assert report.n_failed == 0
    assert _status(db, job.id) == JobStatus.LISTING_EXPIRED.value


def test_expired_row_is_terminal_and_never_re_enriched(tmp_path: Path) -> None:
    db = tmp_path / "jobbot.db"
    job = _job()
    with connect(db) as conn:
        upsert_new(conn, [job])
        enrich_new_postings([job], conn, registry={"stepstone": _GoneScraper()})
        again = [j.id for j in jobs_needing_enrichment(conn)]

    assert JobStatus.LISTING_EXPIRED.value in TERMINAL_STATUSES
    assert job.id not in again, "an expired listing must not re-enter the queue"


def test_transient_failure_still_gets_retried(tmp_path: Path) -> None:
    """The counterpart: a plain None must stay retryable, or one rate limit
    would strand a live posting forever (the bug this pairs with)."""
    db = tmp_path / "jobbot.db"
    job = _job(job_id="transient_1")
    with connect(db) as conn:
        upsert_new(conn, [job])
        report = enrich_new_postings(
            [job], conn, registry={"stepstone": _TransientlyBrokenScraper()},
        )
        again = [j.id for j in jobs_needing_enrichment(conn)]

    assert report.n_failed == 1
    assert report.n_expired == 0
    assert _status(db, job.id) != JobStatus.LISTING_EXPIRED.value
    assert job.id in again, "a transient failure must remain retryable"
