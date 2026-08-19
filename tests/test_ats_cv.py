"""The ATS track: the base CV must survive a machine read.

These tests exist because the failure mode is invisible by eye. The editorial
general CV looks immaculate and still parses into `1 0 +   Y E A R S` with no
LinkedIn URL anywhere in the text layer, so the guard has to read the rendered
file back rather than inspect the source.
"""
from __future__ import annotations

import pytest

from jobbot.config import REPO_ROOT
from jobbot.generators.ats import (
    ATSFormatError,
    audit_ats_docx,
    audit_ats_pdf,
    audit_ats_text,
    audit_contact_integrity,
    build_ats_cv,
    parse_cv_markdown,
    render_ats_html,
)

BASE_CV = REPO_ROOT / "data" / "applications" / "cv_general_ats.md"

MINIMAL = """# Ada Lovelace

Product Manager

Berlin, Germany | +49 30 000000 | ada@example.com

www.example.com | linkedin.com/in/ada | github.com/ada

## Profile

Product manager with a decade of delivery.

## Work Experience

**Product Manager, Analytical Engines, Berlin, 2020 - Present**

Punch-card platform for scientific computation.

- Cut card-loading time by 40% by redesigning the operator workflow.

*Fortran, punch cards*

## Skills

- **Delivery:** Agile, Scrum.

## Education

**Diplom, University of London, 1843**

## Languages

English (native speaker)
"""


def test_parse_extracts_header_and_sections():
    doc = parse_cv_markdown(MINIMAL)
    assert doc.name == "Ada Lovelace"
    assert doc.title == "Product Manager"
    assert len(doc.contact) == 2
    assert [s.heading for s in doc.sections] == [
        "Profile", "Work Experience", "Skills", "Education", "Languages",
    ]
    experience = doc.sections[1]
    assert [b.kind for b in experience.blocks] == ["role", "para", "bullet", "note"]


def test_tables_are_rejected():
    md = MINIMAL.replace(
        "- Cut card-loading time by 40% by redesigning the operator workflow.",
        "| Role | Year |\n|---|---|\n| PM | 2020 |",
    )
    with pytest.raises(ATSFormatError, match="tables"):
        parse_cv_markdown(md)


def test_html_is_single_column_and_uncoloured():
    html = render_ats_html(parse_cv_markdown(MINIMAL))
    for hazard in ("letter-spacing", "text-transform", "column-count", "<table", "float:"):
        assert hazard not in html
    # Only black ink on white paper: no accent colours to confuse a scanner.
    assert "#8d2b1c" not in html


def test_audit_flags_letter_spacing_and_missing_urls():
    findings = audit_ats_text("1 0 +   Y E A R S   O F   E X P.\nSome body text.")
    assert any("letter-spacing" in f for f in findings)
    assert any("LinkedIn" in f for f in findings)
    assert any("profile" in f for f in findings)


def test_audit_flags_banned_artefacts():
    text = "Contact: me@x.com +49 30 111111 linkedin.com/in/x github.com/x lovable.app/cv"
    findings = audit_ats_text(text)
    assert any("lovable" in f for f in findings)
    assert any("em-dash" in f for f in audit_ats_text(text + " a — b"))
    assert any("Master of Science" in f for f in audit_ats_text(text + " Master of Science"))
    assert any("transliterated" in f for f in audit_ats_text(text + " Muenchen"))


def test_contact_integrity_catches_glued_contact_line():
    doc = parse_cv_markdown(MINIMAL)
    glued = "Product Manager in Softwareada@example.com www.example.com"
    findings = audit_contact_integrity(doc, glued)
    assert any("ada@example.com" in f for f in findings)
    intact = " ".join(doc.contact)
    assert audit_contact_integrity(doc, intact) == []


def test_render_round_trips_clean(tmp_path):
    paths, findings = build_ats_cv(BASE_CV, tmp_path, stem="cv", max_pages=2)
    assert findings == []
    assert paths["pdf"].exists() and paths["docx"].exists()


def test_base_cv_fits_the_two_page_budget(tmp_path):
    paths, _ = build_ats_cv(BASE_CV, tmp_path, stem="cv")
    assert audit_ats_pdf(paths["pdf"], max_pages=2) == []


def test_docx_has_no_tables_and_keeps_the_text_layer(tmp_path):
    paths, _ = build_ats_cv(BASE_CV, tmp_path, stem="cv")
    assert audit_ats_docx(paths["docx"]) == []


def test_missing_strict_extractor_is_reported_not_silently_skipped(tmp_path, monkeypatch):
    from jobbot.generators import ats

    paths, _ = build_ats_cv(BASE_CV, tmp_path, stem="cv")
    original = ats.extract_pdf_text
    monkeypatch.setattr(
        ats, "extract_pdf_text", lambda path: {"pypdf": original(path)["pypdf"]}
    )
    findings = ats.audit_ats_pdf(paths["pdf"])
    assert any("pdfminer.six is not installed" in f for f in findings)


def test_keyword_coverage_separates_echoed_from_missing_terms():
    from jobbot.generators.ats import keyword_coverage

    jd = (
        "We are looking for a Product Owner with strong stakeholder management, "
        "sprint planning and retrospective facilitation. Salesforce administration "
        "is required. Salesforce experience is essential."
    )
    result = keyword_coverage(BASE_CV.read_text(encoding="utf-8"), jd)
    assert "stakeholder management" in result["covered"]
    assert "retrospective" in result["covered"]
    assert "salesforce" in result["missing"]


def test_base_cv_carries_the_core_product_vocabulary():
    """The terms a recruiter boolean-searches for have to be literally present."""
    text = BASE_CV.read_text(encoding="utf-8").lower()
    for term in (
        "product owner", "product manager", "requirements", "stakeholder management",
        "agile", "scrum", "kanban", "safe", "sprint planning", "retrospective",
        "backlog refinement", "user stories", "acceptance criteria", "roadmap",
        "discovery", "mvp", "kpi", "user acceptance testing", "jira", "confluence",
    ):
        assert term in text, f"missing ATS keyword: {term}"


def test_bullets_stay_attached_to_their_text(tmp_path):
    """WeasyPrint's default outside marker extracts as orphan bullet glyphs."""
    from jobbot.generators.ats import extract_pdf_text

    paths, _ = build_ats_cv(BASE_CV, tmp_path, stem="cv")
    for text in extract_pdf_text(paths["pdf"]).values():
        orphans = [line for line in text.splitlines() if line.strip() in {"•", "-"}]
        assert not orphans, f"{len(orphans)} orphan bullet markers in the text layer"
