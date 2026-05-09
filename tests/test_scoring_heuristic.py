from jobbot.models import JobPosting
from jobbot.profile import Profile
from jobbot.scoring import passes_heuristic


def _profile() -> Profile:
    return Profile(
        personal={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+49123456789",
            "location": "Berlin",
            "authorization": {"eu_citizen": True},
            "salary": {"currency": "EUR", "min": 80000, "max": 120000},
            "notice_period_weeks": 4,
        },
        preferences={"remote": True},
        must_have_skills=["product management"],
        nice_to_have_skills=[],
        deal_breakers={"keywords": ["intern"], "industries": [], "on_site_only": False},
        screener_defaults={},
    )


def test_intern_keyword_does_not_match_internal() -> None:
    job = JobPosting(
        id="j1",
        source="test",
        title="Senior Product Manager - Internal Tools",
        company="Acme",
        location="Berlin",
        url="https://example.com/jobs/1", # type: ignore
        description="Lead internal platform strategy and product management for core tooling.",
    )
    ok, _ = passes_heuristic(job, _profile())
    assert ok is True


def test_intern_keyword_matches_standalone_word() -> None:
    job = JobPosting(
        id="j2",
        source="test",
        title="Product Manager Intern",
        company="Acme",
        location="Berlin",
        url="https://example.com/jobs/2", # type: ignore
        description="Intern role in product management.",
    )
    ok, reason = passes_heuristic(job, _profile())
    assert ok is False
    assert "deal-breaker keyword: intern" in reason
