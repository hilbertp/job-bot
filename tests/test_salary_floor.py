"""Salary-floor filter: drop postings whose STATED top pay is below the
candidate's floor before spending an LLM scoring call.

Real-world driver, 2026-05-18: a Berlin headless-CMS startup (Hygraph)
posted a strong-fit PM role at EUR 65,000 to 75,000. The user (a senior
international PM anchored at EUR 125k) called surfacing that "LAUGHABLE"
and asked to filter out anything under EUR 90k.

Design choices pinned here:
  - Use the TOP of the stated range. A range whose top clears the floor
    stays in play (negotiable); only filter when even the best case is
    below floor.
  - Currency + period normalised to EUR/year (approximate FX is fine,
    this is a coarse gate, not precise comp math).
  - No stated salary -> never filtered (we don't penalise unknown comp).
  - floor <= 0 disables the filter entirely.
"""
from __future__ import annotations

from jobbot.applier.salary import (
    annualised_top_eur, parse_posting_salary, posting_below_salary_floor,
)


# ---------------------------------------------------------------------------
# annualised_top_eur
# ---------------------------------------------------------------------------

def test_annualised_top_eur_yearly_eur():
    parsed = parse_posting_salary("EUR 65,000 - 75,000 per year")
    assert parsed is not None
    assert annualised_top_eur(parsed) == 75_000


def test_annualised_top_eur_monthly_annualises():
    parsed = parse_posting_salary("6.000 - 7.000 EUR per month")
    assert parsed is not None
    # top 7000/month * 12 = 84000
    assert annualised_top_eur(parsed) == 84_000


def test_annualised_top_eur_usd_converts_down():
    parsed = parse_posting_salary("$90,000 - $100,000 / year")
    assert parsed is not None
    # 100k USD * 0.92 = 92000 EUR
    assert abs(annualised_top_eur(parsed) - 92_000) <= 1


def test_annualised_top_eur_gbp_converts_up():
    parsed = parse_posting_salary("80,000 - 90,000 GBP per year")
    assert parsed is not None
    # 90k GBP * 1.17 = 105300 EUR
    assert abs(annualised_top_eur(parsed) - 105_300) <= 1


# ---------------------------------------------------------------------------
# posting_below_salary_floor
# ---------------------------------------------------------------------------

def test_hygraph_65_75k_is_below_90k_floor():
    """The driving case: EUR 65k-75k must be filtered at a 90k floor."""
    below, reason = posting_below_salary_floor(
        "Compensation: EUR 65,000 - 75,000 per year", 90_000,
    )
    assert below is True
    assert "salary_below_floor" in reason
    assert "75000" in reason


def test_range_top_above_floor_is_kept():
    """EUR 80k-100k tops out above the floor -> negotiable, keep it."""
    below, _ = posting_below_salary_floor(
        "Salary band: 80,000 - 100,000 EUR / year", 90_000,
    )
    assert below is False


def test_exactly_at_floor_is_kept():
    """Top exactly at floor is not 'below' floor."""
    below, _ = posting_below_salary_floor(
        "We offer 85,000 - 90,000 EUR per year", 90_000,
    )
    assert below is False


def test_no_stated_salary_is_never_filtered():
    """Most postings state no salary; those must pass through untouched."""
    below, reason = posting_below_salary_floor(
        "We are looking for a Senior Product Manager to own our roadmap. "
        "Great team, remote-first, learning budget.", 90_000,
    )
    assert below is False
    assert reason == ""


def test_floor_zero_disables_filter():
    """floor <= 0 means the filter is off, even a tiny salary passes."""
    below, _ = posting_below_salary_floor(
        "Salary: EUR 30,000 - 40,000 per year", 0,
    )
    assert below is False


def test_usd_role_just_under_floor_is_filtered():
    """$90k-95k tops out at ~87k EUR, below a 90k EUR floor -> filtered."""
    below, reason = posting_below_salary_floor(
        "Pay range: $90,000 - $95,000 annually", 90_000,
    )
    # 95000 * 0.92 = 87400 EUR < 90000
    assert below is True
    assert "salary_below_floor" in reason


def test_gbp_role_above_floor_is_kept():
    """GBP 85k tops at ~99k EUR -> above a 90k EUR floor, keep it."""
    below, _ = posting_below_salary_floor(
        "Salary: 75,000 - 85,000 GBP per year", 90_000,
    )
    assert below is False
