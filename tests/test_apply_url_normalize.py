"""`normalize_apply_url` rewrites JD-page URLs to the actual form path so
the LLM-fill adapter lands on a fillable form instead of the description
page (which falls back to the dry-run GenericAdapter).

Real-world driver: 2026-05-21, Sweed and Nylas both fell through to the
dry-run GenericAdapter because their Ashby posting URL is the JD page; the
form lives at `<posting>/application`.
"""
from __future__ import annotations

from jobbot.applier.apply_url import normalize_apply_url


def test_ashby_jd_url_gets_application_suffix():
    assert (
        normalize_apply_url(
            "https://jobs.ashbyhq.com/nylas/2ad7ae0b-5c93-4c7d-acad-99c8a76f5a38"
        )
        == "https://jobs.ashbyhq.com/nylas/2ad7ae0b-5c93-4c7d-acad-99c8a76f5a38/application"
    )


def test_ashby_trailing_slash_normalized():
    assert (
        normalize_apply_url(
            "https://jobs.ashbyhq.com/sweedpos.com/eb71cf3d-40f1-4378-b56a-a606bd0bd9f2/"
        )
        == "https://jobs.ashbyhq.com/sweedpos.com/eb71cf3d-40f1-4378-b56a-a606bd0bd9f2/application"
    )


def test_ashby_query_string_dropped_and_suffixed():
    assert (
        normalize_apply_url(
            "https://jobs.ashbyhq.com/galvany/f13ea833-74fb-4812-b8a2-c408ebcdb3c9?utm=x"
        )
        == "https://jobs.ashbyhq.com/galvany/f13ea833-74fb-4812-b8a2-c408ebcdb3c9/application"
    )


def test_ashby_already_application_left_untouched():
    url = "https://jobs.ashbyhq.com/primer.io/b5f3bee5-4228-418e-b9d2-0652fff785a6/application"
    assert normalize_apply_url(url) == url


def test_non_ashby_url_untouched():
    url = "https://job-boards.greenhouse.io/backblaze/jobs/5210076008"
    assert normalize_apply_url(url) == url


def test_join_url_untouched():
    url = "https://join.com/companies/endios/16117915-senior-product-owner-m-w-d"
    assert normalize_apply_url(url) == url


def test_none_and_empty_pass_through():
    assert normalize_apply_url(None) is None
    assert normalize_apply_url("") == ""
