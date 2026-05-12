"""Unified opus-style application package.

Pins:
  - The renderer emits the editorial typography scaffolding: top + bottom
    banners with company + role, Newsreader serif headlines, § section
    markers, roman-numeral section dividers for Cover Letter (I) and
    Curriculum Vitae (II).
  - Section extraction recovers the cover-letter and CV sub-sections so
    ATS form adapters that still expect cv.md / cover_letter.md keep
    working.
  - The trust-anchor band is injected top + bottom of the package.
  - The email channel attaches application_package.pdf when present and
    falls back to cv.pdf + cover_letter.pdf when the package failed to
    render.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from jobbot.applier.email_channel import _build_message
from jobbot.config import Secrets
from jobbot.generators.pipeline import (
    _extract_section,
    _inject_trust_anchors,
    _render_application_html,
    _SEC_COVER_LETTER_RE,
    _SEC_CURRICULUM_VITAE_RE,
)
from jobbot.models import GeneratedDocs, JobPosting
from jobbot.profile import Profile


SAMPLE_PACKAGE_MD = """# Philipp Hilbert. *Founding Product Manager.*

*Positioning,* AI-native PM for messy B2B workflows.

Berlin, Germany · philipp@true-north.berlin · true-north.berlin

---

## Why Acme

Acme is interesting because of its workflow ambition. *That is exactly the environment where my strengths compound.*

## AI-native stack

*Daily tools, not buzzwords.*

- **Lovable** — polished front-end prototypes
- **Claude Code** — in-repo refactors
- **Cursor** — shipping environment
- **GPT-5** — spec, edge cases, review
- **Framer** — design-heavy work
- **Gamma.app** — presentations

## How I would work at Acme

*First weeks, concrete.*

### Week 1

#### Listen, map, find the gaps.

Join customer calls, map the workflows, identify ambiguity.

### Week 2

#### Prototype, clarify, slice.

Prototype the first flows, clarify edge cases.

### Week 3+

#### Ship, unblock, close loops.

Turn validated workflows into shippable increments.

---

# I  Cover letter

Dear Acme team,

Your role description reads like a call for someone who can create clarity.

Best regards,
*Philipp Hilbert*

---

# II  Curriculum vitae

## Bearing

Founding Product Manager. AI-native operator.

## Core strengths

- Translating messy operational workflows into dev-ready requirements
- AI-native execution and rapid prototyping
- Cross-functional stakeholder alignment

## Professional experience

### Rohde & Schwarz   2024, 2025

*Product Owner — AI Data Transformation*

- Built and operated a central AI and data management platform.
- Delivered autonomous production-ready features.

## Languages

German, native. English, C2.
"""


def _job() -> JobPosting:
    return JobPosting(
        id="opus-1", source="linkedin",
        title="Founding Product Manager", company="Acme",
        url="https://example.com/opus", apply_url=None,
        description="Founding PM for an AI-native operations product.",
    )


def _profile_with_links() -> Profile:
    return Profile(
        personal={
            "full_name": "Philipp Hilbert",
            "links": {
                "linkedin": "https://linkedin.com/in/philipphilbert",
                "github": "https://github.com/hilbertp",
                "website": "https://true-north.berlin",
                "youtube_english_sample": "https://www.youtube.com/watch?v=nt06f71lgfE",
            },
        },
        preferences={},
    )


def test_render_emits_top_and_bottom_company_banners() -> None:
    html = _render_application_html(SAMPLE_PACKAGE_MD, job=_job())
    soup = BeautifulSoup(html, "html.parser")

    banners = soup.select(".package-banner")
    assert len(banners) == 2, "package needs both a top and a bottom banner"

    top, bottom = banners
    assert "top" in (top.get("class") or [])
    assert "bottom" in (bottom.get("class") or [])
    top_text = top.get_text(" ", strip=True)
    assert "APPLICATION" in top_text and "ACME" in top_text
    assert "FOUNDING PRODUCT MANAGER" in top_text


def test_render_rewrites_roman_numeral_section_headings_to_dividers() -> None:
    html = _render_application_html(SAMPLE_PACKAGE_MD, job=_job())
    soup = BeautifulSoup(html, "html.parser")

    dividers = soup.select(".section-divider")
    numerals = [d.select_one(".section-numeral").get_text(strip=True)
                for d in dividers]
    titles = [d.select_one(".section-title").get_text(strip=True)
              for d in dividers]
    assert numerals == ["I", "II"]
    assert titles == ["Cover letter", "Curriculum vitae"]


def test_render_loads_newsreader_serif_and_section_marker_styling() -> None:
    html = _render_application_html(SAMPLE_PACKAGE_MD, job=_job())
    # The Google Font import is what gives the hero its opus-style serif.
    assert "Newsreader" in html
    # Section markers use the § prefix via CSS ::before.
    assert "content: \"§ \"" in html


def test_extract_cover_letter_returns_section_i_body() -> None:
    body = _extract_section(_SEC_COVER_LETTER_RE, SAMPLE_PACKAGE_MD)
    assert body.startswith("# I  Cover letter")
    assert "Dear Acme team" in body
    # Must NOT bleed into section II.
    assert "Curriculum vitae" not in body


def test_extract_cv_returns_section_ii_body() -> None:
    body = _extract_section(_SEC_CURRICULUM_VITAE_RE, SAMPLE_PACKAGE_MD)
    assert body.startswith("# II  Curriculum vitae")
    assert "Bearing" in body and "Languages" in body
    # Cover letter content does NOT belong here.
    assert "Dear Acme team" not in body


def test_trust_anchor_injection_lands_in_unified_package() -> None:
    injected = _inject_trust_anchors(SAMPLE_PACKAGE_MD, _profile_with_links())
    # Top band: before the first horizontal rule.
    head = injected.split("---", 1)[0]
    assert "[LinkedIn]" in head and "[GitHub]" in head
    assert "[true-north.berlin]" in head
    assert "[YouTube (EN sample)]" in head
    # Bottom band: last visible content of the document.
    tail_lines = [ln for ln in injected.rstrip().splitlines() if ln.strip()]
    assert "[LinkedIn]" in tail_lines[-1] or "[YouTube" in tail_lines[-1]


def test_email_channel_prefers_application_package_pdf(tmp_path: Path) -> None:
    out = tmp_path / "job_out"
    out.mkdir()
    pkg = out / "application_package.pdf"
    cv = out / "cv.pdf"
    cl = out / "cover_letter.pdf"
    pkg.write_bytes(b"%PDF package")
    cv.write_bytes(b"%PDF cv stub")
    cl.write_bytes(b"%PDF cl stub")

    docs = GeneratedDocs(
        cv_md="# CV", cv_html="<h1>CV</h1>",
        cover_letter_md="cover", cover_letter_html="<p>cover</p>",
        output_dir=str(out),
        cv_pdf=str(cv), cover_letter_pdf=str(cl),
        application_package_pdf=str(pkg),
    )
    job = _job().model_copy(update={"apply_email": "careers@acme.test"})
    msg = _build_message(job, _profile_with_links(), docs,
                        Secrets(anthropic_api_key="x", gmail_address="a@b",
                                gmail_app_password="x", notify_to="a@b",
                                truenorth_smtp_user="hilbert@true-north.berlin"))

    attachments = {a.get_filename(): a for a in msg.iter_attachments()}
    assert set(attachments) == {"application_package.pdf"}, (
        "the unified package should be the sole attachment when available"
    )


def test_email_channel_falls_back_to_cv_and_cl_when_package_missing(tmp_path: Path) -> None:
    out = tmp_path / "job_out"
    out.mkdir()
    cv = out / "cv.pdf"
    cl = out / "cover_letter.pdf"
    cv.write_bytes(b"%PDF cv stub")
    cl.write_bytes(b"%PDF cl stub")

    docs = GeneratedDocs(
        cv_md="# CV", cv_html="<h1>CV</h1>",
        cover_letter_md="cover", cover_letter_html="<p>cover</p>",
        output_dir=str(out),
        cv_pdf=str(cv), cover_letter_pdf=str(cl),
        # Note: application_package_pdf intentionally None
    )
    job = _job().model_copy(update={"apply_email": "careers@acme.test"})
    msg = _build_message(job, _profile_with_links(), docs,
                        Secrets(anthropic_api_key="x", gmail_address="a@b",
                                gmail_app_password="x", notify_to="a@b",
                                truenorth_smtp_user="hilbert@true-north.berlin"))

    attachments = {a.get_filename(): a for a in msg.iter_attachments()}
    assert set(attachments) == {"cv.pdf", "cover_letter.pdf"}
