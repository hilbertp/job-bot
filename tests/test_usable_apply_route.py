"""`usable_apply_route()` is the gate between the DB's raw apply_url /
apply_email and what the dashboard surfaces. It enforces the rule:

  *every Stage 3 row must show either a working canonical apply URL OR
  a real apply email — never a paywalled aggregator link.*

Per user feedback on 2026-05-15:
  *"when i click the link, and its behind a paywall, you have failed."*

These tests pin the four buckets the helper must classify into.
"""
from __future__ import annotations

from jobbot.state import is_paywalled_apply_url, usable_apply_route


# ---------------------------------------------------------------------------
# is_paywalled_apply_url — the paywall-domain test
# ---------------------------------------------------------------------------

def test_paywall_detected_dailyremote():
    assert is_paywalled_apply_url(
        "https://dailyremote.com/remote-job/product-manager-12345"
    ) is True


def test_paywall_detected_linkedin_country_subdomain():
    """LinkedIn URLs come in many subdomains (de.linkedin.com,
    uk.linkedin.com, www.linkedin.com). The substring match catches
    all of them."""
    assert is_paywalled_apply_url(
        "https://de.linkedin.com/jobs/view/product-owner-at-acme-12345"
    ) is True
    assert is_paywalled_apply_url(
        "https://www.linkedin.com/jobs/view/4412345"
    ) is True


def test_paywall_detected_xing():
    assert is_paywalled_apply_url(
        "https://www.xing.com/jobs/berlin-product-manager-12345"
    ) is True


def test_canonical_employer_url_not_paywalled():
    """Greenhouse, Recruitee, Lever, Workday, Personio, SmartRecruiters,
    company-own careers pages — none of these are paywalled."""
    assert is_paywalled_apply_url(
        "https://job-boards.greenhouse.io/backblaze/jobs/5210076008"
    ) is False
    assert is_paywalled_apply_url(
        "https://gtowizard.recruitee.com/o/product-manager-3"
    ) is False
    assert is_paywalled_apply_url(
        "https://jobs.lever.co/example/abc123"
    ) is False
    assert is_paywalled_apply_url(
        "https://xpate.jobs.personio.com/job/2633050"
    ) is False
    assert is_paywalled_apply_url(
        "https://procilongroup.scope-recruiting.de/?page=job&id=106044"
    ) is False
    assert is_paywalled_apply_url("https://careers.example.com/job/123") is False


def test_paywall_detector_handles_empty():
    assert is_paywalled_apply_url(None) is False
    assert is_paywalled_apply_url("") is False
    assert is_paywalled_apply_url("   ") is False


# ---------------------------------------------------------------------------
# usable_apply_route — the routing decision
# ---------------------------------------------------------------------------

def test_email_wins_over_url_when_both_present():
    """If both fields are populated, prefer the email channel —
    automatable + traceable. The URL is metadata."""
    kind, value = usable_apply_route(
        "careers@example.com",
        "https://example.com/jobs/123",
    )
    assert kind == "email"
    assert value == "careers@example.com"


def test_canonical_url_returns_url_route():
    kind, value = usable_apply_route(
        None, "https://job-boards.greenhouse.io/backblaze/jobs/5210076008"
    )
    assert kind == "url"
    assert value.endswith("5210076008")


def test_paywalled_url_alone_returns_missing():
    """The single most important assertion. dailyremote / linkedin /
    xing URLs are NOT valid apply routes; when that's all we have,
    the route is 'missing'."""
    for paywalled in (
        "https://dailyremote.com/remote-job/product-manager-1",
        "https://de.linkedin.com/jobs/view/product-owner-at-acme-12345",
        "https://www.xing.com/jobs/berlin-product-manager-12345",
    ):
        kind, reason = usable_apply_route(None, paywalled)
        assert kind == "missing", f"paywalled {paywalled!r} should be 'missing'"
        assert "paywalled" in reason.lower()


def test_paywalled_url_with_email_falls_back_to_email():
    """Even if the URL is paywalled, a real apply email is still
    usable — route through that."""
    kind, value = usable_apply_route(
        "careers@example.com",
        "https://dailyremote.com/remote-job/product-manager-1",
    )
    assert kind == "email"
    assert value == "careers@example.com"


def test_nothing_returns_missing():
    kind, reason = usable_apply_route(None, None)
    assert kind == "missing"
    assert "no apply_url" in reason.lower()


def test_empty_strings_return_missing():
    """Common DB state: apply_email='' rather than None. Should
    behave the same as None."""
    kind, reason = usable_apply_route("", "")
    assert kind == "missing"


def test_whitespace_only_email_treated_as_missing():
    kind, reason = usable_apply_route("   ", None)
    assert kind == "missing"
