"""Deterministic job-description signal extraction (generators.jd_signals).

The signals feed the generation prompts' targeting rules and are verified
after generation by the QA gate, so their extraction must be precise:
a false directive pollutes a real cover letter, and a mirror term the
candidate cannot back would push the generator toward inventing.
"""
from __future__ import annotations

from jobbot.generators.jd_signals import (
    Directive,
    build_signals,
    detect_language,
    extract_directives,
    extract_mirror_terms,
    render_signal_block,
)
from jobbot.models import JobPosting
from jobbot.profile import Profile


def _profile() -> Profile:
    return Profile(
        personal={"full_name": "Philipp Hilbert"},
        preferences={},
        capabilities=[
            {"skill": "Product Discovery", "years": 8, "sources": []},
            {"skill": "Jira", "years": 10, "sources": []},
        ],
        domains=[{"name": "B2B SaaS", "depth": "deep", "years": 9}],
        nice_to_have_skills=["OKRs"],
    )


_BASE_CV = (
    "# Philipp Hilbert\n\n"
    "## What I can do\n\n"
    "**Delivery**, Jira, Confluence, GitLab\n"
    "**Product strategy**, roadmapping, stakeholder management\n"
)


def _job(description: str, title: str = "Senior Product Manager") -> JobPosting:
    return JobPosting(
        id="j1", source="test", title=title, company="Acme",
        url="https://example.com/j", description=description,
    )


# --- language ------------------------------------------------------------

def test_detects_german_by_function_words():
    text = ("Wir suchen eine erfahrene Person für unser Team. Deine Aufgaben "
            "sind vielfältig und die Anforderungen hoch. Bewerbung bitte mit "
            "Lebenslauf.")
    assert detect_language(text) == "de"


def test_detects_english_by_function_words():
    text = ("We are looking for an experienced person to join our team. "
            "Your responsibilities will span the product and the "
            "requirements are high.")
    assert detect_language(text) == "en"


def test_mixed_posting_with_english_title_but_german_body_is_german():
    text = ("Senior Product Manager\n"
            "Wir bieten dir ein starkes Team und spannende Aufgaben. Deine "
            "Erfahrung mit agilen Methoden ist für die Stelle wichtig, und "
            "wir freuen uns über eine Bewerbung mit Angabe der Kenntnisse.")
    assert detect_language(text) == "de"


# --- directives ----------------------------------------------------------

def test_extracts_trap_word_directive():
    ds = extract_directives(
        "To prove you read this posting, include the word 'banana' in your "
        "cover letter."
    )
    assert any(d.must_contain == "banana" for d in ds)


def test_extracts_start_with_directive():
    ds = extract_directives(
        'Please start your cover letter with "I read the whole posting".'
    )
    assert any(d.must_contain == "I read the whole posting" for d in ds)


def test_extracts_german_reference_code():
    ds = extract_directives(
        "Bitte geben Sie die Referenznummer: X7-2024 in Ihrer Bewerbung an."
    )
    assert any(d.must_contain == "X7-2024" for d in ds)


def test_extracts_question_without_checkable_token():
    ds = extract_directives(
        "In your cover letter, please tell us: what would you change about "
        "our onboarding after 10 minutes?"
    )
    assert any(d.must_contain is None and "onboarding" in d.instruction
               for d in ds)


def test_plain_posting_yields_no_directives():
    ds = extract_directives(
        "We are a growing B2B SaaS company. You will own the roadmap and "
        "work with reference customers across Europe."
    )
    assert ds == []


def test_duplicate_tokens_are_deduped():
    text = ("Include the word 'banana' in your letter. Really: include the "
            "word 'banana'.")
    ds = extract_directives(text)
    assert [d.must_contain for d in ds].count("banana") == 1


# --- mirror terms --------------------------------------------------------

def test_mirror_term_requires_presence_in_both_posting_and_candidate():
    jd = ("You will drive Product Discovery and work in Jira. Kubernetes "
          "experience is a plus.")
    terms = extract_mirror_terms(jd, _profile(), _BASE_CV)
    assert "Product Discovery" in terms
    assert "Jira" in terms
    # Kubernetes is in the posting but nowhere in the candidate's material.
    assert "Kubernetes" not in terms


def test_mirror_terms_use_the_postings_spelling():
    jd = "You know your way around JIRA and product discovery."
    terms = extract_mirror_terms(jd, _profile(), _BASE_CV)
    # The posting's casing is what recruiters search for.
    assert "JIRA" in terms
    assert "product discovery" in terms


def test_generic_single_words_are_not_mirror_terms():
    profile = Profile(
        personal={}, preferences={},
        capabilities=[{"skill": "Product", "years": 9, "sources": []}],
    )
    jd = "You will own the product end to end."
    assert extract_mirror_terms(jd, profile, "") == []


def test_base_cv_tool_lists_feed_the_vocabulary():
    jd = "Experience with Confluence and GitLab required."
    terms = extract_mirror_terms(jd, Profile(personal={}, preferences={}),
                                 _BASE_CV)
    assert "Confluence" in terms and "GitLab" in terms


# --- assembly ------------------------------------------------------------

def test_build_signals_and_render_block():
    job = _job(
        "We need OKRs discipline and Jira fluency. Include the word "
        "'banana' in your cover letter.",
    )
    signals = build_signals(job, _profile(), _BASE_CV)
    assert signals.language == "en"
    assert signals.posting_title == "Senior Product Manager"
    assert "Jira" in signals.mirror_terms and "OKRs" in signals.mirror_terms
    assert any(d.must_contain == "banana" for d in signals.directives)

    block = render_signal_block(signals)
    assert block.startswith("# Application signals")
    assert "posting_title: Senior Product Manager" in block
    assert "banana" in block


def test_render_block_marks_empty_sections_explicitly():
    signals = build_signals(_job("Plain description."),
                            Profile(personal={}, preferences={}), "")
    block = render_signal_block(signals)
    assert "mirror_terms: (none found)" in block
    assert "directives: (none found)" in block


def test_directive_dataclass_defaults():
    d = Directive(instruction="answer the question")
    assert d.must_contain is None
