"""Post-generation QA gate (generators.qa).

The QA report automates the checks the research says actually matter:
the select-and-copy text-layer test on the ATS-facing cv.pdf, the
two-page budget, mirror-term coverage, embedded-directive compliance,
and the house content bans (lovable links, em/en dashes, filler).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobbot.generators.jd_signals import Directive, JdSignals
from jobbot.generators.qa import (
    QA_REPORT_FILENAME,
    check_banned_content,
    check_directive_compliance,
    check_mirror_coverage,
    check_page_budget,
    check_pdf_text_layer,
    run_qa,
)
from jobbot.profile import Profile


def _profile() -> Profile:
    return Profile(
        personal={"full_name": "Philipp Hilbert",
                  "email": "hilbert@true-north.berlin"},
        preferences={},
    )


def _signals(**kw) -> JdSignals:
    base = dict(language="en", posting_title="Product Manager",
                mirror_terms=[], directives=[])
    base.update(kw)
    return JdSignals(**base)


# --- banned content ------------------------------------------------------

def test_lovable_anywhere_is_a_fail():
    check = check_banned_content("See my work at https://foo.lovable.app/x")
    assert check.status == "fail"
    assert "lovable" in check.detail


def test_surviving_en_dash_is_a_fail():
    assert check_banned_content("Discovery – never a phase.").status == "fail"


def test_dash_inside_code_fence_is_exempt():
    assert check_banned_content("```\nrange(1—5)\n```").status == "pass"


def test_stock_filler_phrases_warn():
    check = check_banned_content("I am passionate about innovation.")
    assert check.status == "warn"


def test_clean_documents_pass():
    assert check_banned_content("Shipped EMIL in under a week.").status == "pass"


# --- mirror coverage -----------------------------------------------------

def test_all_terms_present_passes():
    cv = "Led Product Discovery in Jira across nine teams."
    assert check_mirror_coverage(cv, ["Product Discovery", "Jira"]).status == "pass"


def test_missing_terms_warn_and_are_named():
    check = check_mirror_coverage("Led discovery work.", ["Jira", "OKRs"])
    assert check.status == "warn"
    assert "Jira" in check.detail and "OKRs" in check.detail


def test_no_terms_is_a_pass():
    assert check_mirror_coverage("anything", []).status == "pass"


# --- directive compliance ------------------------------------------------

def test_satisfied_directive_passes():
    signals = _signals(directives=[
        Directive(instruction='include "banana"', must_contain="banana"),
    ])
    assert check_directive_compliance(
        "Banana is my favorite fruit, as requested.", signals,
    ).status == "pass"


def test_missing_directive_token_fails():
    signals = _signals(directives=[
        Directive(instruction='quote the reference code "X7-2024"',
                  must_contain="X7-2024"),
    ])
    check = check_directive_compliance("Dear team, I apply.", signals)
    assert check.status == "fail"
    assert "X7-2024" in check.detail


def test_uncheckable_directives_pass_vacuously():
    signals = _signals(directives=[Directive(instruction="answer a question")])
    assert check_directive_compliance("letter", signals).status == "pass"


# --- PDF checks (real WeasyPrint render, real pypdf extraction) ----------

def _render_pdf(tmp_path: Path, html: str) -> str:
    weasyprint = pytest.importorskip("weasyprint")
    dest = tmp_path / "cv.pdf"
    weasyprint.HTML(string=html).write_pdf(str(dest))
    return str(dest)


def test_text_layer_check_passes_on_real_render(tmp_path: Path):
    """A complete contact block plus canonical headings is a clean pass."""
    pdf = _render_pdf(
        tmp_path,
        "<h1>Philipp Hilbert</h1>"
        "<p>+357 94101644 &middot; hilbert@true-north.berlin</p>"
        "<h2>WORK EXPERIENCE</h2><p>Product Manager</p>"
        "<h2>SKILLS</h2><p>Jira</p>"
        "<h2>EDUCATION</h2><p>TU Berlin</p>"
        "<h2>LANGUAGES</h2><p>German, English</p>",
    )
    assert check_pdf_text_layer(
        pdf, "Philipp Hilbert", "hilbert@true-north.berlin",
    ).status == "pass"


def test_text_layer_check_warns_on_thin_record(tmp_path: Path):
    """Name and email alone parse, so this is not a fail. But no phone and
    no canonical headings leave a thin structured record, which the gate
    now surfaces as a warning instead of a silent pass."""
    pdf = _render_pdf(
        tmp_path,
        "<h1>Philipp Hilbert</h1><p>hilbert@true-north.berlin</p>",
    )
    check = check_pdf_text_layer(
        pdf, "Philipp Hilbert", "hilbert@true-north.berlin",
    )
    assert check.status == "warn"
    assert "phone" in check.detail or "headings" in check.detail


def test_text_layer_check_fails_when_contact_is_missing(tmp_path: Path):
    pdf = _render_pdf(tmp_path, "<p>An anonymous document.</p>")
    check = check_pdf_text_layer(
        pdf, "Philipp Hilbert", "hilbert@true-north.berlin",
    )
    assert check.status == "fail"


def test_page_budget_passes_at_two_pages_and_fails_at_three(tmp_path: Path):
    two = _render_pdf(
        tmp_path,
        '<p>page one</p><p style="page-break-before: always">page two</p>',
    )
    assert check_page_budget(two).status == "pass"
    three = _render_pdf(
        tmp_path,
        '<p>1</p><p style="page-break-before: always">2</p>'
        '<p style="page-break-before: always">3</p>',
    )
    assert check_page_budget(three).status == "fail"


# --- orchestration -------------------------------------------------------

def test_run_qa_writes_report_and_never_raises(tmp_path: Path):
    report = run_qa(
        job_dir=tmp_path,
        profile=_profile(),
        signals=_signals(mirror_terms=["Jira"]),
        cv_md="Led delivery in Jira.",
        cover_letter_md="Dear team.",
        cv_pdf_path=None,  # missing PDF degrades to warn, not crash
    )
    payload = json.loads((tmp_path / QA_REPORT_FILENAME).read_text())
    assert payload["worst"] in {"pass", "warn", "fail"}
    names = {c["name"] for c in payload["checks"]}
    assert {"pdf_text_layer", "mirror_coverage",
            "directive_compliance", "banned_content"} <= names
    assert report.worst == payload["worst"]


def test_run_qa_worst_reflects_a_hard_failure(tmp_path: Path):
    report = run_qa(
        job_dir=tmp_path,
        profile=_profile(),
        signals=_signals(),
        cv_md="Portfolio: mysite.lovable.app",
        cover_letter_md="Dear team.",
        cv_pdf_path=None,
    )
    assert report.worst == "fail"
