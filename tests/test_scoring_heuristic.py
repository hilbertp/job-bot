import pytest

from jobbot.config import Secrets
from jobbot.models import JobPosting
from jobbot.profile import Profile
from jobbot.scoring import CannotScore, MIN_BODY_WORDS, llm_score, passes_heuristic


def _profile(deal_breaker_keywords: list[str] | None = None) -> Profile:
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
        deal_breakers={
            "keywords": deal_breaker_keywords if deal_breaker_keywords is not None else ["intern"],
            "industries": [],
            "on_site_only": False,
        },
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


def test_seniority_keyword_in_body_ignored_when_title_is_senior() -> None:
    """Hiring contact named 'Junior Team Lead' must not filter a Senior posting."""
    job = JobPosting(
        id="hero",
        source="test",
        title="Senior Product Manager (w/m/d)",
        company="HERO",
        location="Berlin",
        url="https://example.com/jobs/hero", # type: ignore
        description=(
            "Lead product management. Contacts: Janek (Junior Team Lead Product "
            "Management) and Marcel (Senior Team Lead Product Management)."
        ),
    )
    ok, _ = passes_heuristic(job, _profile(deal_breaker_keywords=["junior"]))
    assert ok is True


def test_seniority_keyword_in_title_still_filters_even_with_senior_word() -> None:
    """A Junior Team Lead posting (title contains both junior and lead) is still junior."""
    job = JobPosting(
        id="jr-lead",
        source="test",
        title="Junior Team Lead Product Management",
        company="Acme",
        location="Berlin",
        url="https://example.com/jobs/jr-lead", # type: ignore
        description="Product management role.",
    )
    ok, reason = passes_heuristic(job, _profile(deal_breaker_keywords=["junior"]))
    assert ok is False
    assert "junior" in reason


def test_seniority_keyword_in_body_still_filters_when_title_is_neutral() -> None:
    """Body-only seniority hits still apply when the title doesn't signal senior+.
    Also guards against the body being scanned non-lowercased (case bug)."""
    job = JobPosting(
        id="neutral",
        source="test",
        title="Product Manager (m/w/d)",
        company="Acme",
        location="Berlin",
        url="https://example.com/jobs/neutral", # type: ignore
        description="Junior position, 0–2 years of product management experience.",
    )
    ok, reason = passes_heuristic(job, _profile(deal_breaker_keywords=["junior"]))
    assert ok is False
    assert "junior" in reason


def _secrets() -> Secrets:
    return Secrets(
        anthropic_api_key="dummy",
        gmail_address="x@example.com",
        gmail_app_password="x",
        notify_to="x@example.com",
    )


def test_llm_score_refuses_short_body() -> None:
    """FR-SCO-01: a thin body must not be scored. The LLM is never called."""
    job = JobPosting(
        id="short",
        source="test",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/short",  # type: ignore
        description="Lead product. " * 5,  # well below MIN_BODY_WORDS
    )
    with pytest.raises(CannotScore) as exc:
        llm_score(job, _profile(), _secrets())
    assert exc.value.reason.startswith("no_body")
    assert str(MIN_BODY_WORDS) in exc.value.reason
