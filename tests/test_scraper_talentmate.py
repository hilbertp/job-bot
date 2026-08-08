"""talentmate.com parsing: cards, pagination, and the JSON-LD employer name.

Mocks httpx at the boundary, so no network. Fixtures mirror the real markup
captured 2026-08-02 (cards are `div.job-details`, the employer only exists in
the detail page's schema.org block).
"""
from __future__ import annotations

import pytest

from jobbot.scrapers.talentmate import TalentmateScraper

_CARD = """
<td><div class="job-details"><div class="job-detail-wrapper">
  <div class="com-details">
    <a href="{url}" class="no-underline-onhover"><h3>{title}</h3></a>
    <div class="common">
      <div class="set"><span class="tm-building"></span><span>Talentmate</span></div>
      <div class="set"><span class="tm-location"></span><span>{loc}</span></div>
    </div>
    <div class="description"><p>Short teaser about the role.</p></div>
  </div>
  <div class="button-wrapper"><div class="buttons">
    <a href="{url}">View Job</a></div><p>Posted on {posted}</p></div>
</div></div></td>
"""


def _page(cards: list[str]) -> str:
    return "<html><body><table>" + "".join(cards) + "</table></body></html>"


_DETAIL = """
<html><head>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"JobPosting","title":"Product Manager",
 "hiringOrganization":{{"@type":"Organization","name":"ClearGrid"}},
 "datePosted":"07-08-2026"}}
</script></head>
<body><div class="Job-profile-content">{body}</div></body></html>
"""


class _Resp:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


@pytest.fixture()
def scraper():
    return TalentmateScraper()


def test_fetch_parses_cards_and_pages(monkeypatch, scraper):
    pages = {
        1: _page([_CARD.format(url="https://www.talentmate.com/jobs/uae/dubai/pm-voice-ai/2608-1",
                               title="Product Manager - Voice AI", loc="Dubai",
                               posted="07 Aug 2026")]),
        2: _page([_CARD.format(url="https://www.talentmate.com/jobs/uae/abu-dhabi/spm/2608-2",
                               title="Senior Product Manager", loc="Abu Dhabi",
                               posted="06 Aug 2026")]),
        3: _page([]),  # no cards -> stop paging
    }
    seen_params = []

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=None):
        seen_params.append(params)
        return _Resp(pages[params["page"]])

    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product manager"})

    assert [j.title for j in jobs] == ["Product Manager - Voice AI",
                                       "Senior Product Manager"]
    assert [p["search"] for p in seen_params] == ["product manager"] * 3
    first = jobs[0]
    assert first.source == "talentmate"
    assert first.location == "Dubai"
    assert str(first.url).endswith("/2608-1")
    assert first.posted_at is not None
    assert (first.posted_at.year, first.posted_at.month, first.posted_at.day) == (2026, 8, 7)
    # The portal names itself on every card; that must not become the company.
    assert first.company == "(see posting)"
    assert len({j.id for j in jobs}) == 2


def test_country_query_pins_the_path_and_makes_one_request(monkeypatch, scraper):
    """Unpinned search returned 127 Indian rows per 137 (measured), and the
    country path ignores &page, so it must be one request to /jobs/<country>
    with no page param."""
    calls = []

    def fake_get(url, params=None, **kw):
        calls.append((url, dict(params or {})))
        return _Resp(_page([_CARD.format(
            url="https://www.talentmate.com/jobs/uae/dubai/pm/2608-1",
            title="Product Manager", loc="Dubai", posted="07 Aug 2026")]))

    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product manager", "country": "uae"})

    assert len(calls) == 1, "country path ignores paging; one request only"
    url, params = calls[0]
    assert url == "https://www.talentmate.com/jobs/uae"
    assert params == {"search": "product manager"}
    assert "page" not in params
    assert len(jobs) == 1


def test_unpinned_query_still_pages(monkeypatch, scraper):
    calls = []
    monkeypatch.setattr(
        "jobbot.scrapers.talentmate.httpx.get",
        lambda url, params=None, **kw: (
            calls.append((url, dict(params or {}))),
            _Resp(_page([_CARD.format(
                url=f"https://www.talentmate.com/jobs/uae/dubai/pm/2608-{len(calls)}",
                title="Product Manager", loc="Dubai", posted="07 Aug 2026")])),
        )[1],
    )
    scraper.fetch({"q": "product manager"})
    assert [c[0] for c in calls] == ["https://www.talentmate.com/jobs"] * 3
    assert [c[1]["page"] for c in calls] == [1, 2, 3]


def test_duplicate_cards_are_deduped(monkeypatch, scraper):
    """Each posting is linked twice in the real markup (card + title)."""
    card = _CARD.format(url="https://www.talentmate.com/jobs/uae/dubai/pm/2608-9",
                        title="Product Manager", loc="Dubai", posted="01 Aug 2026")
    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get",
                        lambda *a, **k: _Resp(_page([card, card])))
    jobs = scraper.fetch({"q": "product manager"})
    assert len(jobs) == 1


def test_fetch_detail_fills_body_and_real_employer(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get",
                        lambda *a, **k: _Resp(_DETAIL.format(body="word " * 150)))
    job = _stub_job(scraper)
    out = scraper.fetch_detail(job)
    assert out is not None
    assert len(out.description.split()) >= 100
    # The employer only exists in the JSON-LD; without it every Gulf row
    # would stay anonymous on the dashboard.
    assert out.company == "ClearGrid"


def test_fetch_detail_rejects_short_body(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get",
                        lambda *a, **k: _Resp(_DETAIL.format(body="too short")))
    assert scraper.fetch_detail(_stub_job(scraper)) is None


def test_fetch_survives_http_error(monkeypatch, scraper):
    def boom(*a, **k):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr("jobbot.scrapers.talentmate.httpx.get", boom)
    assert scraper.fetch({"q": "product manager"}) == []


def _stub_job(scraper):
    from jobbot.models import JobPosting
    from jobbot.scrapers.base import stable_id
    url = "https://www.talentmate.com/jobs/uae/dubai/pm/2608-1"
    return JobPosting(id=stable_id("talentmate", url), source="talentmate",
                      title="Product Manager", company="(see posting)",
                      location="Dubai", url=url, apply_url=url, description="")
