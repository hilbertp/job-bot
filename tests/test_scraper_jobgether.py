"""jobgether.com parsing: the 410-with-body list page, title filtering, the
JSON-LD offer page, and the rate-limit / gone verdicts.

Mocks httpx at the boundary, so no network. Fixtures mirror what was measured
2026-09-17: the list page answers 410 but still links every offer as
/offer/<24-hex>-<slug>, the offer page carries one JSON-LD JobPosting and an
ATS link tagged utm_source=Jobgether, and a bare 9-byte 403 is the rate wall.
"""
from __future__ import annotations

import pytest

from jobbot.models import JobPosting
from jobbot.scrapers.base import ListingGone, stable_id
from jobbot.scrapers.jobgether import JobgetherScraper

_ID_A = "6aa8ca17b563ea142eaba83d"
_ID_B = "5bb7ca17b563ea142eaba84e"
_ID_C = "4cc6ca17b563ea142eaba85f"

_LINK = '<div class="card"><a href="/offer/{id}-{slug}"><h3>{title}</h3><span>Acme</span></a></div>'


def _list_page(rows: list[tuple[str, str, str]]) -> str:
    body = "".join(_LINK.format(id=i, slug=s, title=t) for i, s, t in rows)
    return f"<html><body><a href='/remote-jobs'>All jobs</a>{body}</body></html>"


_DETAIL = """
<html><head>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"JobPosting",
 "title":"Principal Product Manager - Personal Loans Growth",
 "description":"<p>{body}</p>",
 "hiringOrganization":{{"@type":"Organization","name":"Upgrade, Inc."}},
 "datePosted":"Tue Sep 15 2026 04:31:19 GMT+0000 (Coordinated Universal Time)",
 "jobLocation":[{{"@type":"Place","address":{{"@type":"PostalAddress","addressCountry":"US"}}}}]}}
</script></head>
<body>
<h3>Key facts</h3>
<ul>{facts}<li><span class="font-semibold">Full time</span></li>
<li><span class="font-semibold">Senior (5-10 years)</span></li></ul>
<a href="https://www.linkedin.com/company/upgrade">LinkedIn</a>
<a href="{apply}">APPLY</a>
</body></html>
"""
# Mirrors the live "Key facts" markup: a label span, then one link per state.
_FACTS = ('<li><div><span class="text-muted-foreground">Remote from: </span> '
          '<a href="/remote-jobs/california-usa">California (USA)</a><span>, </span>'
          '<a href="/remote-jobs/delaware-usa">Delaware (USA)</a></div></li>')
_APPLY = ("https://job-boards.greenhouse.io/upgrade/jobs/4733842005"
          "?utm_source=Jobgether&utm_medium=referral&utm_campaign=feed")


def _detail(body: str = "word " * 150, facts: str = _FACTS, apply: str = _APPLY) -> str:
    return _DETAIL.format(body=body, facts=facts, apply=apply)


class _Resp:
    def __init__(self, text: str, status_code: int = 200, url: str | None = None):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        return None


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("jobbot.scrapers.jobgether.time.sleep", lambda s: None)


@pytest.fixture()
def scraper():
    return JobgetherScraper()


def _stub_job(offer_id: str = _ID_A) -> JobPosting:
    url = f"https://jobgether.com/offer/{offer_id}-principal-product-manager---personal-loans-growth"
    return JobPosting(id=stable_id("jobgether", url), source="jobgether",
                      title="Principal Product Manager - Personal Loans Growth",
                      company="Jobgether (see detail)", location="Remote",
                      url=url, apply_url=url, description="", tags=["remote"])


def test_fetch_parses_410_list_page_into_postings(monkeypatch, scraper):
    """The list page answers 410 with a full body; raise_for_status would
    discard it. One request, no detail fetches, one row per offer id."""
    calls = []
    page = _list_page([
        (_ID_A, "principal-product-manager---personal-loans-growth",
         "Principal Product Manager - Personal Loans Growth"),
        (_ID_B, "senior-product-manager-payments", "Senior Product Manager, Payments"),
        (_ID_A, "principal-product-manager---personal-loans-growth",
         "Principal Product Manager - Personal Loans Growth"),  # linked twice
    ])

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(page, status_code=410)

    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get", fake_get)
    jobs = scraper.fetch({"q": "product manager"})

    assert calls == ["https://jobgether.com/remote-jobs/product-manager"]
    assert [j.title for j in jobs] == [
        "Principal Product Manager - Personal Loans Growth",
        "Senior Product Manager, Payments",
    ]
    first = jobs[0]
    assert first.source == "jobgether"
    assert first.id.startswith("jobgether_")
    assert str(first.url) == (
        f"https://jobgether.com/offer/{_ID_A}-principal-product-manager---personal-loans-growth"
    )
    assert first.tags == ["remote"]
    assert first.company == "Jobgether (see detail)"
    assert len({j.id for j in jobs}) == 2


def test_fetch_filters_titles_by_query_client_side(monkeypatch, scraper):
    """Only the product-manager list is known to exist, so both queries read
    it and the keyword narrows the titles here."""
    page = _list_page([
        (_ID_A, "product-owner-platform", "Product Owner, Platform"),
        (_ID_B, "senior-product-manager", "Senior Product Manager"),
        (_ID_C, "data-engineer", "Data Engineer"),
    ])
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(page, status_code=200))

    assert [j.title for j in scraper.fetch({"q": "product owner"})] == ["Product Owner, Platform"]
    assert [j.title for j in scraper.fetch({"q": "product manager"})] == ["Senior Product Manager"]


def test_fetch_title_never_becomes_a_mashed_card_blob(monkeypatch, scraper):
    """Three anchor shapes: no text at all, an anchor wrapping a whole card
    without a heading, and plain title text. The slug is the title unless the
    anchor text is a heading or spells the slug exactly."""
    page = (
        f"<html><body>"
        f"<a href='/offer/{_ID_A}-principal-product-manager---growth'><img src='x.png'></a>"
        f"<a href='/offer/{_ID_B}-senior-product-manager'><p>Senior Product Manager</p>"
        f"<p>Acme Inc</p><p>Remote, USA</p></a>"
        f"<a href='/offer/{_ID_C}-product-manager-ai-platform'>Product Manager, AI Platform</a>"
        f"</body></html>"
    )
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(page, status_code=410))
    jobs = scraper.fetch({"q": "product manager"})
    assert [j.title for j in jobs] == [
        "Principal Product Manager - Growth",
        "Senior Product Manager",
        "Product Manager, AI Platform",
    ]


def test_fetch_detail_fills_from_jsonld_and_deutms_apply_link(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(_detail()))
    out = scraper.fetch_detail(_stub_job())

    assert out is not None
    assert len(out.description.split()) >= 100
    assert "<p>" not in out.description
    assert out.company == "Upgrade, Inc."
    # datePosted is a JavaScript Date.toString(), which parse_posted_at
    # cannot read; the module parses it itself.
    assert out.posted_at is not None
    assert (out.posted_at.year, out.posted_at.month, out.posted_at.day) == (2026, 9, 15)
    # Key facts name the states; JSON-LD only says "US", so the text wins.
    assert out.location == "California (USA), Delaware (USA)"
    assert str(out.apply_url) == "https://job-boards.greenhouse.io/upgrade/jobs/4733842005"
    # The offer page stays the canonical url; only apply_url points at the ATS.
    assert str(out.url).startswith("https://jobgether.com/offer/")


def test_fetch_detail_location_falls_back_to_jsonld_country(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(_detail(facts="")))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert out.location == "US"


def test_fetch_detail_recognises_percent_encoded_utm(monkeypatch, scraper):
    """The live page writes utm%5Fsource=Jobgether (underscore encoded)."""
    apply = ("https://job-boards.greenhouse.io/upgrade/jobs/4733842005"
             "?utm%5Fsource=Jobgether&utm%5Fcontent=6aa8ca17&utm%5Fcampaign=search")
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(_detail(apply=apply)))
    out = scraper.fetch_detail(_stub_job())
    assert out is not None
    assert str(out.apply_url) == "https://job-boards.greenhouse.io/upgrade/jobs/4733842005"


def test_403_on_list_returns_empty_without_raising(monkeypatch, scraper):
    """A bare 9-byte 403 is the rate wall: stop, log, hand back what we have."""
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp("Forbidden", status_code=403))
    assert scraper.fetch({"q": "product manager"}) == []


def test_403_on_detail_returns_none_not_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp("Forbidden", status_code=403))
    assert scraper.fetch_detail(_stub_job()) is None


@pytest.mark.parametrize("status", [404, 410])
def test_gone_status_on_detail_raises_listing_gone(monkeypatch, scraper, status):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp("", status_code=status))
    with pytest.raises(ListingGone) as exc:
        scraper.fetch_detail(_stub_job())
    assert str(status) in exc.value.reason


def test_redirect_to_index_on_detail_raises_listing_gone(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp("<html></html>", status_code=200,
                                                url="https://jobgether.com/remote-jobs"))
    with pytest.raises(ListingGone):
        scraper.fetch_detail(_stub_job())


def test_detail_without_jobposting_block_returns_none(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp("<html><body>" + "word " * 200 + "</body></html>"))
    assert scraper.fetch_detail(_stub_job()) is None


def test_detail_rejects_short_body(monkeypatch, scraper):
    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get",
                        lambda url, **kw: _Resp(_detail(body="too short")))
    assert scraper.fetch_detail(_stub_job()) is None


def test_fetch_survives_transport_error(monkeypatch, scraper):
    def boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("jobbot.scrapers.jobgether.httpx.get", boom)
    assert scraper.fetch({"q": "product manager"}) == []
    assert scraper.fetch_detail(_stub_job()) is None
