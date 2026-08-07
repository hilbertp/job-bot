"""Job-alert email ingestion: parsing, dedup across emails, and the
guarantee that alert rows never trigger a fetch back to the board.

These boards (bayt.com, freelance.de) forbid crawling, so the email is the
only channel and the only body we will ever have. The tests pin both halves:
what we extract, and what we must never do afterwards.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from jobbot.alerts import runner as alert_runner
from jobbot.alerts.mailbox import AlertEmail
from jobbot.alerts.parsers import (
    canonical_url, dedup_key_for, parse_bayt, parse_freelance_de, parser_for,
)
from jobbot.config import Config, Secrets
from jobbot.state import connect, jobs_needing_enrichment

# A tracking link whose token differs per email, wrapping the real job URL.
_TRACKED = ("https://click.mail.bayt.com/f/a/{token}/AAH/x/"
            "?url=https%3A%2F%2Fwww.bayt.com%2Fen%2Fuae%2Fjobs%2F"
            "senior-product-manager-5412345%2F")

_BAYT_HTML = """
<html><body><table>
<tr><td>
  <a href="{link}">Senior Product Manager - Emirates NBD - Dubai, UAE</a>
  <p>{body}</p>
</td></tr>
<tr><td><a href="https://www.bayt.com/en/unsubscribe/">Unsubscribe</a></td></tr>
</table></body></html>
"""

_FREELANCE_HTML = """
<html><body>
<div class="projekt">
  <a href="https://mail.freelance.de/c/click?u=https%3A%2F%2Fwww.freelance.de%2F
projekte%2Fprojekt-998877-Product-Owner-Zahlungsverkehr">Product Owner Zahlungsverkehr</a>
  <p>Einsatzort: Frankfurt<br>{body}</p>
</div>
<a href="https://www.freelance.de/abmelden">Abmelden</a>
</body></html>
"""


def _long(words: int = 140) -> str:
    return " ".join(f"wort{i}" for i in range(words))


def _config(**kw) -> Config:
    cfg = Config()
    cfg.alerts.enabled = True
    for k, v in kw.items():
        setattr(cfg.alerts, k, v)
    return cfg


def _secrets() -> Secrets:
    return Secrets(anthropic_api_key="x", gmail_address="a@b.com",
                   gmail_app_password="x", notify_to="a@b.com")


def _email(sender: str, html: str) -> AlertEmail:
    return AlertEmail(sender=sender, subject="New jobs for your search",
                      received_at=datetime(2026, 8, 7, 6, 0, tzinfo=timezone.utc),
                      html=html, text="")


# ------------------------------- parsing -----------------------------------


def test_canonical_url_unwraps_tracker_without_http():
    wrapped = _TRACKED.format(token="TOKEN123")
    assert canonical_url(wrapped) == (
        "https://www.bayt.com/en/uae/jobs/senior-product-manager-5412345/"
    )


def test_dedup_key_is_stable_across_differing_tracking_tokens():
    """The same job in Monday's and Tuesday's alert must collapse to one row."""
    a = dedup_key_for(_TRACKED.format(token="MON"), "Senior PM", None)
    b = dedup_key_for(_TRACKED.format(token="TUE"), "Senior PM", None)
    assert a == b


def test_bayt_parser_splits_title_company_location():
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long())
    got = parse_bayt(html, "")
    assert len(got) == 1
    p = got[0]
    assert p.title == "Senior Product Manager"
    assert p.company == "Emirates NBD"
    assert p.location == "Dubai, UAE"
    assert p.url.startswith("https://www.bayt.com/")
    assert len(p.description.split()) >= 100


def test_parser_ignores_unsubscribe_and_footer_links():
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long())
    assert all("unsubscribe" not in p.title.lower() for p in parse_bayt(html, ""))


def test_freelance_de_parser_extracts_location_and_placeholder_company():
    got = parse_freelance_de(_FREELANCE_HTML.format(body=_long()), "")
    assert len(got) == 1
    assert got[0].location == "Frankfurt"
    # The client is hidden on freelance.de listings; the placeholder is what
    # update_enrichment knows how to overwrite later.
    assert got[0].company == "(see posting)"


def test_parser_for_routes_by_sender():
    assert parser_for("jobalert@bayt.com")[0] == "bayt_alert"
    assert parser_for("noreply@mail.freelance.de")[0] == "freelance_de_alert"
    assert parser_for("jobs@some-other-board.io")[0] == "job_alert"


def test_plaintext_only_alert_still_yields_postings():
    text = (
        "Neue Projekte fuer dich:\n"
        "Product Owner Zahlungsverkehr\n"
        "https://www.freelance.de/projekte/projekt-998877-Product-Owner\n"
        "Frankfurt, remote moeglich\n"
    )
    got = parse_freelance_de("", text)
    assert [p.title for p in got] == ["Product Owner Zahlungsverkehr"]


# ------------------------------ ingestion ----------------------------------


@pytest.fixture()
def db(tmp_path: Path, monkeypatch):
    import jobbot.state as state
    path = tmp_path / "jobbot.db"
    monkeypatch.setattr(state, "DB_PATH", path)
    return path


def _run(db, emails, monkeypatch, config=None):
    monkeypatch.setattr(alert_runner, "fetch_alert_emails",
                        lambda *a, **k: emails)
    with connect(db) as conn:
        summary = alert_runner.scan_alerts(conn, _secrets(), config or _config())
        rows = conn.execute(
            "SELECT id, source, title, company, description_full, "
            "description_scraped, status FROM seen_jobs"
        ).fetchall()
    return summary, rows


def test_ingest_creates_scorable_rows(db, monkeypatch):
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long())
    summary, rows = _run(db, [_email("jobalert@bayt.com", html)], monkeypatch)

    assert summary["new"] == 1
    assert summary["thin"] == 0
    assert rows[0]["source"] == "bayt_alert"
    assert rows[0]["company"] == "Emirates NBD"
    assert rows[0]["status"] == "scraped"          # ready for the scorer
    assert len(rows[0]["description_full"].split()) >= 100


def test_alert_rows_never_enter_the_enrichment_fetch_queue(db, monkeypatch):
    """The whole point: we must not send a request back to a board that
    forbids crawling, so these rows must be invisible to the retry queue."""
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long())
    _run(db, [_email("jobalert@bayt.com", html)], monkeypatch)
    with connect(db) as conn:
        assert jobs_needing_enrichment(conn) == []


def test_thin_alert_is_recorded_and_counted_not_dropped(db, monkeypatch):
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body="Apply now")
    summary, rows = _run(db, [_email("jobalert@bayt.com", html)], monkeypatch)
    assert summary["new"] == 1
    assert summary["thin"] == 1
    assert len(rows) == 1  # the link is kept even though it cannot be scored
    with connect(db) as conn:
        assert jobs_needing_enrichment(conn) == []  # still no crawl-back


def test_same_job_in_two_emails_is_one_row(db, monkeypatch):
    emails = [
        _email("jobalert@bayt.com",
               _BAYT_HTML.format(link=_TRACKED.format(token="MON"), body=_long())),
        _email("jobalert@bayt.com",
               _BAYT_HTML.format(link=_TRACKED.format(token="TUE"), body=_long())),
    ]
    summary, rows = _run(db, emails, monkeypatch)
    assert summary["postings"] == 1
    assert summary["new"] == 1
    assert len(rows) == 1


def test_rescanning_the_same_email_adds_nothing(db, monkeypatch):
    """Scans are idempotent, which is what lets the mailbox stay read-only."""
    html = _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long())
    emails = [_email("jobalert@bayt.com", html)]
    _run(db, emails, monkeypatch)
    summary, rows = _run(db, emails, monkeypatch)
    assert summary["new"] == 0
    assert len(rows) == 1


def test_disabled_alerts_do_nothing(db, monkeypatch):
    cfg = _config()
    cfg.alerts.enabled = False
    called = []
    monkeypatch.setattr(alert_runner, "fetch_alert_emails",
                        lambda *a, **k: called.append(1) or [])
    with connect(db) as conn:
        summary = alert_runner.scan_alerts(conn, _secrets(), cfg)
    assert summary["skipped"]
    assert called == []


def test_broken_parser_does_not_abort_the_scan(db, monkeypatch):
    """One malformed alert must not cost us the rest of the batch."""
    good = _email("jobalert@bayt.com",
                  _BAYT_HTML.format(link=_TRACKED.format(token="A"), body=_long()))
    bad = _email("jobalert@bayt.com", "<html><body>truncated")

    def flaky(html, text):
        if "Senior Product Manager" not in html:
            raise ValueError("boom")
        return parse_bayt(html, text)

    monkeypatch.setattr("jobbot.alerts.runner.parser_for",
                        lambda sender: ("bayt_alert", flaky))
    summary, rows = _run(db, [bad, good], monkeypatch)
    assert summary["new"] == 1
    assert len(rows) == 1
