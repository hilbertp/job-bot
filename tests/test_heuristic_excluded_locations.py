"""Excluded-location gate: drop no-go on-site roles before the LLM call.

Runs 342-345 spent roughly 127 detail fetches and scoring calls per sweep on
Indian on-site postings after the Gulf sources went live. The candidate will
not relocate to India or the Philippines, but WILL take a fully remote role
advertised from anywhere, so the gate keys on the posting's location and
exempts explicit full-remote listings.
"""
from __future__ import annotations

import pytest

from jobbot.models import JobPosting
from jobbot.profile import Profile
from jobbot.scoring import passes_heuristic

_EXCLUDED = ["India", "Bengaluru", "Mumbai", "Philippines", "Taguig"]


def _profile(**prefs) -> Profile:
    base = {
        "remote": True,
        "excluded_locations": _EXCLUDED,
        "on_site_ok_locations": ["Dubai", "Abu Dhabi"],
    }
    base.update(prefs)
    return Profile(
        personal={"full_name": "T", "email": "t@example.com"},
        preferences=base,
        must_have_skills=["product"],
    )


def _job(location: str | None, body: str = "We need a product manager. " * 30) -> JobPosting:
    return JobPosting(
        id="x_1", source="talentmate", title="Product Manager", company="Acme",
        location=location, url="https://example.com/j/1",
        apply_url="https://example.com/j/1", description=body,
    )


@pytest.mark.parametrize("location", [
    "Bengaluru, Karnataka, India",
    "Mumbai",
    "India",
    "Taguig National Capital Region",
])
def test_onsite_role_in_excluded_location_is_dropped(location):
    ok, reason = passes_heuristic(_job(location), _profile())
    assert ok is False
    assert "excluded location" in reason


@pytest.mark.parametrize("location", [
    "Dubai, United Arab Emirates",
    "Abu Dhabi",
    "Berlin, Germany",
    "Remote, EU",
])
def test_wanted_locations_pass(location):
    ok, reason = passes_heuristic(_job(location), _profile())
    assert ok is True, reason


@pytest.mark.parametrize("phrase", [
    "This is a fully remote position.",
    "100% remote role, work from anywhere.",
    "We are remote-first.",
    "Work from anywhere in the world.",
])
def test_fully_remote_rescues_an_excluded_location(phrase):
    body = phrase + " Product manager wanted. " * 20
    ok, reason = passes_heuristic(_job("Bengaluru, India", body), _profile())
    assert ok is True, reason


def test_hybrid_does_not_rescue_an_excluded_location():
    """Hybrid means commuting distance, so it is still a relocation."""
    body = "Hybrid role, partly remote, 3 days in our Bengaluru office. " * 8
    ok, reason = passes_heuristic(_job("Bengaluru, India", body), _profile())
    assert ok is False
    assert "excluded location" in reason


def test_bare_remote_mention_does_not_rescue():
    """"remote team" / "remote-friendly" is not an offer of full remote."""
    body = "You will lead a remote team across our Mumbai and Pune offices. " * 8
    ok, _ = passes_heuristic(_job("Mumbai", body), _profile())
    assert ok is False


def test_body_mentioning_an_excluded_city_does_not_drop_a_gulf_role():
    """The gate reads the location field only: a Dubai role that mentions a
    Bengaluru dev team must survive."""
    body = "Product manager in Dubai working with our Bengaluru engineering team. " * 8
    ok, reason = passes_heuristic(_job("Dubai, United Arab Emirates", body), _profile())
    assert ok is True, reason


def test_missing_location_is_not_penalised():
    ok, reason = passes_heuristic(_job(None), _profile())
    assert ok is True, reason


def test_gate_is_inert_without_configured_exclusions():
    profile = _profile(excluded_locations=[])
    ok, reason = passes_heuristic(_job("Bengaluru, India"), profile)
    assert ok is True, reason
