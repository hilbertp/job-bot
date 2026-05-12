"""5-stage outcome funnel on the dashboard top strip.

Pins:
  - The five stages render in the user-specified order with the
    correct absolute counts.
  - Percent badges are computed against Total and color-bucketed
    (red < 20%, amber 20-50%, green >= 50%).
  - `cannot_score:*` rows count toward Total but NOT toward Suitable.
  - The Interviewed card carries an `M5` pill so the placeholder zero
    is read as expected, not a bug.
  - The old "Scraped 0 / Last 24h" tiles are gone; Activity Today now
    lives in the Recent Runs header.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from jobbot.dashboard.server import _load_legacy_dashboard_module

_dashboard = _load_legacy_dashboard_module()
compute_funnel = _dashboard.compute_funnel
compute_activity_today = _dashboard.compute_activity_today
_percentage_color = _dashboard._percentage_color
from jobbot.models import JobPosting, JobStatus
from jobbot.state import (
    connect,
    record_application,
    update_enrichment,
    update_status,
    upsert_new,
)


def _job(job_id: str, source: str = "linkedin") -> JobPosting:
    return JobPosting(
        id=job_id,
        source=source,
        title="Senior PM",
        company="Acme",
        url=f"https://example.com/jobs/{job_id}",  # type: ignore[arg-type]
        apply_url=f"https://example.com/jobs/{job_id}",  # type: ignore[arg-type]
        description="snippet",
    )


def _seed_known_funnel(db: Path) -> None:
    """Seed a DB with:
        Total       = 10  (10 rows in seen_jobs)
        Suitable    =  6  (6 rows with score >= 70)
        Tailored    =  3  (3 rows with output_dir set)
        Applied     =  1  (1 application submitted=1)
        Interviewed =  0  (proof_level column doesn't exist yet)

    Includes 1 `cannot_score:no_body` row that counts toward Total but
    not toward Suitable (score remains NULL).
    """
    with connect(db) as conn:
        # 10 rows scraped
        jobs = [_job(f"j{i}") for i in range(10)]
        upsert_new(conn, jobs)

        # Mark j0 as cannot_score:no_body — counted in Total, NOT in Suitable
        update_status(
            conn, "j0", JobStatus.CANNOT_SCORE_NO_BODY,
            reason="< 100 words",
        )

        # 6 rows score >= 70 (j1..j6)
        for i in range(1, 7):
            update_status(
                conn, f"j{i}", JobStatus.SCORED, score=80, reason="good fit",
            )

        # j7..j9 stay at score < 70 (below threshold)
        for i in range(7, 10):
            update_status(
                conn, f"j{i}", JobStatus.BELOW_THRESHOLD,
                score=40, reason="weak",
            )

        # 3 of the 6 suitable rows went through Stage 3 generation
        for i in range(1, 4):
            update_status(
                conn, f"j{i}", JobStatus.GENERATED,
                output_dir=f"/tmp/{i}",
            )

        # 1 of the 3 tailored was actually submitted
        class _R:
            status = JobStatus.APPLY_SUBMITTED
            submitted = True
            dry_run = False
            needs_review_reason = None
            error = None
            screenshot_path = None
            confirmation_url = None

        record_application(conn, "j1", _R())


# ---------------------------------------------------------------------------
# compute_funnel — pure computation
# ---------------------------------------------------------------------------

def test_funnel_has_five_stages_in_order(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    with connect(db) as conn:
        funnel = compute_funnel(conn)

    assert [s["label"] for s in funnel] == [
        "Total", "Suitable", "Tailored", "Applied", "Interviewed",
    ]


def test_funnel_absolute_counts(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    with connect(db) as conn:
        funnel = compute_funnel(conn)

    counts = {s["label"]: s["count"] for s in funnel}
    assert counts == {
        "Total": 10,
        "Suitable": 6,
        "Tailored": 3,
        "Applied": 1,
        "Interviewed": 0,
    }


def test_cannot_score_row_counts_total_but_not_suitable(
    tmp_path: Path, monkeypatch,
) -> None:
    """The pre-fix scoring gate refuses some rows as cannot_score:no_body —
    their score column stays NULL. They must still appear in Total (they
    were scraped) but must NOT inflate Suitable."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    with connect(db) as conn:
        upsert_new(conn, [_job("only_cannot")])
        update_status(
            conn, "only_cannot", JobStatus.CANNOT_SCORE_NO_BODY,
            reason="< 100 words",
        )
        # NOTE: no score recorded — column stays NULL.

        funnel = compute_funnel(conn)

    counts = {s["label"]: s["count"] for s in funnel}
    assert counts["Total"] == 1
    assert counts["Suitable"] == 0


def test_funnel_percentages_are_against_total_jobs(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    with connect(db) as conn:
        funnel = compute_funnel(conn)

    by_label = {s["label"]: s for s in funnel}
    assert by_label["Total"]["pct_of_total"] is None
    assert by_label["Suitable"]["pct_of_total"] == 60.0      # 6/10
    assert by_label["Tailored"]["pct_of_total"] == 30.0      # 3/10
    assert by_label["Applied"]["pct_of_total"] == 10.0       # 1/10
    assert by_label["Interviewed"]["pct_of_total"] == 0.0    # 0/10


def test_percentage_color_thresholds() -> None:
    """Red < 20%, amber 20-50%, green 50%+."""
    assert _percentage_color(0.0) == "red"
    assert _percentage_color(19.9) == "red"
    assert _percentage_color(20.0) == "amber"
    assert _percentage_color(49.9) == "amber"
    assert _percentage_color(50.0) == "green"
    assert _percentage_color(100.0) == "green"
    assert _percentage_color(None) == "neutral"


def test_funnel_percentage_color_assignment(
    tmp_path: Path, monkeypatch,
) -> None:
    """Seeded fixture: Suitable 60% (green), Tailored 30% (amber),
    Applied 10% (red), Interviewed 0% (red)."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    with connect(db) as conn:
        funnel = compute_funnel(conn)

    by_label = {s["label"]: s for s in funnel}
    assert by_label["Total"]["percentage_color"] == "neutral"
    assert by_label["Suitable"]["percentage_color"] == "green"
    assert by_label["Tailored"]["percentage_color"] == "amber"
    assert by_label["Applied"]["percentage_color"] == "red"
    assert by_label["Interviewed"]["percentage_color"] == "red"


def test_interviewed_has_pending_milestone_flag(
    tmp_path: Path, monkeypatch,
) -> None:
    """Interviewed should carry the M5 pending-milestone tag so the
    template can render the placeholder pill."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    with connect(db) as conn:
        funnel = compute_funnel(conn)

    by_label = {s["label"]: s for s in funnel}
    assert by_label["Interviewed"]["pending_milestone"] == "M5"
    for other in ("Total", "Suitable", "Tailored", "Applied"):
        assert by_label[other]["pending_milestone"] is None


def test_funnel_empty_db_renders_zeros_and_no_percentage(
    tmp_path: Path, monkeypatch,
) -> None:
    """No rows anywhere — every count is 0; percentages are undefined
    because there is no total denominator."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    with connect(db) as conn:
        funnel = compute_funnel(conn)

    assert all(s["count"] == 0 for s in funnel)
    assert funnel[0]["pct_of_total"] is None
    for s in funnel[1:]:
        assert s["pct_of_total"] is None
        assert s["percentage_color"] == "neutral"


# ---------------------------------------------------------------------------
# compute_activity_today — moves the old "Last 24h" tile into Recent Runs
# ---------------------------------------------------------------------------

def test_activity_today_counts_within_24h_window(
    tmp_path: Path, monkeypatch,
) -> None:
    """1 posted in last 24h, 1 outside; 1 scored, 1 applied."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)

    with connect(db) as conn:
        upsert_new(conn, [_job("recent"), _job("old")])
        # Backdate "old" to >24h ago.
        conn.execute(
            "UPDATE seen_jobs SET first_seen_at = ? WHERE id = ?",
            ((now - timedelta(hours=48)).isoformat(), "old"),
        )
        # Mark "recent" as scored within the window.
        conn.execute(
            "UPDATE seen_jobs SET scored_at = ?, score = 80 WHERE id = ?",
            ((now - timedelta(hours=2)).isoformat(), "recent"),
        )

        class _R:
            status = JobStatus.APPLY_SUBMITTED
            submitted = True
            dry_run = False
            needs_review_reason = None
            error = None
            screenshot_path = None
            confirmation_url = None

        record_application(conn, "recent", _R())

        activity = compute_activity_today(conn, now=now)

    assert activity == {"posted": 1, "scored": 1, "applied": 1}


# ---------------------------------------------------------------------------
# Template rendering — full home page check
# ---------------------------------------------------------------------------

def test_dashboard_home_renders_five_funnel_cards(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")

    strip = soup.find(id="funnel-strip")
    assert strip is not None
    cards = strip.find_all(attrs={"data-funnel-stage": True})
    assert [c["data-funnel-stage"] for c in cards] == [
        "total", "suitable", "tailored", "applied", "interviewed",
    ]
    counts = [c.find(attrs={"data-funnel-count": True}).get_text(strip=True)
              for c in cards]
    assert counts == ["10", "6", "3", "1", "0"]


def test_dashboard_home_renders_percentage_color_classes(
    tmp_path: Path, monkeypatch,
) -> None:
    """The seeded fixture produces green/amber/red/red — assert each
    card carries the matching data-funnel-percentage attribute."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find(id="funnel-strip").find_all(attrs={"data-funnel-stage": True})

    # The Total card has no percentage badge; the other four do.
    badges = [c.find(attrs={"data-funnel-percentage": True}) for c in cards]
    assert badges[0] is None
    assert badges[1]["data-funnel-percentage"] == "green"   # Suitable 60%
    assert badges[2]["data-funnel-percentage"] == "amber"   # Tailored 30%
    assert badges[3]["data-funnel-percentage"] == "red"     # Applied 10%
    assert badges[4]["data-funnel-percentage"] == "red"     # Interviewed 0%


def test_dashboard_home_renders_m5_pill_on_interviewed(
    tmp_path: Path, monkeypatch,
) -> None:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")

    interviewed = soup.find(attrs={"data-funnel-stage": "interviewed"})
    pill = interviewed.find(attrs={"data-funnel-pending-milestone": True})
    assert pill is not None
    assert pill.get_text(strip=True) == "M5"

    # Sanity: no other card has the pill.
    for stage in ("total", "suitable", "tailored", "applied"):
        card = soup.find(attrs={"data-funnel-stage": stage})
        assert card.find(attrs={"data-funnel-pending-milestone": True}) is None


def test_dashboard_home_drops_legacy_kpi_strip(
    tmp_path: Path, monkeypatch,
) -> None:
    """The old six tiles (Scraped / Scored / Tailored / Applied / Last 24h)
    must be gone from the top strip — keeping them around would re-confuse
    the user who reported 'Scraped 0' against 'Total Jobs 350'."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")
    strip = soup.find(id="funnel-strip")

    # Inside the funnel strip there must be no "Scraped" / "Last 24h" header.
    text = strip.get_text(" ", strip=True)
    assert "Scraped" not in text
    assert "Last 24h" not in text


def test_dashboard_home_moves_activity_today_into_recent_runs(
    tmp_path: Path, monkeypatch,
) -> None:
    """The old 'Last 24h' tile is now an 'Activity today' subline in
    Recent Runs, with three counters: posted / scored / applied."""
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    _seed_known_funnel(db)

    client = _load_legacy_dashboard_module().app.test_client()
    html = client.get("/").get_data(as_text=True)
    soup = BeautifulSoup(html, "html.parser")

    panel = soup.find(id="recent-runs-panel")
    assert panel is not None
    activity = panel.find(id="activity-today")
    assert activity is not None
    labels = {el["data-activity"]: el.get_text(strip=True)
              for el in activity.find_all(attrs={"data-activity": True})}
    assert set(labels.keys()) == {"posted", "scored", "applied"}
    # Every value must be a numeric string (an int rendered by Jinja).
    for v in labels.values():
        assert v.isdigit()
