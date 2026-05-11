"""Pure-parsing tests for the four new remote-job portal scrapers.

These mock httpx/feedparser at the boundary so they never hit the network.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from jobbot.scrapers.dailyremote import DailyRemoteScraper
from jobbot.scrapers.nodesk import NoDeskScraper, _split_title_company
from jobbot.scrapers.working_nomads import WorkingNomadsScraper


# --------------------------- working_nomads --------------------------------


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


_WN_PAYLOAD = [
    {
        "url": "https://www.workingnomads.com/job/go/1/",
        "title": "Senior Product Manager",
        "description": "<p>We are hiring a " + "remote " * 110 + "PM.</p>",
        "company_name": "Acme",
        "category_name": "Product",
        "tags": "product,saas,remote",
        "location": "Anywhere",
        "pub_date": "2026-05-11T04:28:08-04:00",
    },
    {
        "url": "https://www.workingnomads.com/job/go/2/",
        "title": "Frontend Engineer",
        "description": "<p>React.</p>",
        "company_name": "Beta",
        "category_name": "Engineering",
        "tags": "react,frontend",
        "location": "Anywhere",
        "pub_date": "2026-05-10T04:28:08-04:00",
    },
]


def test_working_nomads_fetch_filters_by_query(monkeypatch):
    scraper = WorkingNomadsScraper()
    monkeypatch.setattr(
        "jobbot.scrapers.working_nomads.httpx.get",
        lambda *a, **kw: _FakeResp(_WN_PAYLOAD),
    )

    got_all = scraper.fetch({"q": ""})
    assert [j.company for j in got_all] == ["Acme", "Beta"]

    got_product = scraper.fetch({"q": "product"})
    assert [j.company for j in got_product] == ["Acme"]
    assert got_product[0].source == "working_nomads"
    assert got_product[0].id.startswith("working_nomads_")
    assert "remote" in got_product[0].tags


def test_working_nomads_fetch_detail_threshold():
    scraper = WorkingNomadsScraper()
    # >= 100 words: returns same job (description preserved)
    long_job = scraper.fetch({"q": ""})[0] if False else None  # silence linter

    # Build a JobPosting directly to avoid replicating fetch path
    from jobbot.models import JobPosting
    long_text = " ".join(["word"] * 150)
    long_job = JobPosting(
        id="working_nomads_x",
        source="working_nomads",
        title="t", company="c",
        url="https://www.workingnomads.com/job/go/x/",
        description=long_text,
    )
    assert scraper.fetch_detail(long_job) is long_job

    short_job = long_job.model_copy(update={"description": "only ten words ten words ten words ten words too short"})
    assert scraper.fetch_detail(short_job) is None


# --------------------------- nodesk ---------------------------------------


def test_nodesk_split_title_company():
    assert _split_title_company("Senior PM at Acme") == ("Senior PM", "Acme")
    assert _split_title_company("PM at Big Corp, Inc.") == ("PM", "Big Corp, Inc.")
    # ' at ' inside title — rpartition takes the LAST occurrence
    assert _split_title_company("Looking at Data at Stripe") == ("Looking at Data", "Stripe")
    assert _split_title_company("Bare title") == ("Bare title", "Unknown")


def test_nodesk_fetch_parses_feed_and_filters(monkeypatch):
    scraper = NoDeskScraper()

    fake_feed = SimpleNamespace(entries=[
        SimpleNamespace(
            link="https://nodesk.co/remote-jobs/acme-product-manager/",
            title="Product Manager at Acme",
            summary="Acme is hiring a remote PM.",
        ),
        SimpleNamespace(
            link="https://nodesk.co/remote-jobs/beta-ml-engineer/",
            title="ML Engineer at Beta",
            summary="Beta is hiring an MLE.",
        ),
        SimpleNamespace(  # malformed — no link, must be skipped
            link="",
            title="Bogus at Whatever",
            summary="",
        ),
    ])
    monkeypatch.setattr(
        "jobbot.scrapers.nodesk.feedparser.parse",
        lambda url: fake_feed,
    )

    all_jobs = scraper.fetch({"q": ""})
    assert [j.company for j in all_jobs] == ["Acme", "Beta"]
    assert all_jobs[0].title == "Product Manager"
    assert all_jobs[0].id.startswith("nodesk_")

    product_only = scraper.fetch({"q": "product"})
    assert [j.title for j in product_only] == ["Product Manager"]


# --------------------------- dailyremote ----------------------------------


_DR_LISTING_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Article","headline":"Header"},
  {"@type":"ItemList","numberOfItems":2,"itemListElement":[
    {"@type":"ListItem","position":1,"url":"https://dailyremote.com/remote-job/pm-1","name":"Product Manager at [Unlock with Premium]"},
    {"@type":"ListItem","position":2,"url":"https://dailyremote.com/remote-job/pm-2","name":"Senior Product Manager at [Unlock with Premium]"}
  ]}
]}
</script>
</head><body></body></html>
"""

_DR_DETAIL_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context":"http://schema.org",
  "@type":"JobPosting",
  "title":"Product Manager",
  "hiringOrganization":{"@type":"Organization","name":"micro1"},
  "description":"&lt;p&gt;""" + ("Lead PM work across a remote-first team. " * 30) + """&lt;/p&gt;"
}
</script>
</head><body></body></html>
"""


def test_dailyremote_fetch_parses_listing_json_ld(monkeypatch):
    scraper = DailyRemoteScraper()

    class R:
        text = _DR_LISTING_HTML
        status_code = 200
        def raise_for_status(self): pass

    monkeypatch.setattr("jobbot.scrapers.dailyremote.httpx.get", lambda *a, **kw: R())
    got = scraper.fetch({"q": "product manager"})
    assert [j.title for j in got] == ["Product Manager", "Senior Product Manager"]
    assert all(j.company == "Unknown" for j in got)  # filled by detail fetch
    assert got[0].url.host == "dailyremote.com"


def test_dailyremote_fetch_detail_extracts_company_and_description(monkeypatch):
    scraper = DailyRemoteScraper()

    class R:
        text = _DR_DETAIL_HTML
        status_code = 200

    monkeypatch.setattr("jobbot.scrapers.dailyremote.httpx.get", lambda *a, **kw: R())
    monkeypatch.setattr("jobbot.scrapers.dailyremote.time.sleep", lambda _s: None)

    from jobbot.models import JobPosting
    stub = JobPosting(
        id="dailyremote_x",
        source="dailyremote",
        title="Product Manager",
        company="Unknown",
        url="https://dailyremote.com/remote-job/pm-1",
        description="",
    )
    out = scraper.fetch_detail(stub)
    assert out is not None
    assert out.company == "micro1"
    assert "remote-first team" in out.description
    assert "&lt;" not in out.description  # entities unescaped


def test_dailyremote_fetch_detail_returns_none_when_body_too_short(monkeypatch):
    scraper = DailyRemoteScraper()

    short_html = """
    <html><head><script type="application/ld+json">
    {"@context":"http://schema.org","@type":"JobPosting","title":"x",
     "hiringOrganization":{"name":"y"},"description":"too short"}
    </script></head></html>
    """

    class R:
        text = short_html
        status_code = 200

    monkeypatch.setattr("jobbot.scrapers.dailyremote.httpx.get", lambda *a, **kw: R())
    monkeypatch.setattr("jobbot.scrapers.dailyremote.time.sleep", lambda _s: None)

    from jobbot.models import JobPosting
    stub = JobPosting(
        id="dailyremote_x",
        source="dailyremote",
        title="x", company="Unknown",
        url="https://dailyremote.com/remote-job/x",
        description="",
    )
    assert scraper.fetch_detail(stub) is None
