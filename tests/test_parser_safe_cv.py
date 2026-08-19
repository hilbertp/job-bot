"""Parser-safe CV pipeline: render rules, prompt pins, and the wired path.

Research grounding (screening-stack dossier, 2026-08): cv.pdf is the
ATS-facing artefact. Multi-column reading order is the top documented
parse risk (extracted text interleaves, skill fields come back blank,
and blank fields make the candidate invisible in recruiter search), so
the standalone CV renders single-column while the human-facing unified
package keeps its editorial two-column grids. The generation payload
carries deterministic targeting signals, and every package leaves a
qa_report.json behind.
"""
from __future__ import annotations

import json
from pathlib import Path

from jobbot.config import Config, Secrets
from jobbot.generators.pipeline import (
    PROMPTS,
    _render_application_html,
    _render_html,
    generate_application_package,
)
from jobbot.models import JobPosting
from jobbot.profile import Profile


def test_standalone_cv_render_has_no_multi_column_layout():
    html = _render_html("# Name\n\n*Tools.*\n\n- **Jira**, delivery\n")
    assert "column-count" not in html


def test_unified_package_render_keeps_its_two_column_grids():
    html = _render_application_html("# Name\n")
    assert "column-count: 2" in html


def test_prompts_carry_the_targeting_rules():
    package = (PROMPTS / "application_package.md").read_text()
    tailor = (PROMPTS / "cv_tailor.md").read_text()
    letter = (PROMPTS / "cover_letter.md").read_text()
    assert "mirror_terms" in package and "mirror_terms" in tailor
    assert "Title alignment" in package
    assert "-Present" in package, "the ASCII-hyphen date rule must be pinned"
    assert "Directives are mandatory" in letter


def test_tighten_prompt_exists_and_pins_the_budget():
    tighten = (PROMPTS / "cv_tighten.md").read_text()
    assert "TWO" in tighten
    assert "Never drop a role" in tighten


_SAMPLE_PACKAGE = """# Philipp Hilbert. *Senior Product Manager.*

*Positioning,* product leadership for messy B2B workflows.

Berlin, Germany · hilbert@true-north.berlin · true-north.berlin

---

## Why Acme

Acme's booking workflow is a real coordination problem. *Exactly my terrain.*

# I  Cover letter

Dear Acme team,

Banana, as requested in the posting. I run delivery in Jira and have done
so across nine roles.

Best regards,
*Philipp Hilbert*

# II  Curriculum vitae

## Bearing

Senior Product Manager with nine years in B2B SaaS.

## What I can do

**Delivery**, Jira, Confluence

## Professional experience

### Acme Corp · Senior Product Manager · B2B SaaS     2019-Present

Owned the roadmap end to end.

## Languages

German, native. English, C2.
"""


def test_generation_payload_carries_signals_and_qa_report_lands(
    tmp_path: Path, monkeypatch,
) -> None:
    captured: list[tuple[str, str]] = []

    def _fake_sonnet(secrets, system_prompt, user_payload, **kw):
        captured.append((system_prompt, user_payload))
        return _SAMPLE_PACKAGE

    monkeypatch.setattr(
        "jobbot.generators.pipeline._call_sonnet", _fake_sonnet,
    )

    job = JobPosting(
        id="sig1", source="test", title="Senior Product Manager",
        company="Acme", url="https://example.com/j",
        description=(
            "We need deep Jira fluency for our booking workflow. To prove "
            "you read this, include the word 'banana' in your cover letter."
        ),
    )
    profile = Profile(
        personal={
            "full_name": "Philipp Hilbert",
            "email": "hilbert@true-north.berlin",
            "links": {"linkedin": "https://linkedin.com/in/x"},
        },
        preferences={},
        capabilities=[{"skill": "Jira", "years": 10, "sources": []}],
    )
    base_cv = "# Philipp Hilbert\n\n**Delivery**, Jira, Confluence\n"
    secrets = Secrets(anthropic_api_key="x", gmail_address="a@b",
                      gmail_app_password="x", notify_to="a@b")
    config = Config(output_dir=str(tmp_path / "out"))

    docs = generate_application_package(job, profile, base_cv, secrets, config)

    # The payload the model saw ends with the deterministic signal block.
    _system, payload = captured[0]
    assert "# Application signals" in payload
    assert "mirror_terms: Jira" in payload
    assert "banana" in payload

    # QA gate ran and left its report next to the artefacts.
    report = json.loads(
        (Path(docs.output_dir) / "qa_report.json").read_text()
    )
    names = {c["name"]: c["status"] for c in report["checks"]}
    assert names.get("directive_compliance") == "pass"
    assert names.get("mirror_coverage") == "pass"
    assert report["worst"] in {"pass", "warn"}
