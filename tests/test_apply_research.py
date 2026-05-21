"""Apply-path research: resolve canonical employer apply URLs for
paywalled-aggregator rows during enrichment.

The Anthropic web_search call is mocked. We pin: JSON parsing (incl.
fenced + prose-wrapped), the null/failure path, and the enrichment
integration (only paywalled rows researched, per-run cap, per
company+title cache, resolved URL persisted to raw_json).
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jobbot.enrichment.apply_research import _extract_json, research_apply_url


def _secrets():
    return SimpleNamespace(anthropic_api_key="x")


def _msg(text: str):
    blk = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[blk])


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

def test_extract_plain_json():
    d = _extract_json('{"apply_url": "https://x.io/jobs/1", "ats": "Greenhouse"}')
    assert d["apply_url"] == "https://x.io/jobs/1"


def test_extract_fenced_json():
    d = _extract_json('```json\n{"apply_url": "https://x.io/1"}\n```')
    assert d["apply_url"] == "https://x.io/1"


def test_extract_json_amid_prose():
    d = _extract_json('Here is the result: {"apply_url": null, "reason": "not found"} done')
    assert d["apply_url"] is None


def test_extract_garbage_returns_none():
    assert _extract_json("sorry, no idea") is None


# ---------------------------------------------------------------------------
# research_apply_url
# ---------------------------------------------------------------------------

def test_research_returns_canonical_url():
    payload = '{"apply_url": "https://approvalmax.teamtailor.com/jobs/777", "ats": "TeamTailor", "confidence": "high", "reason": "exact"}'
    client = MagicMock()
    client.messages.create.return_value = _msg(payload)
    with patch("anthropic.Anthropic", return_value=client):
        url, note = research_apply_url(
            "ApprovalMax", "Product Manager",
            "https://dailyremote.com/remote-job/pm-5006763", _secrets(),
        )
    assert url == "https://approvalmax.teamtailor.com/jobs/777"
    assert "TeamTailor" in note


def test_research_null_when_not_found():
    payload = '{"apply_url": null, "ats": null, "confidence": "low", "reason": "no employer page"}'
    client = MagicMock()
    client.messages.create.return_value = _msg(payload)
    with patch("anthropic.Anthropic", return_value=client):
        url, note = research_apply_url("Obscure Co", "PM", "https://dailyremote.com/x", _secrets())
    assert url is None
    assert "no employer page" in note


def test_research_rejects_non_http_url():
    payload = '{"apply_url": "see company website", "ats": "n/a"}'
    client = MagicMock()
    client.messages.create.return_value = _msg(payload)
    with patch("anthropic.Anthropic", return_value=client):
        url, _ = research_apply_url("Co", "PM", "https://dailyremote.com/x", _secrets())
    assert url is None


def test_research_handles_api_error():
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("rate limited")
    with patch("anthropic.Anthropic", return_value=client):
        url, note = research_apply_url("Co", "PM", "https://dailyremote.com/x", _secrets())
    assert url is None
    assert "error" in note.lower()


def test_research_skips_without_company_or_title():
    url, _ = research_apply_url("", "PM", "https://x", _secrets())
    assert url is None


# ---------------------------------------------------------------------------
# enrichment integration
# ---------------------------------------------------------------------------

def _make_scraper(detail_job):
    class _S:
        source = detail_job.source
        def fetch_detail(self, job):
            return detail_job
    return {detail_job.source: _S()}


def _config(enabled=True, cap=50):
    return SimpleNamespace(
        apply_research_enabled=enabled, apply_research_max_per_run=cap,
    )


def test_enrichment_researches_only_paywalled_rows(tmp_path, monkeypatch):
    from jobbot.enrichment.runner import enrich_new_postings
    from jobbot.models import JobPosting
    from jobbot.state import connect, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    body = "Senior Product Manager. " * 60  # > 100 words so it enriches
    paywalled = JobPosting(
        id="dr1", source="dailyremote", title="Product Manager", company="ApprovalMax",
        url="https://dailyremote.com/remote-job/pm-1",
        apply_url="https://dailyremote.com/remote-job/pm-1", description=body,
    )
    clean = JobPosting(
        id="gh1", source="dailyremote", title="PM", company="Acme",
        url="https://boards.greenhouse.io/acme/jobs/9",
        apply_url="https://boards.greenhouse.io/acme/jobs/9", description=body,
    )
    with connect(db) as conn:
        upsert_new(conn, [paywalled, clean])

    calls = []
    def _fake_research(company, title, current_url, secrets, **kw):
        calls.append(company)
        return "https://approvalmax.teamtailor.com/jobs/777", "TeamTailor (high)"

    monkeypatch.setattr(
        "jobbot.enrichment.apply_research.research_apply_url", _fake_research)

    with connect(db) as conn:
        enrich_new_postings(
            [paywalled, clean], conn,
            registry={"dailyremote": _make_scraper(paywalled)["dailyremote"]},
            config=_config(), secrets=_secrets(),
        )
        # Only the paywalled row should have been researched.
        assert calls == ["ApprovalMax"], f"researched wrong set: {calls}"
        dr = json.loads(conn.execute(
            "SELECT raw_json FROM seen_jobs WHERE id='dr1'").fetchone()["raw_json"])
        gh = json.loads(conn.execute(
            "SELECT raw_json FROM seen_jobs WHERE id='gh1'").fetchone()["raw_json"])
    assert dr["apply_url"] == "https://approvalmax.teamtailor.com/jobs/777"
    assert gh["apply_url"] == "https://boards.greenhouse.io/acme/jobs/9"  # untouched


def test_enrichment_research_respects_cap(tmp_path, monkeypatch):
    from jobbot.enrichment.runner import enrich_new_postings
    from jobbot.models import JobPosting
    from jobbot.state import connect, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    body = "Product Manager role. " * 60
    jobs = [
        JobPosting(id=f"dr{i}", source="dailyremote", title=f"PM {i}",
                   company=f"Co{i}", url=f"https://dailyremote.com/j{i}",
                   apply_url=f"https://dailyremote.com/j{i}", description=body)
        for i in range(3)
    ]
    with connect(db) as conn:
        upsert_new(conn, jobs)

    calls = []
    def _fake_research(company, *a, **k):
        calls.append(company)
        return "https://x.io/canonical", "ATS"
    monkeypatch.setattr(
        "jobbot.enrichment.apply_research.research_apply_url", _fake_research)

    class _S:
        source = "dailyremote"
        def __init__(self, jobs): self._m = {j.id: j for j in jobs}
        def fetch_detail(self, job): return self._m[job.id]

    with connect(db) as conn:
        enrich_new_postings(
            jobs, conn, registry={"dailyremote": _S(jobs)},
            config=_config(cap=2), secrets=_secrets(),
        )
    assert len(calls) == 2, f"cap not respected: {calls}"


def test_enrichment_no_research_when_disabled(tmp_path, monkeypatch):
    from jobbot.enrichment.runner import enrich_new_postings
    from jobbot.models import JobPosting
    from jobbot.state import connect, upsert_new

    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    body = "Product Manager. " * 60
    job = JobPosting(id="dr1", source="dailyremote", title="PM", company="Co",
                     url="https://dailyremote.com/j1",
                     apply_url="https://dailyremote.com/j1", description=body)
    with connect(db) as conn:
        upsert_new(conn, [job])

    called = []
    monkeypatch.setattr(
        "jobbot.enrichment.apply_research.research_apply_url",
        lambda *a, **k: called.append(1) or ("x", "y"))

    class _S:
        source = "dailyremote"
        def fetch_detail(self, j): return job
    with connect(db) as conn:
        enrich_new_postings(
            [job], conn, registry={"dailyremote": _S()},
            config=_config(enabled=False), secrets=_secrets(),
        )
    assert called == [], "research ran while disabled"
