"""builtin.com parsing: cards, paging, title filter, JSON-LD and the visible fallback.

Mocks httpx at the boundary, so no network. Fixtures mirror the real markup
captured 2026-09-17: cards are `div[data-id="job-card"]`, the employer sits in
`a[data-id="company-title"]`, the detail page carries a JobPosting inside a
JSON-LD `@graph`, and "The Role" is a `div.bg-midnight` banner followed by
the body box.
"""
from __future__ import annotations

import pytest

from jobbot.models import JobPosting
from jobbot.scrapers.base import ListingGone, stable_id
from jobbot.scrapers.builtin import BuiltInScraper

_CARD = """
<div id="job-card-{id}" data-id="job-card" class="job-bounded-responsive bg-white">
  <div class="left-side-tile-item-2">
    <a href="/company/{slug}" data-id="company-title" data-builtin-track-job-id="{id}"><span>{company}</span></a>
  </div>
  <div class="left-side-tile-item-3"><h2>
    <a href="/job/{slug}/{id}" data-id="job-card-title" data-alias="/job/{slug}/{id}"
       data-builtin-track-job-id="{id}" class="card-alias-after-overlay">{title}</a></h2></div>
  <span class="fs-xs fw-bold"><i class="fa-regular fa-clock fs-xs"></i>{ago}</span>
  <span class="font-barlow text-gray-04">Remote</span>
  <span class="font-barlow text-gray-03">27 Locations</span>
</div>
"""


def _card(id: int, title: str, company: str = "Growe Talents", ago: str = "6 Days Ago") -> str:
    return _CARD.format(id=id, slug="product-manager", title=title, company=company, ago=ago)


def _page(cards: list[str]) -> str:
    return '<html><body><div id="jobs-list">' + "".join(cards) + "</div></body></html>"


_JSONLD_DETAIL = """
<html><head>
<script type="application/ld&#x2B;json">
{{"@context":"https://schema.org","@graph":[
 {{"@type":"JobPosting","title":"Product Manager",
   "description":"<b>About the role</b><ul><li><p>{body}</p></li></ul>",
   "datePosted":"2026-09-15","jobLocationType":"TELECOMMUTE",
   "applicantLocationRequirements":{countries},
   "hiringOrganization":{{"@type":"Organization","name":"Growe Talents"}}}},
 {{"@type":"BreadcrumbList"}}]}}
</script></head>
<body><div class="mb-sm">Posted 2 Days Ago</div>
<a href="/company/growe-talents">Growe Talents</a>
<div class="bg-midnight">The Role</div><div class="bg-white">visible copy</div>
</body></html>
"""

_VISIBLE_DETAIL = """
<html><body>
<div class="mb-sm">Posted 3 Hours Ago</div>
<a href="/company/pencil"><img alt="Pencil Logo"></a>
<a href="/company/pencil">Pencil</a>
<div class="col-12 col-lg-6">
  <div class="bg-midnight text-white">The Role</div>
  <div class="bg-white rounded-3"><div class="mb-sm">{body}</div>
    <div class="cursor-pointer">Read Full Description</div></div>
</div>
<div class="col-12 col-lg-6">
  <a aria-label="Sign up to apply"><span>Sign up to apply</span></a>
  <div class="fs-md fw-bold">Apply Instructions</div>
  <div class="fs-sm">Send resume to jobs@example.com</div>
</div>
</body></html>
"""


class _Resp:
    def __init__(self, text: str, status_code: int = 200,
                 url: str = "https://builtin.com/job/product-manager/11227631"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture()
def scraper():
    return BuiltInScraper()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("jobbot.scrapers.builtin.time.sleep", lambda s: None)


def _stub_job() -> JobPosting:
    url = "https://builtin.com/job/product-manager/11227631"
    return JobPosting(id=stable_id("builtin", url), source="builtin",
                      title="Product Manager", company="Growe Talents",
                      location="United States (Remote)", url=url, apply_url=url)


def test_fetch_parses_cards_and_pages(monkeypatch, scraper):
    pages = {
        1: _page([_card(11227631, "Product Manager", ago="30 Minutes Ago"),
                  _card(11225052, "Product Manager - Media - Remote", company="Pencil")]),
        2: _page([_card(11130800, "Senior Product Manager", company="Nebius")]),
        3: _page([]),
    }
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=None):
        calls.append((url, dict(params)))
        return _Resp(pages[params["page"]])

    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product manager"})

    assert [j.title for j in jobs] == ["Product Manager", "Product Manager - Media - Remote",
                                       "Senior Product Manager"]
    assert [c[0] for c in calls] == ["https://builtin.com/jobs/remote/product"] * 3
    assert [c[1] for c in calls] == [{"page": p, "search": "product manager"} for p in (1, 2, 3)]
    first = jobs[0]
    assert first.id.startswith("builtin_")
    assert first.source == "builtin"
    assert str(first.url) == "https://builtin.com/job/product-manager/11227631"
    assert first.apply_url == first.url
    assert first.company == "Growe Talents"
    assert jobs[1].company == "Pencil"
    assert first.location == "United States (Remote)"
    assert first.tags == ["remote", "us"]
    assert first.posted_at is not None
    assert len({j.id for j in jobs}) == 3


def test_fetch_filters_titles_by_query(monkeypatch, scraper):
    """The Product Owner page returned Product Manager titles too (measured
    2026-09-17), so every needle of the query must sit in the title."""
    feed = _page([
        _card(1, "Product Owner, Subscriptions"), _card(2, "Product Owner"),
        _card(3, "Manager, Product Manager"), _card(4, "Product Manager - Data"),
        _card(5, "Head of Product"),
    ])
    calls = []

    def fake_get(url, params=None, **kw):
        calls.append((url, dict(params)))
        return _Resp(feed)

    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get", fake_get)

    owners = [j.title for j in scraper.fetch({"q": "product owner"})]
    assert owners == ["Product Owner, Subscriptions", "Product Owner"]
    # The owner query goes to the dedicated role page without a search param.
    assert calls[0][0] == "https://builtin.com/jobs/remote/product/search/product-owner"
    assert "search" not in calls[0][1]

    managers = [j.title for j in scraper.fetch({"q": "product manager"})]
    assert managers == ["Manager, Product Manager", "Product Manager - Data"]


def test_fetch_detail_reads_jsonld(monkeypatch, scraper):
    countries = '[{"@type":"Country","name":"GRC"},{"@type":"Country","name":"CYP"}]'
    monkeypatch.setattr(
        "jobbot.scrapers.builtin.httpx.get",
        lambda *a, **k: _Resp(_JSONLD_DETAIL.format(body="word " * 150, countries=countries)))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert len(out.description.split()) >= 100
    assert out.description.startswith("About the role")
    assert "<b>" not in out.description
    assert out.company == "Growe Talents"
    assert out.location == "Remote: GRC, CYP"
    assert (out.posted_at.year, out.posted_at.month, out.posted_at.day) == (2026, 9, 15)


def test_fetch_detail_single_country_and_default_location(monkeypatch, scraper):
    one = '[{"@type":"Country","name":"USA"}]'
    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp(_JSONLD_DETAIL.format(body="word " * 150, countries=one)))
    assert scraper.fetch_detail(_stub_job()).location == "United States (Remote)"

    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp(_JSONLD_DETAIL.format(body="word " * 150, countries="[]")))
    # Nothing stated: the card's default stays.
    assert scraper.fetch_detail(_stub_job()).location == "United States (Remote)"


def test_fetch_detail_falls_back_to_visible_role_section(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp(_VISIBLE_DETAIL.format(body="word " * 150)))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert len(out.description.split()) >= 100
    assert "Apply Instructions" not in out.description
    assert "Sign up to apply" not in out.description
    assert "Read Full Description" not in out.description
    assert out.company == "Pencil"
    assert out.location == "United States (Remote)"
    assert out.posted_at is not None


def test_fetch_detail_rejects_short_body(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp(_VISIBLE_DETAIL.format(body="too short")))
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_detail_404_raises_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp("<html>Not found</html>", status_code=404))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_detail_403_is_transient_not_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get",
                        lambda *a, **k: _Resp("<html>Forbidden</html>", status_code=403))
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_detail_redirect_to_index_raises_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr(
        "jobbot.scrapers.builtin.httpx.get",
        lambda *a, **k: _Resp(_VISIBLE_DETAIL.format(body="word " * 150),
                              url="https://builtin.com/jobs/remote/product"))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_survives_http_error(monkeypatch, scraper):
    def boom(*a, **k):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr("jobbot.scrapers.builtin.httpx.get", boom)
    assert scraper.fetch({"q": "product manager"}) == []
