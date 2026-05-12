"""Enrichment must persist the real company name to seen_jobs.

The dailyremote scraper hides employers behind "[Unlock with Premium]"
on listing pages and only exposes the real name in JSON-LD on the detail
page. Before this fix, fetch_detail correctly extracted "GTO Wizard"
but the runner discarded it — so the dashboard saw 50+ rows all labelled
"Unknown" and they collided into one dedup group.

Three contracts under regression test:

1. `update_enrichment(..., company="ACME")` writes ACME to seen_jobs.company.
2. `update_enrichment(..., company="Unknown")` does NOT overwrite — placeholder
   strings are on a deny-list. Same for the freelancermap-style anonymous tag.
3. End-to-end: the enrichment runner threads `enriched.company` through to
   `update_enrichment`, so a scraper whose fetch() returns "Unknown" but
   whose fetch_detail() returns "ACME" ends up with "ACME" in the DB.
"""
from __future__ import annotations

from pathlib import Path

from jobbot.models import JobPosting
from jobbot.state import (
    _is_real_company_name,
    connect,
    update_enrichment,
    upsert_new,
)


def _seed(db: Path, *, company: str = "Unknown") -> str:
    """Insert a job row with the given starting company name."""
    job = JobPosting(
        id="enrich_co_1", source="dailyremote",
        title="Product Manager", company=company,
        url="https://dailyremote.com/job/1",
        apply_url="https://dailyremote.com/job/1",
        description="listing snippet",
    )
    with connect(db) as conn:
        upsert_new(conn, [job])
    return job.id


def _read_company(db: Path, job_id: str) -> str:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT company FROM seen_jobs WHERE id = ?", (job_id,),
        ).fetchone()
    return row["company"]


# ---------------------------------------------------------------------------
# Contract 1 — real company name is persisted
# ---------------------------------------------------------------------------

def test_real_company_name_overwrites_listing_placeholder(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db, company="Unknown")

    with connect(db) as conn:
        update_enrichment(
            conn, job_id=job_id,
            description_full=" ".join(["responsibility"] * 200),
            description_scraped=True, description_word_count=200,
            seniority=None, salary_text=None, apply_email=None,
            company="GTO Wizard",
        )

    assert _read_company(db, job_id) == "GTO Wizard"


# ---------------------------------------------------------------------------
# Contract 2 — placeholder strings are filtered, never overwrite a real name
# ---------------------------------------------------------------------------

def test_placeholder_company_does_not_overwrite_real_name(
    tmp_path: Path, monkeypatch,
) -> None:
    """Defensive: if fetch_detail couldn't get the real company and falls
    back to 'Unknown', we must NOT overwrite a previously-good name."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db, company="ACME GmbH")  # already had real name

    with connect(db) as conn:
        update_enrichment(
            conn, job_id=job_id,
            description_full=" ".join(["x"] * 200),
            description_scraped=True, description_word_count=200,
            seniority=None, salary_text=None, apply_email=None,
            company="Unknown",
        )

    assert _read_company(db, job_id) == "ACME GmbH"


def test_freelancermap_anonymous_tag_is_a_placeholder(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db, company="Real Customer GmbH")

    with connect(db) as conn:
        update_enrichment(
            conn, job_id=job_id,
            description_full=" ".join(["x"] * 200),
            description_scraped=True, description_word_count=200,
            seniority=None, salary_text=None, apply_email=None,
            company="freelancermap (Auftraggeber anonym)",
        )

    assert _read_company(db, job_id) == "Real Customer GmbH"


def test_company_left_unchanged_when_none_passed(
    tmp_path: Path, monkeypatch,
) -> None:
    """Backwards-compat: callers that don't pass `company` should behave
    exactly as before (no UPDATE of the company column)."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    job_id = _seed(db, company="Original Inc")

    with connect(db) as conn:
        update_enrichment(
            conn, job_id=job_id,
            description_full=" ".join(["x"] * 200),
            description_scraped=True, description_word_count=200,
            seniority=None, salary_text=None, apply_email=None,
        )

    assert _read_company(db, job_id) == "Original Inc"


# ---------------------------------------------------------------------------
# Placeholder detection unit tests
# ---------------------------------------------------------------------------

def test_is_real_company_name_catches_known_placeholders() -> None:
    for placeholder in [
        "", "Unknown", "unknown", "  Unknown  ",
        "(see posting)", "[Unlock with Premium]",
        "Anonymous", "freelancermap (Auftraggeber anonym)",
        None,
    ]:
        assert not _is_real_company_name(placeholder), (
            f"{placeholder!r} should be filtered as a placeholder"
        )


def test_is_real_company_name_accepts_real_names() -> None:
    for name in ["GTO Wizard", "ACME GmbH", "N26", "Bundesagentur für Arbeit"]:
        assert _is_real_company_name(name), f"{name!r} should be accepted"


# ---------------------------------------------------------------------------
# Contract 3 — end-to-end via the enrichment runner
# ---------------------------------------------------------------------------

class _FakeScraperWithDetail:
    source = "dailyremote"

    def fetch_detail(self, job):
        long_body = " ".join(["responsibility"] * 240)
        return job.model_copy(update={
            "description": long_body,
            "company": "GTO Wizard",
        })


def test_enrichment_runner_persists_company_from_fetch_detail(
    tmp_path: Path, monkeypatch,
) -> None:
    import jobbot.enrichment.runner as runner

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _ = _seed(db, company="Unknown")

    # Reconstruct the JobPosting the runner expects to receive (the
    # pipeline normally passes JobPosting objects, not just job_ids).
    job = JobPosting(
        id="enrich_co_1", source="dailyremote",
        title="Product Manager", company="Unknown",
        url="https://dailyremote.com/job/1",
        apply_url="https://dailyremote.com/job/1",
        description="listing snippet",
    )

    with connect(db) as conn:
        runner.enrich_new_postings(
            [job], conn,
            registry={"dailyremote": _FakeScraperWithDetail()},
        )

    assert _read_company(db, job.id) == "GTO Wizard"
