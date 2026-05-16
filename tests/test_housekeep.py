"""`housekeep_shortlist` HEAD-probes each live shortlist row and marks
dead apply URLs as `listing_expired`. Same probe runs in the apply
runner before launching a browser, just batched.

Pinned behaviours:
  - HTTP 410 → mark as expired with reason naming the status.
  - Redirect to /open-roles → mark as expired even when status is 200.
  - HTTP 200 on a real-looking apply URL → leave row alone.
  - apply_email set → skip the probe (email-apply rows have no URL).
  - Network error → leave row alone (not a strong signal).
  - dry_run=True → report but do not write.
  - Row already at a terminal status → skipped (not in the scan set).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from jobbot.housekeep import housekeep_shortlist
from jobbot.models import JobPosting, JobStatus
from jobbot.state import connect, upsert_new


def _seed(db_path: Path, rows):
    """Each `rows` entry: dict(id, status, score, apply_url=None, apply_email=None).
    Inserts via upsert_new + status update."""
    with connect(db_path) as conn:
        upsert_new(conn, [
            JobPosting(
                id=r["id"], source="test", title=f"PM {r['id']}",
                company="Acme", url=r.get("url", f"https://x.test/{r['id']}"),
                apply_url=r.get("apply_url") or r.get("url",
                                                     f"https://x.test/{r['id']}"),
                apply_email=r.get("apply_email"),
                description="body " * 30,
            )
            for r in rows
        ])
        for r in rows:
            conn.execute(
                "UPDATE seen_jobs SET status = ?, score = ?, apply_email = ? "
                "WHERE id = ?",
                (r["status"], r["score"], r.get("apply_email"), r["id"]),
            )


def _mock_head_for(urls_to_responses):
    """Build a context manager that mocks httpx.Client.head().
    `urls_to_responses` maps url substring → (status_code, final_url).
    """
    def _head(self, url, **_kw):
        for needle, (status, final) in urls_to_responses.items():
            if needle in url:
                resp = MagicMock()
                resp.status_code = status
                resp.url = final or url
                return resp
        resp = MagicMock()
        resp.status_code = 200
        resp.url = url
        return resp
    return patch("httpx.Client.head", _head)


def test_http_410_row_marked_listing_expired(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "gone", "status": JobStatus.SCORED.value, "score": 85,
        "apply_url": "https://dailyremote.com/jobs/gone-410",
    }])
    with _mock_head_for({"dailyremote": (410, None)}):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.marked_expired == 1
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status, discard_reason FROM seen_jobs WHERE id = 'gone'"
        ).fetchone()
    assert row["status"] == JobStatus.LISTING_EXPIRED.value
    assert "410" in (row["discard_reason"] or "")


def test_redirect_to_open_roles_marked_listing_expired(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "consensys", "status": JobStatus.SCORED.value, "score": 91,
        "apply_url": "https://job-boards.greenhouse.io/consensys/jobs/7551395",
    }])
    with _mock_head_for({
        "consensys/jobs": (200, "https://consensys.io/open-roles"),
    }):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.marked_expired == 1
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status FROM seen_jobs WHERE id = 'consensys'"
        ).fetchone()
    assert row["status"] == JobStatus.LISTING_EXPIRED.value


def test_live_apply_url_is_left_alone(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "live", "status": JobStatus.SCORED.value, "score": 88,
        "apply_url": "https://greenhouse.io/x/jobs/12345",
    }])
    with _mock_head_for({"greenhouse.io/x/jobs/12345": (200, None)}):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.marked_expired == 0
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status FROM seen_jobs WHERE id = 'live'"
        ).fetchone()
    assert row["status"] == JobStatus.SCORED.value


def test_email_apply_row_is_skipped(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "email", "status": JobStatus.SCORED.value, "score": 80,
        "apply_email": "jobs@x.com",
    }])
    # No HTTP mock needed; the probe must not call HEAD for email rows.
    with patch("httpx.Client.head", side_effect=AssertionError(
        "HEAD must not be called for email-apply rows"
    )):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.skipped_email_apply == 1
    assert report.marked_expired == 0


def test_network_error_leaves_row_alone(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "neterr", "status": JobStatus.SCORED.value, "score": 80,
        "apply_url": "https://timeout.example/job",
    }])
    def _boom(self, url, **_kw):
        raise httpx.ConnectError("simulated network error")
    with patch("httpx.Client.head", _boom):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.network_errors == 1
    assert report.marked_expired == 0
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status FROM seen_jobs WHERE id = 'neterr'"
        ).fetchone()
    assert row["status"] == JobStatus.SCORED.value


def test_dry_run_does_not_write(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [{
        "id": "would_mark", "status": JobStatus.SCORED.value, "score": 80,
        "apply_url": "https://dailyremote.com/jobs/x",
    }])
    with _mock_head_for({"dailyremote": (410, None)}):
        with connect(db) as conn:
            report = housekeep_shortlist(conn, dry_run=True)
    assert report.marked_expired == 1
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status FROM seen_jobs WHERE id = 'would_mark'"
        ).fetchone()
    assert row["status"] == JobStatus.SCORED.value, (
        "dry_run must not write to DB"
    )


def test_terminal_status_rows_are_skipped(tmp_path: Path, monkeypatch) -> None:
    """An already-listing_expired row must not be probed again. Same for
    apply_submitted / rejected / interview_invited / etc. — those are
    terminal states the audit should leave alone."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed(db, [
        {"id": "already_expired", "status": JobStatus.LISTING_EXPIRED.value, "score": 72},
        {"id": "already_applied", "status": JobStatus.APPLY_SUBMITTED.value, "score": 88},
    ])
    with patch("httpx.Client.head", side_effect=AssertionError(
        "HEAD must not be called for terminal-status rows"
    )):
        with connect(db) as conn:
            report = housekeep_shortlist(conn)
    assert report.scanned == 0
