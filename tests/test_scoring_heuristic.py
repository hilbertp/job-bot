from pathlib import Path
from types import SimpleNamespace

import pytest

from jobbot.config import Secrets
from jobbot.models import JobPosting
from jobbot.profile import Profile
from jobbot.scoring import (
    CannotScore, MIN_BODY_WORDS, PROMPT_PATH, _build_user_message,
    llm_score, llm_score_tailored, passes_heuristic,
)


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
        llm_score(job, _profile(), _secrets(), description_scraped=True)
    assert exc.value.reason.startswith("no_body")
    assert str(MIN_BODY_WORDS) in exc.value.reason


def test_llm_score_refuses_when_description_not_scraped() -> None:
    """FR-SCO-01: a long listing-card snippet is not a real body. Without an
    enrichment fetch (description_scraped=False), refuse — even if the
    snippet is over the word-count floor."""
    body = " ".join(["lead product"] * 250)  # well above MIN_BODY_WORDS
    job = JobPosting(
        id="snippet",
        source="test",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/snippet",  # type: ignore
        description=body,
    )
    with pytest.raises(CannotScore) as exc:
        llm_score(job, _profile(), _secrets(), description_scraped=False)
    assert exc.value.reason.startswith("no_body")
    assert "description_scraped" in exc.value.reason


def test_llm_score_refuses_when_primary_cv_missing(monkeypatch) -> None:
    """FR-SCO-01: if the PRIMARY_ corpus CV is missing, refuse — never silent
    fallback to a thinner profile file."""
    monkeypatch.setattr(
        "jobbot.scoring.load_primary_cv",
        lambda: (_ for _ in ()).throw(FileNotFoundError("no PRIMARY_ CV")),
    )

    body = " ".join(["lead product"] * 250)  # comfortably above MIN_BODY_WORDS
    job = JobPosting(
        id="nocv",
        source="test",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/nocv",  # type: ignore
        description=body,
    )
    with pytest.raises(CannotScore) as exc:
        llm_score(job, _profile(), _secrets(), description_scraped=True)
    assert exc.value.reason.startswith("no_primary_cv")


def test_user_message_has_five_sections_in_order() -> None:
    """FR-SCO-02: the user message ordering is part of the contract — assert it."""
    job = JobPosting(
        id="ordering",
        source="linkedin",
        title="Senior Product Manager",
        company="Acme",
        location="Berlin / Remote",
        url="https://example.com/jobs/ordering",  # type: ignore
        description="Job body text " * 100,
    )
    msg = _build_user_message(job, _profile(), base_cv="# Philipp Hilbert CV\n\nExperience: ...")

    headers = [
        "# Primary CV (source of truth)",
        "# Compiled profile (yaml)",
        "# Hard preferences (yaml)",
        "# Job description",
        "# Job metadata",
    ]
    positions = [msg.find(h) for h in headers]
    assert all(p != -1 for p in positions), f"missing section header(s): {positions}"
    assert positions == sorted(positions), f"sections out of order: {positions}"


def test_user_message_tailored_variant_swaps_cv_and_injects_cover_letter() -> None:
    """Stage-3 rescore: tailored CV replaces section 1's label, and a cover-
    letter section sits between hard preferences and the job description."""
    job = JobPosting(
        id="tailored-msg",
        source="linkedin",
        title="Senior PM",
        company="Acme",
        url="https://example.com/jobs/tailored-msg",  # type: ignore
        description="Job body " * 100,
    )
    tailored_cv = "# Tailored CV for Acme\n\nReordered bullets for this role."
    tailored_cl = "Dear Acme team,\n\nI'm excited..."

    msg = _build_user_message(
        job, _profile(), base_cv=tailored_cv,
        cv_section_label="Tailored CV (this application's CV)",
        extra_section=("Cover letter (tailored)", tailored_cl),
    )

    assert "# Tailored CV (this application's CV)" in msg
    assert "# Primary CV (source of truth)" not in msg
    assert "# Cover letter (tailored)" in msg

    # Cover letter sits between hard preferences and job description
    hp = msg.find("# Hard preferences (yaml)")
    cl = msg.find("# Cover letter (tailored)")
    jd = msg.find("# Job description")
    assert hp < cl < jd, f"cover letter section misplaced: hp={hp}, cl={cl}, jd={jd}"


def test_user_profile_facts_are_prompted_as_authoritative() -> None:
    """User-entered facts can enrich the profile even when the PRIMARY_ CV
    omitted them, without treating generated profile guesses as stronger
    than the CV."""
    fact = "Logistik Vertiefung im Master Studium an der TU Berlin."
    profile = _profile().model_copy(update={"user_facts": [fact]})
    job = JobPosting(
        id="profile-fact",
        source="dailyremote",
        title="Product Manager",
        company="Descartes",
        url="https://example.com/jobs/profile-fact",  # type: ignore
        description="Job body " * 100,
    )

    msg = _build_user_message(job, profile, base_cv="# CV\n\nProduct leadership.")
    prompt = PROMPT_PATH.read_text()

    assert "user_facts:" in msg
    assert fact in msg
    assert "Treat `user_facts` as authoritative user-provided facts" in prompt


def test_llm_score_tailored_refuses_empty_inputs() -> None:
    """The rescore is meaningless without both tailored artifacts — refuse."""
    job = JobPosting(
        id="empty-tailored",
        source="test",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/empty",  # type: ignore
        description="x " * 250,
    )
    with pytest.raises(CannotScore) as exc:
        llm_score_tailored(job, _profile(), _secrets(),
                           tailored_cv_md="", tailored_cover_letter_md="cl")
    assert exc.value.reason.startswith("no_tailored_cv")

    with pytest.raises(CannotScore) as exc:
        llm_score_tailored(job, _profile(), _secrets(),
                           tailored_cv_md="cv", tailored_cover_letter_md="   ")
    assert exc.value.reason.startswith("no_tailored_cl")


def test_initial_llm_score_uses_sonnet_primary_cv_and_full_scraped_description(
    monkeypatch,
) -> None:
    """Regression for the initial profile checker/scorer:
    - calls Sonnet, not Haiku;
    - uses the PRIMARY_ CV corpus text;
    - sends the full enriched job description under the cap."""
    captured: dict = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text='{"score": 88, "reason": "strong primary-profile fit"}',
                    )
                ]
            )

    class FakeAnthropic:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr("jobbot.scoring.Anthropic", FakeAnthropic)
    monkeypatch.setattr(
        "jobbot.scoring.load_primary_cv",
        lambda: "# PRIMARY PROFILE SENTINEL\n\nProduct leadership proof.",
    )

    sentinel = "FULL_DESCRIPTION_SENTINEL_AT_END"
    body = " ".join(["product management ownership"] * 220) + f" {sentinel}"
    job = JobPosting(
        id="initial-score",
        source="test",
        title="Senior Product Manager",
        company="Acme",
        url="https://example.com/jobs/initial-score",  # type: ignore
        description=body,
    )

    result = llm_score(job, _profile(), _secrets(), description_scraped=True)

    assert result.score == 88
    assert captured["api_key"] == "dummy"
    assert captured["model"] == "claude-sonnet-4-6"
    assert captured["max_tokens"] == 800

    user_message = captured["messages"][0]["content"]
    assert "# Primary CV (source of truth)" in user_message
    assert "PRIMARY PROFILE SENTINEL" in user_message
    assert "# Job description" in user_message
    assert sentinel in user_message


def test_score_prompt_does_not_over_penalize_transferable_pm_domain_gaps() -> None:
    """Regression for the Descartes/SellerCloud case: a strong PM role fit
    must not be dragged below shortlist range solely because the exact
    e-commerce/OMS/WMS/logistics domain is absent from the CV. Behavior is
    encoded by the soft/hard domain-gap split in the calibration block."""
    prompt = PROMPT_PATH.read_text()

    assert "Domain gap, soft case" in prompt
    assert "treat the gap as manageable" in prompt
    assert "Transferable B2B SaaS" in prompt
    assert "Domain gap, hard case" in prompt
    assert "required, mandatory, core, central, essential" in prompt
    assert "should usually score 85+" in prompt
    assert "\"ideally\", \"preferred\", \"nice to have\", \"bonus\", or \"plus\"" in prompt
    assert "academic specialization or prior hands-on work in a requested domain" in prompt


def test_score_prompt_treats_hybrid_plus_willing_to_relocate_as_compatible() -> None:
    """Regression for the Peter Park case: a senior PM role in Munich
    with a 3-days-office / 2-days-remote schedule was scored 62 because
    the model treated `preferences.on_site_ok: false` as a hard veto
    even though `willing_to_relocate: true`. The corrected calibration
    must pin three things:

      1. Hybrid is NOT incompatible when willing_to_relocate=true.
      2. Hybrid in Germany + EU-based candidate + willing_to_relocate
         should land the location axis in 70-90.
      3. on_site_ok=false is a remote-first preference, not a hybrid veto.

    If any of these three pins go missing, every German hybrid role
    in the shortlist becomes vulnerable to the same under-score.
    """
    prompt = PROMPT_PATH.read_text()

    assert "Location scoring (axis-level guidance)" in prompt
    assert "Do not treat hybrid as incompatible if the candidate is willing to relocate" in prompt
    assert "Germany/EU-based with willing_to_relocate=true" in prompt
    assert "location score should normally be 70–90" in prompt
    assert "severe penalties below 40 for location when the role is on-site-only" in prompt
    assert "on_site_ok: false" in prompt
    assert "preference for remote-first, NOT a veto on hybrid" in prompt
