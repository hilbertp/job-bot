"""Salary resolver: parse employer-stated range from the JD; otherwise
fall back to the candidate's profile anchor.

User feedback on 2026-05-15 after a 6666 EUR/month undershoot:
  *"we need a script to customize salary expectations: if they provide
   one themselves, use the lower end. if they don't provide apply with
   125k."*

These tests pin the parser against real-world JD wording I've seen
(Consensys, German postings with "EUR/year", monthly variants, etc.)
plus the resolver's fallback contract.
"""
from __future__ import annotations

from jobbot.applier.salary import (
    ApplySalary,
    ParsedSalary,
    apply_salary_for,
    parse_posting_salary,
)


# ---------------------------------------------------------------------------
# parse_posting_salary
# ---------------------------------------------------------------------------

def test_parses_dollar_K_range_consensys_style():
    """Real Consensys JD wording: 'The salary range is $166K to $208K.'"""
    text = "Compensation: The salary range is $166K to $208K depending on experience."
    p = parse_posting_salary(text)
    assert p == ParsedSalary(low=166_000, high=208_000, currency="USD", period="year")


def test_parses_dollar_K_range_en_dash():
    text = "Salary: $120K – $160K per year, plus equity."
    p = parse_posting_salary(text)
    assert p.low == 120_000 and p.high == 160_000
    assert p.currency == "USD" and p.period == "year"


def test_parses_euro_suffix_range_with_commas():
    text = "We offer a salary between 80,000 - 100,000 EUR / year, depending on seniority."
    p = parse_posting_salary(text)
    assert p.low == 80_000 and p.high == 100_000
    assert p.currency == "EUR" and p.period == "year"


def test_parses_euro_suffix_european_dot_thousands():
    """German postings often write 80.000 - 100.000 EUR."""
    text = "Gehalt: 80.000 - 100.000 EUR pro Jahr."
    p = parse_posting_salary(text)
    assert p.low == 80_000 and p.high == 100_000
    assert p.currency == "EUR"


def test_parses_currency_symbol_prefix_with_commas():
    text = "We pay €120,000 to €150,000 per year for this role."
    p = parse_posting_salary(text)
    assert p.low == 120_000 and p.high == 150_000
    assert p.currency == "EUR"


def test_parses_monthly_period_when_explicit():
    text = "Monthly compensation: €6,000 - €8,000 per month."
    p = parse_posting_salary(text)
    assert p.period == "month"
    assert p.low == 6_000 and p.high == 8_000


def test_parses_single_amount_when_no_range():
    """Postings that quote a single figure with 'per year' — treat as
    low==high so the resolver still has a number to anchor on."""
    text = "Base salary is $150,000 per year."
    p = parse_posting_salary(text)
    assert p.low == 150_000 and p.high == 150_000
    assert p.currency == "USD" and p.period == "year"


def test_returns_none_when_no_salary_mentioned():
    text = (
        "We are looking for a Senior Product Manager to join our team. "
        "Strong product judgment, comfort with data, and experience "
        "shipping consumer products required."
    )
    assert parse_posting_salary(text) is None


def test_returns_none_on_empty_input():
    assert parse_posting_salary("") is None
    assert parse_posting_salary(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# apply_salary_for — the resolver the adapters call
# ---------------------------------------------------------------------------

def test_prefers_employer_low_end_when_posting_states_range():
    """The Consensys case that triggered the feature: JD said $166K-$208K,
    we should anchor at the LOW END ($166K), not the candidate's 125k EUR."""
    text = "Salary range: $166K to $208K. We hire remotely."
    salary = apply_salary_for(text, profile_application_anchor_eur_year=125_000)
    assert salary.amount_per_year == 166_000
    assert salary.currency == "USD"
    assert salary.sourced_from == "posting"
    assert salary.amount_per_month == 13_833


def test_falls_back_to_profile_anchor_when_posting_silent():
    text = "We are hiring a remote PM. Strong product judgment required."
    salary = apply_salary_for(text, profile_application_anchor_eur_year=125_000)
    assert salary.amount_per_year == 125_000
    assert salary.currency == "EUR"
    assert salary.sourced_from == "profile_anchor"
    assert salary.amount_per_month == 10_417  # 125000 / 12 → 10416.67 → round


def test_monthly_form_field_helper():
    """Recruitee's pattern: the salary field is numeric-only and asks
    for monthly EUR. `.for_monthly_field()` returns the integer to type
    directly (no currency / period suffix)."""
    salary = apply_salary_for("", profile_application_anchor_eur_year=125_000)
    assert salary.for_monthly_field() == 10_417


def test_yearly_text_field_helper():
    """Greenhouse's pattern: free-text 'Desired Salary' field. We emit
    a string with currency + period suffix so a recruiter reading the
    submission can interpret the unit unambiguously."""
    salary = apply_salary_for(
        "Salary: $166K-$208K", profile_application_anchor_eur_year=125_000,
    )
    assert salary.for_yearly_field() == "166000 USD/year"


def test_monthly_posting_is_annualised_for_yearly_anchor():
    """If the posting quotes monthly, the ApplySalary should still carry
    a YEARLY number (12x) so the year-field helper formats correctly
    and the month-field helper divides back to the right monthly value."""
    text = "Monthly compensation: €6,000 - €8,000 per month."
    salary = apply_salary_for(text, profile_application_anchor_eur_year=125_000)
    assert salary.amount_per_year == 72_000   # 6000 * 12
    assert salary.amount_per_month == 6_000   # back to monthly
    assert salary.currency == "EUR"
    assert salary.sourced_from == "posting"


def test_custom_profile_anchor_honoured():
    salary = apply_salary_for("", profile_application_anchor_eur_year=160_000)
    assert salary.amount_per_year == 160_000
    assert salary.sourced_from == "profile_anchor"
