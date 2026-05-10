"""User-journey e2e tests (non-live network).

These tests focus on user-facing outcomes rather than unit-level internals.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from jobbot.config import REPO_ROOT
from jobbot.profile_distiller.corpus_loader import MIN_DOC_CHARS, load_corpus


@pytest.mark.e2e
def test_profiles_are_present_readable_and_primary_is_set():
    """User story: my profile corpus exists, is readable, and has one PRIMARY profile."""
    corpus_root = REPO_ROOT / "data" / "corpus"
    cvs_dir = corpus_root / "cvs"

    assert corpus_root.exists(), "Missing data/corpus directory"
    assert cvs_dir.exists(), "Missing data/corpus/cvs directory"

    primary_files = sorted(p for p in cvs_dir.glob("PRIMARY_*") if p.is_file())
    assert len(primary_files) == 1, (
        f"Expected exactly one PRIMARY_ profile file, found {len(primary_files)}"
    )

    bundle = load_corpus(corpus_root)
    assert len(bundle.primary_cv) >= MIN_DOC_CHARS, (
        "PRIMARY profile was loaded but appears too short/low quality"
    )


@pytest.mark.e2e
@pytest.mark.xfail(strict=True, reason="Profile upload command not implemented yet")
def test_user_can_upload_profile_via_cli():
    """User story: can upload/add a profile via app command."""
    import jobbot.cli as cli_module

    # Expected UX target. This currently fails because command does not exist.
    rc = cli_module.main(["profile", "add", "data/corpus/cvs/example.md"])
    assert rc == 0


@pytest.mark.e2e
@pytest.mark.xfail(strict=True, reason="Profile remove command not implemented yet")
def test_user_can_remove_profile_via_cli():
    """User story: can remove a profile via app command."""
    import jobbot.cli as cli_module

    # Expected UX target. This currently fails because command does not exist.
    rc = cli_module.main(["profile", "remove", "data/corpus/cvs/example.md"])
    assert rc == 0
