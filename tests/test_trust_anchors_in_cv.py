"""LinkedIn / GitHub / personal-site / YouTube trust-anchor band must be
visibly present at the top AND bottom of every tailored CV.

The band is injected post-LLM (the tailoring prompt's "never invent"
rule applies to the model, not to deterministic post-processing) so it
is guaranteed to appear regardless of what the model did with the
base CV's header block.
"""
from __future__ import annotations

from jobbot.generators.pipeline import _inject_trust_anchors, _trust_anchor_line
from jobbot.profile import Profile


def _make_profile(**link_overrides) -> Profile:
    links = {
        "linkedin": "https://www.linkedin.com/in/philipphilbert",
        "github": "https://github.com/hilbertp",
        "website": "https://true-north.berlin",
        "youtube_english_sample": "https://www.youtube.com/watch?v=nt06f71lgfE",
    }
    links.update(link_overrides)
    return Profile(personal={"full_name": "Philipp Hilbert", "links": links},
                   preferences={})


SAMPLE_CV = """# Philipp Hilbert

**Founding Product Manager**

Berlin, Germany · philipp@true-north.berlin

---

## Bearing

Founding PM.

## Experience

### projuncta

- Built things.
"""


def test_trust_anchor_line_includes_all_four_entries() -> None:
    line = _trust_anchor_line(_make_profile())
    assert "[LinkedIn](https://www.linkedin.com/in/philipphilbert)" in line
    assert "[GitHub](https://github.com/hilbertp)" in line
    assert "[true-north.berlin](https://true-north.berlin)" in line
    assert "[YouTube (EN sample)](https://www.youtube.com/watch?v=nt06f71lgfE)" in line


def test_trust_anchor_line_skips_missing_entries() -> None:
    """LinkedIn-only profile must still produce a one-entry band."""
    line = _trust_anchor_line(
        Profile(personal={"links": {"linkedin": "https://lnkd.in/x"}},
                preferences={})
    )
    assert line == "[LinkedIn](https://lnkd.in/x)"


def test_trust_anchor_line_returns_none_when_no_links() -> None:
    line = _trust_anchor_line(Profile(personal={}, preferences={}))
    assert line is None


def test_injection_renders_band_above_first_horizontal_rule() -> None:
    out = _inject_trust_anchors(SAMPLE_CV, _make_profile())
    head = out.split("---", 1)[0]
    assert "[LinkedIn]" in head, "trust band must appear in CV header block"
    assert "[GitHub]" in head
    assert "[true-north.berlin]" in head
    assert "[YouTube (EN sample)]" in head


def test_injection_appends_band_at_document_end() -> None:
    out = _inject_trust_anchors(SAMPLE_CV, _make_profile())
    # Last non-empty line should be the trust band (last link entry).
    tail_lines = [ln for ln in out.rstrip().splitlines() if ln.strip()]
    assert "[YouTube (EN sample)]" in tail_lines[-1] or "[LinkedIn]" in tail_lines[-1], (
        "trust band must be the last visible content of the CV"
    )


def test_injection_idempotent_with_no_links_returns_unchanged_cv() -> None:
    no_link_profile = Profile(personal={"links": {}}, preferences={})
    out = _inject_trust_anchors(SAMPLE_CV, no_link_profile)
    assert out == SAMPLE_CV


def test_injection_falls_back_when_no_horizontal_rule_present() -> None:
    """Some LLM outputs drop the `---` divider; we still place the band
    after the H1 + the immediate contact lines."""
    cv = "# Philipp Hilbert\n\n**Founding PM**\n\n## Experience\n\nworked.\n"
    out = _inject_trust_anchors(cv, _make_profile())
    # The band should land after the H1 paragraph but before the next ## heading.
    h1_to_exp = out.split("## Experience", 1)[0]
    assert "[LinkedIn]" in h1_to_exp
