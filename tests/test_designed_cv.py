"""The designed CV render: same facts as the ATS render, typeset for a human.

The point of these tests is that the two documents cannot drift. They share
one Markdown source and one parser, so the risk is not that the facts differ,
it is that the typesetting silently drops or mangles something the plain
render carried.
"""
from pathlib import Path

import pytest

from jobbot.generators.ats import (
    audit_ats_text,
    build_ats_cv,
    extract_pdf_text,
    parse_cv_markdown,
    pdf_page_count,
)
from jobbot.generators.designed import build_designed_cv, render_designed_html

BASE_CV = Path("data/applications/cv_general_ats.md")

pytestmark = pytest.mark.skipif(not BASE_CV.is_file(), reason="base CV source not present")


def test_designed_render_fits_the_two_page_budget(tmp_path):
    pdf = build_designed_cv(BASE_CV, tmp_path, stem="cv")
    assert pdf_page_count(pdf) <= 2


def test_contact_and_profile_urls_survive_extraction(tmp_path):
    """Design is where contact details usually die, so this is the load-bearing test.

    The editorial renderer this replaces lost both profile URLs, because they
    were hyperlink labels rather than printed text.
    """
    pdf = build_designed_cv(BASE_CV, tmp_path, stem="cv")
    text = extract_pdf_text(pdf)["pypdf"].replace("\n", " ")
    for needle in (
        "hilbert@true-north.berlin",
        "+357 94101644",
        "www.true-north.berlin",
        "linkedin.com/in/philipp-hilbert-34032275",
        "github.com/hilbertp",
    ):
        assert needle in text, f"{needle} did not survive the designed render"


def test_designed_render_still_passes_the_text_layer_audit(tmp_path):
    """It is for people, but it should degrade gracefully if a parser sees it.

    In particular the tracking has to stay low enough that words do not
    shatter into spaced characters, which is what the editorial track does.
    """
    pdf = build_designed_cv(BASE_CV, tmp_path, stem="cv")
    text = extract_pdf_text(pdf)["pypdf"]
    assert audit_ats_text(text) == []


def test_both_renders_carry_the_same_dates(tmp_path):
    """One source, so every station date must appear in both documents."""
    import re

    designed = extract_pdf_text(build_designed_cv(BASE_CV, tmp_path / "d", stem="cv"))["pypdf"]
    ats_paths, _ = build_ats_cv(BASE_CV, tmp_path / "a", stem="cv")
    plain = extract_pdf_text(ats_paths["pdf"])["pypdf"]

    dates = set(re.findall(r"\b\d{2}/\d{4}\b", plain))
    assert dates, "the plain render carried no month-precision dates"
    assert dates == set(re.findall(r"\b\d{2}/\d{4}\b", designed))


def test_role_dates_are_split_out_for_typesetting():
    """The date range gets its own span so it can take the structural face."""
    doc = parse_cv_markdown(BASE_CV.read_text(encoding="utf-8"))
    html = render_designed_html(doc)
    assert '<span class="dates">07/2024 - 05/2025</span>' in html
    # A role line without a trailing date must not be mangled by the split.
    assert "Philipp Hilbert" in html
