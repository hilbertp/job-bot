from __future__ import annotations

from jobbot.models import JobPosting
from jobbot.scrapers.indeed import IndeedScraper


def _job(url: str, title: str) -> JobPosting:
    return JobPosting(
        id=f"indeed_{title.lower().replace(' ', '_')}",
        source="indeed",
        title=title,
        company="ACME",
        location="Berlin",
        url=url,
        apply_url=url,
        description="snippet",
    )


def test_indeed_uses_playwright_search(monkeypatch):
    scraper = IndeedScraper()
    search_jobs = [_job("https://de.indeed.com/viewjob?jk=abc", "Product Manager")]

    calls = []

    def _fake_playwright(host, params):
        calls.append((host, params))
        return search_jobs

    monkeypatch.setattr(scraper, "_fetch_playwright", _fake_playwright)

    got = scraper.fetch({"q": "product manager", "l": "Berlin", "country": "de"})
    assert got == search_jobs
    assert calls == [("de.indeed.com", {"q": "product manager", "l": "Berlin"})]


def test_indeed_uses_non_de_host_for_non_de_country(monkeypatch):
    scraper = IndeedScraper()
    search_jobs = [_job("https://www.indeed.com/viewjob?jk=def", "Product Owner")]

    calls = []

    def _fake_playwright(host, params):
        calls.append((host, params))
        return search_jobs

    monkeypatch.setattr(scraper, "_fetch_playwright", _fake_playwright)

    got = scraper.fetch({"q": "product owner", "l": "Berlin", "country": "us"})
    assert got == search_jobs
    assert calls == [("www.indeed.com", {"q": "product owner", "l": "Berlin"})]