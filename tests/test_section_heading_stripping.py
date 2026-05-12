"""The extracted cover-letter / CV sub-sections must NOT keep the
`# I  Cover letter` / `# II  Curriculum vitae` heading.

Why this matters: those headings are visual section dividers inside
the unified application_package PDF. When the cover-letter sub-section
is used standalone (the email body, the dashboard preview, the cv.md
artifact), the heading leaks through as an `<h1>I Cover letter</h1>`
at the top of what the recipient sees — pointing at internal
package structure that they should never know exists.

Discovered when a sent application landed in a recruiter's inbox with
"I Cover letter" rendered as a giant header above "Dear hiring team,".
"""
from __future__ import annotations

from jobbot.generators.pipeline import _strip_section_heading


SAMPLE_COVER_LETTER_SECTION = """# I  Cover letter

Dear hiring team,

The role you describe is exactly the kind of problem I find compelling …

Best regards,
*Philipp Hilbert*
"""


SAMPLE_CV_SECTION = """# II  Curriculum vitae

## Bearing

Founding Product Manager. AI-native operator …

## Core strengths

- Translating messy operational workflows into dev-ready requirements
"""


def test_strip_removes_leading_cover_letter_heading() -> None:
    out = _strip_section_heading(SAMPLE_COVER_LETTER_SECTION)
    assert "I Cover letter" not in out
    assert "I  Cover letter" not in out
    assert out.startswith("Dear hiring team,"), (
        f"first non-heading line should be the salutation; got: {out[:80]!r}"
    )


def test_strip_removes_leading_cv_heading() -> None:
    out = _strip_section_heading(SAMPLE_CV_SECTION)
    assert "II Curriculum vitae" not in out
    assert "II  Curriculum vitae" not in out
    assert out.startswith("## Bearing")


def test_strip_only_removes_the_FIRST_heading_match() -> None:
    """A section can have other H2/H3 headings in its body — those must
    not be touched. Only the very first roman-numeral H1 is the divider."""
    md = "# I  Cover letter\n\nDear team,\n\n## Highlights\n\nThing one\n"
    out = _strip_section_heading(md)
    assert "## Highlights" in out, "subsequent headings must survive"


def test_strip_handles_case_insensitive_roman_numeral_variants() -> None:
    for variant in (
        "# I  Cover letter\n\nBody",
        "# i  Cover letter\n\nBody",
        "# II  Curriculum vitae\n\nBody",
        "# III  Some Third Section\n\nBody",
    ):
        out = _strip_section_heading(variant)
        assert out.startswith("Body"), f"failed for variant: {variant!r} → {out!r}"


def test_strip_is_a_noop_when_no_heading_present() -> None:
    """If extraction already gave us a clean body (the heading is missing
    for some reason), the helper must not mangle the text."""
    plain = "Dear hiring team,\n\nLooking forward to talking.\n"
    assert _strip_section_heading(plain) == plain


def test_strip_does_not_remove_non_roman_h1_headings() -> None:
    """A regular H1 like '# Philipp Hilbert' must NOT be stripped — that's
    the candidate's name on the CV header block, not a section divider."""
    md = "# Philipp Hilbert\n\nBerlin · ...\n"
    assert _strip_section_heading(md).startswith("# Philipp Hilbert")
