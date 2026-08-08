"""Hygiene guards on generated application artefacts.

All three failures below were found in one real package on 2026-08-08, built
for a live 88-score Abu Dhabi posting:

  1. The claude_cli backend is an agentic harness, so it narrated before
     complying: "The session doesn't have file-write permissions granted
     yet. Here is the complete application package..." — and that sentence
     was rendered INTO application_package.pdf, the file the email channel
     attaches to an employer.
  2. That preamble also broke hero extraction (anchored at string start), so
     the standalone cv.md lost the name and contact line and opened cold at
     "## Bearing". A CV PDF with no name and no email reached disk.
  3. Six em-dashes appeared in cv.md although the base CV contains none.
"""
from __future__ import annotations

from jobbot.generators.pipeline import (
    _extract_hero, _scrub_ai_tells, _strip_llm_preamble,
)

_REAL_PREAMBLE = (
    "The session doesn't have file-write permissions granted yet. Here is "
    "the complete application package as rendered Markdown, every section "
    "in the exact specified order, ready to copy:\n\n"
)
_DOC = (
    "# Philipp Hilbert. *AI product lead.*\n\n"
    "*Positioning,* ten years of B2B product delivery.\n\n"
    "Berlin, Germany · hilbert@true-north.berlin · true-north.berlin\n\n"
    "---\n\n"
    "## Bearing\n\nTen years of B2B product management.\n"
)


def test_strips_the_real_cli_preamble():
    out = _strip_llm_preamble(_REAL_PREAMBLE + _DOC)
    assert out.startswith("# Philipp Hilbert.")
    assert "file-write permissions" not in out


def test_leaves_a_clean_document_untouched():
    assert _strip_llm_preamble(_DOC) == _DOC.strip()


def test_does_not_eat_a_document_that_has_no_h1():
    body = "Dear hiring team,\n\nI am writing about the role.\n"
    assert _strip_llm_preamble(body) == body.strip()


def test_ignores_an_h1_far_below_the_preamble_window():
    """A heading 30 lines down is a section, not a document start."""
    body = "\n".join(["prose line"] * 30) + "\n# Late heading\n"
    assert _strip_llm_preamble(body).startswith("prose line")


def test_hero_is_extracted_even_with_a_line_above_it():
    """Trust anchors are injected above the hero; that must not hide it."""
    with_anchor = "[LinkedIn](x) · [GitHub](y)\n\n---\n\n" + _DOC
    hero = _extract_hero(with_anchor)
    assert hero.startswith("# Philipp Hilbert.")
    assert "hilbert@true-north.berlin" in hero, "contact line must survive"
    assert "## Bearing" not in hero


def test_hero_extraction_after_preamble_strip_recovers_name_and_email():
    """End-to-end of the actual bug: preamble in, hero with contact out."""
    hero = _extract_hero(_strip_llm_preamble(_REAL_PREAMBLE + _DOC))
    assert "Philipp Hilbert" in hero
    assert "hilbert@true-north.berlin" in hero


def test_em_and_en_dashes_are_replaced():
    got = _scrub_ai_tells("Discovery is continuous — never a phase – really.")
    assert "—" not in got and "–" not in got
    assert got == "Discovery is continuous, never a phase, really."


def test_scrub_preserves_hyphens_and_bullets():
    src = "- AI-native delivery\n- Zero-to-one marketplace\n"
    assert _scrub_ai_tells(src) == src


def test_scrub_leaves_code_fences_alone():
    src = "Prose — here.\n\n```\nrange(1—5)\n```\n"
    out = _scrub_ai_tells(src)
    assert "Prose, here." in out
    assert "range(1—5)" in out, "a dash inside a snippet is data, not prose"


def test_scrub_is_idempotent():
    once = _scrub_ai_tells("A — B")
    assert _scrub_ai_tells(once) == once
