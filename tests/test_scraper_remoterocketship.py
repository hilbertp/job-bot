"""remoterocketship.com parsing: the __NEXT_DATA__ list, the title filter, and
the detail page's three text sections.

Mocks httpx at the boundary, so no network. Fixtures mirror the real JSON
captured 2026-09-17 (list at pageProps.initialJobOpenings, detail at
pageProps.jobOpening, dead slug answers 404). There is no paging without a
login, so fetch makes exactly one request per query.
"""
from __future__ import annotations

import json

import pytest

from jobbot.models import JobPosting
from jobbot.scrapers.base import ListingGone, stable_id
from jobbot.scrapers.remoterocketship import RemoteRocketshipScraper


def _item(slug="product-manager-texas-remote-2", company="RealPage, Inc.",
          company_slug="realpage-inc", title="Senior Product Manager",
          category="Product Manager", countries=None, location="United States",
          salary="$94,700 - $161,300 per year"):
    return {
        "slug": slug,
        "roleTitle": title,
        "categorizedJobTitle": category,
        "company": {"name": company, "slug": company_slug},
        "url": f"https://jobs.ashbyhq.com/{company_slug}/{slug}",
        "created_at": "2026-09-17T06:12:00.423+00:00",
        "location": location,
        "locationCountries": countries,
        "locationType": "remote",
        "salaryRange": {"salaryHumanReadableText": salary} if salary else None,
        "jobDescriptionSummary": "Senior PM owning multifamily SaaS products",
        "twoLineJobDescriptionSummary": "Senior PM owning vision, roadmaps, and delivery.",
    }


def _next_page(props: dict) -> str:
    payload = json.dumps({"props": {"pageProps": props}})
    return ('<html><head></head><body><div id="__next"></div>'
            f'<script id="__NEXT_DATA__" type="application/json">{payload}</script>'
            "</body></html>")


def _list_page(items: list[dict]) -> str:
    return _next_page({"initialJobOpenings": items})


def _detail_page(opening: dict) -> str:
    return _next_page({"jobOpening": opening, "relatedJobs": []})


_DETAIL_URL = "https://www.remoterocketship.com/company/realpage-inc/jobs/product-manager-texas-remote-2/"


class _Resp:
    def __init__(self, text: str, status_code: int = 200, url: str = _DETAIL_URL):
        self.text = text
        self.status_code = status_code
        self.url = url

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


@pytest.fixture()
def scraper():
    return RemoteRocketshipScraper()


def _stub_job(url=_DETAIL_URL):
    return JobPosting(id=stable_id("remoterocketship", url), source="remoterocketship",
                      title="Senior Product Manager", company="RealPage, Inc.",
                      location="United States", url=url,
                      apply_url="https://jobs.ashbyhq.com/realpage-inc/x", description="")


def test_fetch_parses_next_data_list(monkeypatch, scraper):
    items = [
        _item(),
        _item(slug="product-manager-uzbekistan-remote", company="Bolder Apps",
              company_slug="bolder-apps", title="Product Manager",
              countries=["Uzbekistan", "Georgia", "Argentina"], location="Uzbekistan",
              salary=None),
    ]
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **kw: _Resp(_list_page(items)))

    jobs = scraper.fetch({"q": "product manager"})

    assert [j.title for j in jobs] == ["Senior Product Manager", "Product Manager"]
    first = jobs[0]
    assert first.source == "remoterocketship"
    assert first.id.startswith("remoterocketship_")
    assert first.company == "RealPage, Inc."
    # url is the board's own detail page, apply_url the employer's ATS link.
    assert str(first.url) == _DETAIL_URL
    assert str(first.apply_url).startswith("https://jobs.ashbyhq.com/realpage-inc/")
    assert first.location == "United States"
    assert first.posted_at is not None
    assert (first.posted_at.year, first.posted_at.month, first.posted_at.day) == (2026, 9, 17)
    assert "remote" in first.tags
    assert "salary: $94,700 - $161,300 per year" in first.tags
    assert first.description.startswith("Senior PM owning vision")
    # Second row: countries list wins over the single location, no salary tag.
    assert jobs[1].location == "Uzbekistan, Georgia, Argentina"
    assert jobs[1].tags == ["remote"]
    assert len({j.id for j in jobs}) == 2


def test_fetch_filters_titles_by_query(monkeypatch, scraper):
    items = [
        _item(slug="a", title="Senior Product Manager", category="Product Manager"),
        _item(slug="b", title="Head of Product", category="Product Manager"),
        _item(slug="c", title="Product Owner", category="Product Owner"),
        _item(slug="d", title="Frontend Engineer", category="Software Engineer"),
    ]
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **kw: _Resp(_list_page(items)))

    managers = [j.title for j in scraper.fetch({"q": "product manager"})]
    assert managers == ["Senior Product Manager", "Head of Product"]

    owners = [j.title for j in scraper.fetch({"q": "product owner"})]
    assert owners == ["Product Owner"]


def test_fetch_makes_one_request_to_the_query_slug(monkeypatch, scraper):
    """No paging without a login (measured 2026-09-17), so one request per
    query, to the slug page, with the cache-bypassing page=1."""
    calls = []

    def fake_get(url, params=None, **kw):
        calls.append((url, dict(params or {})))
        return _Resp(_list_page([_item(slug="po-1", title="Product Owner",
                                       category="Product Owner")]))

    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product owner"})

    assert len(jobs) == 1
    assert calls == [("https://www.remoterocketship.com/jobs/product-owner/", {"page": 1})]


def test_fetch_falls_back_to_worldwide_and_skips_bad_rows(monkeypatch, scraper):
    items = [
        _item(slug="w", countries=None, location=""),
        {"roleTitle": "No slug and no url", "company": {"name": "X"}},
    ]
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **kw: _Resp(_list_page(items)))
    jobs = scraper.fetch({"q": ""})
    assert [j.location for j in jobs] == ["Worldwide"]


def test_fetch_survives_http_error(monkeypatch, scraper):
    def boom(*a, **k):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get", boom)
    assert scraper.fetch({"q": "product manager"}) == []


def test_fetch_returns_empty_when_next_data_is_missing(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **kw: _Resp("<html><body>no script tag</body></html>"))
    assert scraper.fetch({"q": "product manager"}) == []


def _opening(desc_words=60, req_words=50, ben_words=20, deleted=None):
    return {
        "roleDescription": " ".join(["own"] * desc_words),
        "roleRequirements": " ".join(["need"] * req_words),
        "benefits": " ".join(["perk"] * ben_words),
        "dateDeleted": deleted,
    }


def test_fetch_detail_joins_sections_and_clears_floor(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp(_detail_page(_opening())))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert len(out.description.split()) >= 100
    assert out.description.startswith("Role:\n")
    assert "Requirements:\n" in out.description
    assert "Benefits:\n" in out.description
    assert out.title == "Senior Product Manager"


def test_fetch_detail_rejects_short_body(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp(_detail_page(_opening(30, 20, 5))))
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_detail_404_is_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp("<html>404</html>", status_code=404))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_detail_redirect_to_index_is_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp(_list_page([]),
                                              url="https://www.remoterocketship.com/jobs/product-manager/"))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_detail_date_deleted_is_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp(_detail_page(_opening(deleted="2026-09-10T00:00:00+00:00"))))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_fetch_detail_403_and_errors_are_transient(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp("<html>blocked</html>", status_code=403))
    assert scraper.fetch_detail(_stub_job()) is None

    def boom(*a, **k):
        raise RuntimeError("timeout")

    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get", boom)
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_detail_without_job_opening_is_transient(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.remoterocketship.httpx.get",
                        lambda *a, **k: _Resp("<html><body>no next data</body></html>"))
    assert scraper.fetch_detail(_stub_job()) is None
