"""wellfound.com parsing: the __NEXT_DATA__ Apollo cache, client-side title
filtering, the JSON-LD detail page and the 30-day freshness rule.

Mocks httpx at the boundary, so no network. Fixtures mirror the real shapes
captured 2026-09-17 (jobs under "JobListingSearchResult:<id>", the company
only on "StartupResult:<id>", the header text "Posted:3 years ago").
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from jobbot.models import JobPosting
from jobbot.scrapers.base import ListingGone, stable_id
from jobbot.scrapers.wellfound import WellfoundScraper

# The site writes salary ranges with an en-dash; the scraper must hand out hyphens.
_EN_DASH = chr(0x2013)


def _epoch(days_ago: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days_ago)).timestamp())


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _list_page(jobs: list[dict], startups: list[dict] = ()) -> str:
    cache: dict = {"ROOT_QUERY": {}}
    for j in jobs:
        cache[f"JobListingSearchResult:{j['id']}"] = {
            "__typename": "JobListingSearchResult", "remote": True, "jobType": "full-time",
            "locationNames": [], "compensation": "", "description": "Short teaser.",
            "liveStartAt": _epoch(2), **j,
        }
    for s in startups:
        cache[f"StartupResult:{s['id']}"] = {
            "__typename": "StartupResult", "id": s["id"], "name": s["name"],
            "highlightedJobListings": [
                {"__ref": f"JobListingSearchResult:{jid}"} for jid in s["jobs"]],
        }
    data = {"props": {"pageProps": {"apolloState": {"data": cache}}}}
    anchors = "".join(f'<a href="/jobs/{j["id"]}-{j["slug"]}">{j["title"]}</a>' for j in jobs)
    return (f"<html><body>{anchors}"
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
            "</body></html>")


def _detail_page(date_posted: str | None, body_words: int = 150,
                 posted_text: str = "today") -> str:
    ld = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": "Product Manager",
        "hiringOrganization": {"@type": "Organization", "name": "Button"},
        "description": "<p>" + "word " * body_words + "</p>",
        "jobLocationType": "TELECOMMUTE",
        "jobLocation": [{"@type": "Place", "address": {
            "@type": "PostalAddress", "addressCountry": "United States"}}],
        "baseSalary": {"@type": "MonetaryAmount", "currency": "USD", "value": {
            "@type": "QuantitativeValue", "minValue": 158000.0, "maxValue": 200000.0}},
    }
    if date_posted:
        ld["datePosted"] = date_posted
    header = f"Product Manager $158k {_EN_DASH} $200k | Remote ( Everywhere ) | Full Time"
    return (f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head>'
            f"<body><div>{header}</div><div>Posted:{posted_text}</div>"
            "<p>We raised $475M last year.</p></body></html>")


_PM_JOBS = [
    {"id": "4675556", "slug": "growth-product-manager", "title": "Growth Product Manager",
     "compensation": f"$170k {_EN_DASH} $170k"},
    {"id": "4450695", "slug": "product-manager", "title": "Product Manager",
     "compensation": f"$228k {_EN_DASH} $264k", "locationNames": ["United States"]},
    {"id": "2934833", "slug": "onboarding-specialist", "title": "Onboarding Specialist"},
]
_STARTUPS = [
    {"id": "781135", "name": "YipitData", "jobs": ["4675556"]},
    {"id": "2", "name": "Check", "jobs": ["4450695", "2934833"]},
]


class _Resp:
    def __init__(self, text: str, status_code: int = 200,
                 url: str = "https://wellfound.com/jobs/1-x"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("jobbot.scrapers.wellfound.time.sleep", lambda s: None)


@pytest.fixture()
def scraper():
    return WellfoundScraper()


def _stub_job(job_id="2644195", slug="product-manager"):
    url = f"https://wellfound.com/jobs/{job_id}-{slug}"
    return JobPosting(id=stable_id("wellfound", url), source="wellfound",
                      title="Product Manager", company="Unknown", location="Remote",
                      url=url, apply_url=url, description="", tags=["remote", "startup"])


def test_fetch_parses_next_data_into_postings(monkeypatch, scraper):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(_list_page(_PM_JOBS, _STARTUPS))

    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product manager"})

    assert calls == ["https://wellfound.com/role/r/product-manager"]
    # The sibling role of the same startup is not a product job.
    assert [j.title for j in jobs] == ["Growth Product Manager", "Product Manager"]
    first, second = jobs
    assert first.source == "wellfound"
    assert first.id.startswith("wellfound_")
    assert str(first.url) == "https://wellfound.com/jobs/4675556-growth-product-manager"
    assert first.apply_url == first.url
    assert first.company == "YipitData"
    assert second.company == "Check"
    assert first.location == "Remote"
    assert second.location == "United States"
    assert first.posted_at is not None
    assert "remote" in first.tags and "startup" in first.tags
    assert "salary: $228k - $264k" in second.tags
    assert not any(_EN_DASH in t for t in second.tags)
    assert len({j.id for j in jobs}) == 2


def test_query_filters_titles_client_side(monkeypatch, scraper):
    jobs = _PM_JOBS + [
        {"id": "3270699", "slug": "product-owner", "title": "Product Owner"},
        {"id": "3852231", "slug": "senior-rev-ops-salesforce-product-owner",
         "title": "Senior Rev Ops Salesforce Product Owner"},
    ]
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(_list_page(jobs, _STARTUPS))

    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get", fake_get)
    titles = [j.title for j in scraper.fetch({"q": "product owner"})]

    assert calls == ["https://wellfound.com/role/r/product-owner"]
    assert titles == ["Product Owner", "Senior Rev Ops Salesforce Product Owner"]


def test_fetch_skips_listings_older_than_30_days(monkeypatch, scraper):
    """liveStartAt equals the detail page's datePosted, so a three-year-old
    card never enters the queue (job 2644195, posted 2023-04-14, still
    served on 2026-09-17)."""
    jobs = [
        {"id": "2644195", "slug": "product-manager", "title": "Product Manager",
         "liveStartAt": _epoch(3 * 365)},
        {"id": "4722714", "slug": "product-manager-patient-engagement",
         "title": "Product Manager, Patient Engagement", "liveStartAt": _epoch(1)},
    ]
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp(_list_page(jobs)))
    got = scraper.fetch({"q": "product manager"})
    assert [j.title for j in got] == ["Product Manager, Patient Engagement"]


def test_fetch_falls_back_to_anchors_without_next_data(monkeypatch, scraper):
    html = ('<html><body><a href="/jobs/3310675-product-manager">x</a>'
            '<a href="/jobs/3310675-product-manager">x</a>'
            '<a href="/jobs/2934833-onboarding-specialist">y</a></body></html>')
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp(html))
    got = scraper.fetch({"q": "product manager"})
    assert [str(j.url) for j in got] == ["https://wellfound.com/jobs/3310675-product-manager"]
    assert got[0].title == "Product Manager"


def test_fetch_403_returns_empty_without_raising(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp("<html>Forbidden</html>", status_code=403))
    assert scraper.fetch({"q": "product manager"}) == []


def test_fetch_survives_transport_error(monkeypatch, scraper):
    def boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get", boom)
    assert scraper.fetch({"q": "product manager"}) == []


def test_fetch_detail_fresh_fills_fields(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp(_detail_page(_iso(2))))
    out = scraper.fetch_detail(_stub_job())

    assert out is not None
    assert len(out.description.split()) >= 100
    assert out.company == "Button"
    assert out.posted_at is not None
    assert (datetime.now(timezone.utc) - out.posted_at).days == 2
    assert out.location == "Remote (Everywhere)"
    assert "salary: $158k - $200k" in out.tags
    assert "remote" in out.tags and "startup" in out.tags
    assert not any(_EN_DASH in t for t in out.tags)


def test_fetch_detail_stale_date_posted_raises_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr(
        "jobbot.scrapers.wellfound.httpx.get",
        lambda url, **kw: _Resp(_detail_page("2023-04-14T19:00:42Z", posted_text="3 years ago")))
    with pytest.raises(ListingGone) as exc:
        scraper.fetch_detail(_stub_job())
    assert exc.value.reason == "posted more than 30 days ago"


def test_fetch_detail_stale_header_text_without_date_posted(monkeypatch, scraper):
    """No datePosted in the JSON-LD: the "Posted:N months/years ago" header is
    the fallback, and months or years mean gone."""
    for text in ("3 years ago", "2 months ago", "1 month ago"):
        page = _detail_page(None, posted_text=text)
        monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                            lambda url, _page=page, **kw: _Resp(_page))
        with pytest.raises(ListingGone):
            scraper.fetch_detail(_stub_job())
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp(_detail_page(None, posted_text="5 days ago")))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert (datetime.now(timezone.utc) - out.posted_at).days == 5


def test_fetch_detail_404_raises_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp("<html>not found</html>", status_code=404))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_detail_403_and_cloudflare_return_none(monkeypatch, scraper):
    """A block is not a verdict on the posting: None, never ListingGone."""
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp("<html>Forbidden</html>", status_code=403))
    assert scraper.fetch_detail(_stub_job()) is None
    monkeypatch.setattr(
        "jobbot.scrapers.wellfound.httpx.get",
        lambda url, **kw: _Resp("<html><title>Just a moment...</title></html>"))
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_detail_rejects_short_body(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.wellfound.httpx.get",
                        lambda url, **kw: _Resp(_detail_page(_iso(1), body_words=20)))
    assert scraper.fetch_detail(_stub_job()) is None
