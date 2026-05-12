"""Outbound applications MUST carry the current business return address.

Every application package the bot generates derives its contact line and
cover-letter sign-off from two sources of truth:

  - data/profile.yaml — `personal.email`, passed to Sonnet as YAML
  - data/base_cv.md   — the contact line in the H1 header block

If either file silently drifts back to a retired email (e.g. after a
restore from backup, a corrupted edit, an LLM auto-suggestion accepted
by mistake, or a forgotten `git checkout` of an old file), every send
that follows would route replies to the wrong inbox. That is the bug
this test exists to prevent.

The test is scoped to the local installation: when the personal source
files are absent (fresh checkout, CI without secrets), it skips. When
the files exist (the operator's actual working tree), it MUST pass.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from jobbot.config import REPO_ROOT

# Single source of truth for "this is the right return address right now."
# Add entries to STALE_EMAILS whenever a previously-used address is
# retired; remove only after confirming no live applications still rely
# on it.
CURRENT_RETURN_ADDRESS = "hilbert@true-north.berlin"
STALE_EMAILS = [
    "philipp@projuncta.com",
]

PROFILE_PATH = REPO_ROOT / "data" / "profile.yaml"
BASE_CV_PATH = REPO_ROOT / "data" / "base_cv.md"


@pytest.mark.skipif(
    not PROFILE_PATH.exists(),
    reason="data/profile.yaml not present (fresh checkout / CI without secrets)",
)
def test_profile_yaml_uses_current_return_address() -> None:
    content = PROFILE_PATH.read_text()
    assert CURRENT_RETURN_ADDRESS in content, (
        f"data/profile.yaml must contain {CURRENT_RETURN_ADDRESS}. "
        f"Without it, every generated application carries the wrong "
        f"return address. Update personal.email."
    )


@pytest.mark.skipif(
    not PROFILE_PATH.exists(),
    reason="data/profile.yaml not present",
)
def test_profile_yaml_does_not_carry_any_stale_email() -> None:
    content = PROFILE_PATH.read_text()
    for stale in STALE_EMAILS:
        assert stale not in content, (
            f"data/profile.yaml still contains the retired email {stale!r}. "
            f"Replace with {CURRENT_RETURN_ADDRESS}. Replies to the old "
            f"address may go to an inbox you no longer monitor."
        )


@pytest.mark.skipif(
    not BASE_CV_PATH.exists(),
    reason="data/base_cv.md not present",
)
def test_base_cv_uses_current_return_address() -> None:
    content = BASE_CV_PATH.read_text()
    assert CURRENT_RETURN_ADDRESS in content, (
        f"data/base_cv.md must contain {CURRENT_RETURN_ADDRESS} in the "
        f"header contact line. The LLM copies the contact line verbatim "
        f"into every tailored CV."
    )


@pytest.mark.skipif(
    not BASE_CV_PATH.exists(),
    reason="data/base_cv.md not present",
)
def test_base_cv_does_not_carry_any_stale_email() -> None:
    content = BASE_CV_PATH.read_text()
    for stale in STALE_EMAILS:
        assert stale not in content, (
            f"data/base_cv.md still contains the retired email {stale!r}. "
            f"Replace with {CURRENT_RETURN_ADDRESS}."
        )


@pytest.mark.skipif(
    not (PROFILE_PATH.exists() and BASE_CV_PATH.exists()),
    reason="profile.yaml or base_cv.md not present",
)
def test_application_package_prompt_payload_carries_current_return_address() -> None:
    """End-to-end: the actual user_payload that goes to Sonnet for the
    application package must contain the current email. This is the
    closest thing to a runtime guarantee — if profile + base_cv are both
    correct, the LLM sees the right address in both the YAML profile and
    the Markdown CV block of its prompt."""
    from jobbot.models import JobPosting
    from jobbot.profile import load_profile

    profile = load_profile()
    base_cv = BASE_CV_PATH.read_text()

    # Mirror the payload construction in generators.pipeline.generate_application_package
    job = JobPosting(
        id="payload-check", source="fake", title="PM", company="ACME",
        url="https://example.com/job", description="...",
    )
    payload = (
        f"# Job\n\n## {job.title} — {job.company}\n\n{job.description}\n\n"
        f"# Profile\n\n```yaml\n{profile.model_dump_json(indent=2)}\n```\n\n"
        f"# Base CV\n\n{base_cv}\n"
    )

    assert CURRENT_RETURN_ADDRESS in payload, (
        f"The LLM prompt payload (profile.yaml + base_cv.md combined) does "
        f"NOT contain {CURRENT_RETURN_ADDRESS}. The bot WILL send "
        f"applications with the wrong return address. Fix profile + CV before "
        f"running `jobbot apply` again."
    )
    for stale in STALE_EMAILS:
        assert stale not in payload, (
            f"The LLM prompt payload contains the retired email {stale!r}. "
            f"Recruiters will reply to an inbox you may no longer monitor."
        )
