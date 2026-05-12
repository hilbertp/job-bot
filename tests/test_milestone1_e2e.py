"""End-to-end regression tests for Milestone 1 (profile distillation pipeline).

Covers the acceptance criteria from MILESTONES.md §M1 without real network / LLM calls:

1. load_corpus — exactly one PRIMARY_ file → succeeds, correct bundle shape
2. load_corpus — zero PRIMARY_ files → CorpusError
3. load_corpus — two PRIMARY_ files → CorpusError
4. rebuild_compiled_profile — mocked LLM → writes profile.compiled.yaml with
   all required top-level keys and non-empty content
5. Idempotency: same corpus → identical corpus_fingerprint across two runs
6. DB schema — connect() on a fresh DB → all M1 enrichment columns present
7. CLI — `profile rebuild` and `profile fetch-website` sub-commands are registered
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIN_DOC_CHARS = 200
LARGE_TEXT = "A" * (MIN_DOC_CHARS + 10)  # just above the 200-char threshold

REQUIRED_PROFILE_KEYS = {
    "voice",
    "capabilities",
    "domains",
    "achievements",
    "seniority_signals",
    "languages",
    "compiled_at",
    "corpus_fingerprint",
}

# Minimal distiller YAML response that satisfies _normalize_profile
MOCK_LLM_YAML = """
voice:
  tone_descriptors: [direct, calm]
  sample_phrases: ["shipping fast", "product north star"]
  avoid_phrases: []
capabilities:
  - skill: Python
    years: 8
    sources: []
domains:
  - name: fintech
    depth: deep
    years: 5
achievements:
  - text: "Launched feature X"
    company: "ACME"
    metric: "3x revenue"
seniority_signals:
  title_progression: [Engineer, Senior, Staff]
  team_size_managed: 6
  scope_keywords: [cross-functional, global]
languages: [English, German]
"""


def _fake_corpus_root(tmp_path: Path) -> Path:
    """Create a minimal corpus directory with exactly one PRIMARY_ CV.

    Returns ``tmp_path / "corpus"`` so that output files written to ``tmp_path``
    are not inside the corpus root and don't skew the fingerprint between runs.
    """
    corpus = tmp_path / "corpus"
    cvs = corpus / "cvs"
    cvs.mkdir(parents=True)
    (cvs / "PRIMARY_my_cv.md").write_text(LARGE_TEXT, encoding="utf-8")
    return corpus


def _make_mock_anthropic_response(yaml_text: str) -> MagicMock:
    """Build a fake anthropic.messages.create() return value."""
    block = SimpleNamespace(type="text", text=yaml_text)
    msg = MagicMock()
    msg.content = [block]
    return msg


# ---------------------------------------------------------------------------
# 1. load_corpus — happy path
# ---------------------------------------------------------------------------

def test_load_corpus_happy_path(tmp_path: Path):
    from jobbot.profile_distiller.corpus_loader import load_corpus, CorpusBundle

    corpus_root = _fake_corpus_root(tmp_path)
    bundle = load_corpus(corpus_root)

    assert isinstance(bundle, CorpusBundle)
    assert len(bundle.primary_cv) >= MIN_DOC_CHARS
    assert isinstance(bundle.other_cvs, list)
    assert isinstance(bundle.cover_letters, list)
    assert isinstance(bundle.website_pages, list)


# ---------------------------------------------------------------------------
# 2. load_corpus — zero PRIMARY_ files → CorpusError
# ---------------------------------------------------------------------------

def test_load_corpus_no_primary(tmp_path: Path):
    from jobbot.profile_distiller.corpus_loader import load_corpus, CorpusError

    cvs = tmp_path / "cvs"
    cvs.mkdir()
    (cvs / "my_cv.md").write_text(LARGE_TEXT, encoding="utf-8")

    with pytest.raises(CorpusError, match="PRIMARY_"):
        load_corpus(tmp_path)


# ---------------------------------------------------------------------------
# 3. load_corpus — two PRIMARY_ files → CorpusError
# ---------------------------------------------------------------------------

def test_load_corpus_two_primaries(tmp_path: Path):
    from jobbot.profile_distiller.corpus_loader import load_corpus, CorpusError

    cvs = tmp_path / "cvs"
    cvs.mkdir()
    (cvs / "PRIMARY_cv_one.md").write_text(LARGE_TEXT, encoding="utf-8")
    (cvs / "PRIMARY_cv_two.md").write_text(LARGE_TEXT, encoding="utf-8")

    with pytest.raises(CorpusError, match="PRIMARY_"):
        load_corpus(tmp_path)


# ---------------------------------------------------------------------------
# 4. rebuild_compiled_profile — mocked LLM → writes full-schema YAML
# ---------------------------------------------------------------------------

def test_rebuild_compiled_profile_writes_schema(tmp_path: Path, monkeypatch):
    from jobbot.profile_distiller.distiller import rebuild_compiled_profile

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    corpus_root = _fake_corpus_root(tmp_path)
    output_path = tmp_path / "profile.compiled.yaml"

    mock_response = _make_mock_anthropic_response(MOCK_LLM_YAML)

    with patch("jobbot.profile_distiller.distiller.Anthropic") as mock_cls:
        instance = mock_cls.return_value
        instance.messages.create.return_value = mock_response

        result = rebuild_compiled_profile(
            corpus_root=corpus_root,
            output_path=output_path,
            secrets=None,  # will fall back to env; but Anthropic is mocked
        )

    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    data: dict[str, Any] = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "profile.compiled.yaml must be a YAML mapping"

    missing = REQUIRED_PROFILE_KEYS - data.keys()
    assert not missing, f"Missing top-level keys: {missing}"

    # Verify nested structure
    assert isinstance(data["voice"], dict)
    assert "tone_descriptors" in data["voice"]
    assert "sample_phrases" in data["voice"]
    assert "avoid_phrases" in data["voice"]
    assert isinstance(data["capabilities"], list)
    assert isinstance(data["domains"], list)
    assert isinstance(data["achievements"], list)
    assert isinstance(data["seniority_signals"], dict)
    assert isinstance(data["languages"], list)
    assert data["compiled_at"]         # non-empty ISO timestamp
    assert data["corpus_fingerprint"]  # non-empty SHA256 hex string


# ---------------------------------------------------------------------------
# 5. Idempotency: same corpus → identical corpus_fingerprint across two runs
# ---------------------------------------------------------------------------

def test_rebuild_corpus_fingerprint_stable(tmp_path: Path, monkeypatch):
    from jobbot.profile_distiller.distiller import rebuild_compiled_profile

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    corpus_root = _fake_corpus_root(tmp_path)

    mock_response = _make_mock_anthropic_response(MOCK_LLM_YAML)

    with patch("jobbot.profile_distiller.distiller.Anthropic") as mock_cls:
        instance = mock_cls.return_value
        instance.messages.create.return_value = mock_response

        out1 = tmp_path / "run1.yaml"
        rebuild_compiled_profile(corpus_root=corpus_root, output_path=out1, secrets=None)

        out2 = tmp_path / "run2.yaml"
        rebuild_compiled_profile(corpus_root=corpus_root, output_path=out2, secrets=None)

    d1 = yaml.safe_load(out1.read_text())
    d2 = yaml.safe_load(out2.read_text())

    assert d1["corpus_fingerprint"] == d2["corpus_fingerprint"], (
        "Identical corpus must produce identical fingerprints"
    )


def test_rebuild_compiled_profile_rejects_empty_placeholder_output(
    tmp_path: Path, monkeypatch,
):
    """A blank placeholder profile weakens every scorer call. Reject it
    instead of silently overwriting data/profile.compiled.yaml with junk."""
    from jobbot.profile_distiller.distiller import rebuild_compiled_profile

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    corpus_root = _fake_corpus_root(tmp_path)
    output_path = tmp_path / "profile.compiled.yaml"
    mock_response = _make_mock_anthropic_response(
        """
voice: {}
capabilities:
  - skill: ""
    years: 0
    sources: []
domains: []
achievements:
  - text: ""
    company: ""
    metric:
seniority_signals: {}
languages: []
"""
    )

    with patch("jobbot.profile_distiller.distiller.Anthropic") as mock_cls:
        instance = mock_cls.return_value
        instance.messages.create.return_value = mock_response

        with pytest.raises(ValueError, match="no usable capabilities"):
            rebuild_compiled_profile(
                corpus_root=corpus_root,
                output_path=output_path,
                secrets=None,
            )

    assert not output_path.exists()


# ---------------------------------------------------------------------------
# 6. DB schema — all M1 enrichment columns present after connect()
# ---------------------------------------------------------------------------

EXPECTED_ENRICHMENT_COLUMNS = {
    "description_full",
    "description_scraped",
    "description_word_count",
    "seniority",
    "salary_text",
    "apply_email",
    "score_breakdown_json",
    "enriched_at",
    "scored_at",
}


def test_state_enrichment_columns_exist(tmp_path: Path, monkeypatch):
    db = tmp_path / "test_m1.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)

    from jobbot.state import connect

    with connect(db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(seen_jobs)")}

    missing = EXPECTED_ENRICHMENT_COLUMNS - cols
    assert not missing, f"Missing enrichment columns in seen_jobs: {missing}"


# ---------------------------------------------------------------------------
# 7. CLI — profile sub-commands are registered and dispatched correctly
# ---------------------------------------------------------------------------

def test_cli_profile_subcommands_registered():
    """Ensure both profile sub-commands route to their handlers via main()."""
    import jobbot.cli as cli_module

    rebuild_calls: list[str] = []
    fetch_calls: list[str] = []

    def fake_rebuild(_args) -> int:
        rebuild_calls.append("called")
        return 0

    def fake_fetch(_args) -> int:
        fetch_calls.append("called")
        return 0

    with (
        patch.object(cli_module, "cmd_profile_rebuild", side_effect=fake_rebuild),
        patch.object(cli_module, "cmd_profile_fetch_website", side_effect=fake_fetch),
    ):
        cli_module.main(["profile", "rebuild"])
        cli_module.main(["profile", "fetch-website"])

    assert rebuild_calls == ["called"], "profile rebuild sub-command not dispatched"
    assert fetch_calls == ["called"], "profile fetch-website sub-command not dispatched"
