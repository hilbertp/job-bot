"""Freelance handling: freelancermap is gated to Product Owner / Manager
titles at the source, and held to an hourly-rate floor instead of the
annual salary floor.

User directive 2026-05-18: "use freelancermap as PO freelance position
only. thats fine at 80 EUR per hour remote!" Two requirements:
  1. Only product roles enter from freelancermap (its search is an
     unfilterable firehose of every trade).
  2. Day/hour rates must not be misread by the annual EUR/year floor
     (a "800 EUR/Tag" rate is NOT an 800 EUR/year salary).
"""
from __future__ import annotations

from jobbot.applier.salary import (
    parse_hourly_rate_eur, posting_below_hourly_floor, posting_below_salary_floor,
)
from jobbot.scrapers.freelancermap import _PRODUCT_TITLE_RE


# ---------------------------------------------------------------------------
# title gate
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize("title", [
    "Product Owner (m/w/d)",
    "Senior Product Manager Telekommunikation",
    "Interim Product Lead",
    "Produktmanager B2B",
    "Product Owner / Scrum",
])
def test_title_gate_admits_product_roles(title):
    assert _PRODUCT_TITLE_RE.search(title) is not None


@pytest.mark.parametrize("title", [
    "Bauleiter Hochbau (m/w/d)",
    "IT Firewall Architekt",
    "Senior Java Developer ePayment",
    "HSE Manager / Fachkraft für Arbeitssicherheit",
    "Projektleiter Rückbau Kohlekraftwerk",
    "SAP CS Berater",
])
def test_title_gate_rejects_non_product_roles(title):
    assert _PRODUCT_TITLE_RE.search(title) is None


# ---------------------------------------------------------------------------
# parse_hourly_rate_eur
# ---------------------------------------------------------------------------

def test_parse_hourly_std():
    assert parse_hourly_rate_eur("Stundensatz: 95 €/Std") == 95


def test_parse_hourly_slash_h():
    assert parse_hourly_rate_eur("Rate 110 EUR/h remote") == 110


def test_parse_day_rate_divided_by_eight():
    # 800 EUR/Tag -> 100 EUR/h
    assert parse_hourly_rate_eur("Tagessatz 800 €/Tag") == 100


def test_parse_no_rate_returns_none():
    assert parse_hourly_rate_eur("Konditionen auf Anfrage, remote möglich") is None


def test_parse_ignores_implausibly_low_numbers():
    # "8 h/Tag" workload is not a rate
    assert parse_hourly_rate_eur("Auslastung 8 h pro Tag, Projektstart sofort") is None


def test_parse_picks_highest_when_multiple():
    assert parse_hourly_rate_eur("ab 70 €/h, bis 90 €/h möglich") == 90


# ---------------------------------------------------------------------------
# posting_below_hourly_floor
# ---------------------------------------------------------------------------

def test_below_floor_filtered():
    below, reason = posting_below_hourly_floor("Rate: 60 €/Std", 80)
    assert below is True
    assert "rate_below_floor" in reason


def test_at_or_above_floor_kept():
    below, _ = posting_below_hourly_floor("Rate: 80 €/Std", 80)
    assert below is False
    below2, _ = posting_below_hourly_floor("Rate: 95 €/Std", 80)
    assert below2 is False


def test_day_rate_above_floor_kept():
    # 800/day = 100/h >= 80 floor
    below, _ = posting_below_hourly_floor("Tagessatz 800 €/Tag", 80)
    assert below is False


def test_day_rate_below_floor_filtered():
    # 560/day = 70/h < 80 floor
    below, reason = posting_below_hourly_floor("Tagessatz 560 €/Tag", 80)
    assert below is True


def test_no_rate_not_filtered():
    below, _ = posting_below_hourly_floor("Rate auf Anfrage", 80)
    assert below is False


def test_floor_zero_disables():
    below, _ = posting_below_hourly_floor("Rate: 30 €/Std", 0)
    assert below is False


# ---------------------------------------------------------------------------
# regression: a day-rate must NOT be filtered by the ANNUAL floor
# ---------------------------------------------------------------------------

def test_annual_floor_would_misread_day_rate_hence_freelance_exemption():
    """This is WHY freelance sources are exempt from the annual floor:
    the annual parser can misread a bare 'EUR 800' as a salary. We assert
    the hourly path keeps an 800 EUR/Tag (=100/h) project, which is well
    above the 80/h floor and must survive."""
    below_hourly, _ = posting_below_hourly_floor("Tagessatz 800 €/Tag", 80)
    assert below_hourly is False
