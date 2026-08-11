"""The tailored CV is a TWO page document.

Generated CVs were coming out at four pages. Three causes, all fixed:

1. The installed base CV was the six-page narrative version, so tailoring
   inherited its length. The base CV is now the two-page document and the
   prompts state its length as a budget rather than raw material.
2. The package prompt asked for "3-5 bullets per role" across nine roles,
   i.e. 27-45 bullets. Roles now keep the base CV's compact two-line shape.
3. The CV is the package's LAST section, so extracting it dragged along the
   package's bottom trust-anchor band. On an otherwise two-page CV that single
   line landed alone on page three (2,407 chars on p1, 1,749 on p2, 69 on p3).
"""
from __future__ import annotations

from pathlib import Path

from jobbot.generators.pipeline import PROMPTS, _strip_trailing_anchor_band


def test_trailing_anchor_band_is_stripped():
    md = ("## Languages\n\nGerman native, English C2\n\n---\n\n"
          "[LinkedIn](x) · [GitHub](y) · www.true-north.berlin\n")
    out = _strip_trailing_anchor_band(md)
    assert out.endswith("German native, English C2")
    assert "LinkedIn" not in out


def test_a_band_in_the_middle_is_left_alone():
    """Only the TRAILING band is redundant; the one above the CV stays."""
    md = ("[LinkedIn](x) · [GitHub](y)\n\n---\n\n## Bearing\n\nTen years.\n")
    assert _strip_trailing_anchor_band(md) == md.rstrip()


def test_content_without_a_band_is_unchanged():
    md = "## Languages\n\nGerman native, English C2"
    assert _strip_trailing_anchor_band(md) == md


def test_prompts_state_the_two_page_budget():
    """Both generation paths must carry the limit, not just one."""
    package = (PROMPTS / "application_package.md").read_text()
    tailor = (PROMPTS / "cv_tailor.md").read_text()
    assert "TWO PAGES" in package
    assert "TWO PAGES" in tailor
    # The bullet-per-role instruction is what produced four pages.
    assert "3–5 bullets per role" not in package
    assert "3-5 bullets per role" not in package


def test_package_prompt_keeps_stack_in_the_capability_summary():
    """Stack/tools live in one summary section, not scattered per project."""
    package = (PROMPTS / "application_package.md").read_text()
    assert "## What I can do" in package
    # The old duplicate strengths list is gone.
    assert "## Core strengths" not in package
