"""Static-site builder: DB rows -> index.html + data.json + docs/."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jobbot.config import Config
from jobbot.models import JobPosting, JobStatus
from jobbot.publish.site import build_site, collect_site_jobs
from jobbot.state import connect, update_status, upsert_new


def _mk_job(i: int, source: str = "remotive", **kw) -> JobPosting:
    defaults = dict(
        id=f"{source}_{i:016d}",
        source=source,
        title=f"Product Manager {i}",
        company=f"Acme {i}",
        location="Remote, EU",
        url=f"https://example.com/jobs/{i}",
        apply_url=f"https://example.com/jobs/{i}/apply",
        description="word " * 150,
    )
    defaults.update(kw)
    return JobPosting(**defaults)


@pytest.fixture()
def db(tmp_path: Path):
    with connect(tmp_path / "test.db") as conn:
        yield conn


def _config(**publish_kw) -> Config:
    cfg = Config()
    for k, v in publish_kw.items():
        setattr(cfg.publish, k, v)
    return cfg


def _seed(conn: sqlite3.Connection, jobs_with_scores: list[tuple[JobPosting, int]]):
    upsert_new(conn, [j for j, _ in jobs_with_scores])
    for job, score in jobs_with_scores:
        update_status(conn, job.id, JobStatus.SCORED, score=score, reason="r")


def test_collect_filters_by_score_and_age(db):
    old = _mk_job(1)
    fresh_low = _mk_job(2)
    fresh_high = _mk_job(3)
    _seed(db, [(old, 90), (fresh_low, 40), (fresh_high, 82)])
    stale = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    db.execute("UPDATE seen_jobs SET first_seen_at = ? WHERE id = ?", (stale, old.id))

    got = collect_site_jobs(db, _config(min_score=60, max_age_days=45))
    assert [j["id"] for j in got] == [fresh_high.id]
    assert got[0]["apply_route"] == "url"
    assert got[0]["apply_target"] == "https://example.com/jobs/3/apply"
    assert got[0]["location"] == "Remote, EU"


def test_posted_today_only_filters_older_postings(db):
    from datetime import datetime as dt
    now = dt(2026, 7, 27, 14, 0, tzinfo=timezone.utc)
    posted_today = _mk_job(1, posted_at=dt(2026, 7, 27, 6, 0, tzinfo=timezone.utc))
    posted_earlier = _mk_job(2, posted_at=dt(2026, 7, 24, 6, 0, tzinfo=timezone.utc))
    no_posted_at = _mk_job(3)  # falls back to first_seen_at (= today)
    _seed(db, [(posted_today, 80), (posted_earlier, 90), (no_posted_at, 70)])
    db.execute("UPDATE seen_jobs SET first_seen_at = ?",
               (now.isoformat(),))

    got = collect_site_jobs(db, _config(posted_today_only=True), now=now)
    assert {j["id"] for j in got} == {posted_today.id, no_posted_at.id}

    # Off by default: all three rows survive.
    got_all = collect_site_jobs(db, _config(), now=now)
    assert len(got_all) == 3


def test_collect_orders_by_best_score(db):
    a, b = _mk_job(1), _mk_job(2)
    _seed(db, [(a, 70), (b, 75)])
    # a's tailored rescore beats b's base score.
    db.execute("UPDATE seen_jobs SET score_tailored = 92 WHERE id = ?", (a.id,))
    got = collect_site_jobs(db, _config(min_score=60))
    assert [j["id"] for j in got] == [a.id, b.id]


def test_hard_paywalled_row_has_no_apply_route(db):
    j = _mk_job(1, source="dailyremote",
                url="https://dailyremote.com/remote-job/pm-1",
                apply_url="https://dailyremote.com/remote-job/pm-1")
    _seed(db, [(j, 80)])
    got = collect_site_jobs(db, _config(min_score=60))
    assert got[0]["apply_route"] == "missing"
    assert got[0]["apply_target"] is None


def test_build_site_writes_page_data_and_docs(db, tmp_path: Path):
    j = _mk_job(1)
    _seed(db, [(j, 88)])
    out_dir = tmp_path / "output" / "2026-07-27" / "remotive__acme-1__pm"
    out_dir.mkdir(parents=True)
    (out_dir / "cv.pdf").write_bytes(b"%PDF-1.4 cv")
    (out_dir / "cover_letter.pdf").write_bytes(b"%PDF-1.4 cl")
    db.execute("UPDATE seen_jobs SET output_dir = ?, status = 'generated' WHERE id = ?",
               (str(out_dir), j.id))

    site_dir = tmp_path / "site"
    report = build_site(db, _config(min_score=60), site_dir, repo_root=tmp_path)

    assert report.n_jobs == 1
    assert report.n_docs_copied == 2
    assert (site_dir / ".nojekyll").exists()
    html = (site_dir / "index.html").read_text()
    assert "Acme 1" in html
    assert f"docs/{j.id}/cv.pdf" in html
    assert 'id="timewin"' in html      # posted-time filter control
    assert 'data-posted="' in html     # per-row stamp the filter reads
    assert 'id="filter-empty"' in html
    assert 'id="run-now"' in html      # manual trigger button
    assert "http://127.0.0.1:5001/api/runs/trigger" in html
    assert 'id="active-run"' in html   # live progress panel
    assert "http://127.0.0.1:5001/api/runs/active" in html
    assert 'id="ar-dot"' in html       # liveness pulse indicator
    assert "ar-pulse" in html          # its animation, gated on freshness
    assert "run may be stuck" in html  # stalled-state copy
    # Pending stages say what they are waiting FOR, not a bare "waiting"
    # and never 0/0. The old assertion pinned the literal string 'waiting';
    # the copy now names the blocking stage, which is the same intent said
    # better, so the assertion follows the intent rather than the literal.
    assert "waiting to start" in html
    assert "waiting for " in html
    assert "STAGE_UNITS" in html       # counts carry their unit, not a bare 29/29
    assert "min left" in html          # active stage carries a rate-based ETA
    assert 'id="ar-ticker"' in html    # live results feed
    assert 'id="ar-strong"' in html    # running strong-match counter
    assert 'id="ar-fails"' in html     # inline failure reasons
    assert "backlog" in html           # scoring queue split new vs backlog
    assert "already known" in html     # scrape→fetch funnel: dedup count
    assert "to fetch" in html          # funnel: what actually gets fetched
    assert "funnelrow" in html         # the in-between row itself
    assert "could not fetch details" in html  # fetch failures named by board
    assert "retries)" in html          # fetch queue split new vs retries
    # Every row links to the posting itself, apply route or not.
    assert f'class="titlelink" href="https://example.com/jobs/1"' in html
    assert "https://example.com/jobs/1/apply" in html
    data = json.loads((site_dir / "data.json").read_text())
    assert data["jobs"][0]["company"] == "Acme 1"
    assert data["jobs"][0]["documents"] == ["cv.pdf", "cover_letter.pdf"]
    assert (site_dir / "docs" / j.id / "cover_letter.pdf").read_bytes() == b"%PDF-1.4 cl"


def test_build_site_include_documents_false_keeps_pdfs_off_site(db, tmp_path: Path):
    j = _mk_job(1)
    _seed(db, [(j, 88)])
    out_dir = tmp_path / "pkg"
    out_dir.mkdir()
    (out_dir / "cv.pdf").write_bytes(b"%PDF")
    db.execute("UPDATE seen_jobs SET output_dir = ? WHERE id = ?", (str(out_dir), j.id))

    site_dir = tmp_path / "site"
    report = build_site(db, _config(include_documents=False), site_dir,
                        repo_root=tmp_path)
    assert report.n_docs_copied == 0
    assert not (site_dir / "docs").exists()
    data = json.loads((site_dir / "data.json").read_text())
    assert data["jobs"][0]["documents"] == []


def test_build_site_removes_stale_docs(db, tmp_path: Path):
    j = _mk_job(1)
    _seed(db, [(j, 88)])
    site_dir = tmp_path / "site"
    stale = site_dir / "docs" / "gone_job" / "cv.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    build_site(db, _config(), site_dir, repo_root=tmp_path)
    assert not stale.exists()
