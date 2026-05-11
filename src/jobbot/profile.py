"""Profile + base CV loader."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .config import REPO_ROOT


class Profile(BaseModel):
    personal: dict
    preferences: dict
    deal_breakers: dict = Field(default_factory=dict)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    screener_defaults: dict[str, str] = Field(default_factory=dict)
    voice: dict = Field(default_factory=dict)
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    domains: list[dict[str, Any]] = Field(default_factory=list)
    achievements: list[dict[str, Any]] = Field(default_factory=list)
    seniority_signals: dict = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    compiled_at: str | None = None
    corpus_fingerprint: str | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """PRD §7.4 FR-PRO-04: merge compiled profile with user overrides."""
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_profile(path: Path | None = None) -> Profile:
    """PRD §7.4 FR-PRO-04: load and merge profile.yaml with profile.compiled.yaml."""
    p = path or REPO_ROOT / "data" / "profile.yaml"
    if not p.exists():
        p = REPO_ROOT / "data" / "profile.example.yaml"

    compiled_path = REPO_ROOT / "data" / "profile.compiled.yaml"
    compiled_data: dict[str, Any] = {}
    if compiled_path.exists():
        loaded = yaml.safe_load(compiled_path.read_text()) or {}
        if isinstance(loaded, dict):
            compiled_data = loaded

    profile_data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(profile_data, dict):
        profile_data = {}

    merged = _deep_merge(compiled_data, profile_data)
    return Profile.model_validate(merged)


def load_base_cv(path: Path | None = None) -> str:
    p = path or REPO_ROOT / "data" / "base_cv.md"
    if not p.exists():
        p = REPO_ROOT / "data" / "base_cv.example.md"
    return p.read_text()


def load_primary_cv(corpus_root: Path | None = None) -> str:
    """PRD §7.5 FR-SCO-01 (FR-SCO-CV gate): return the plaintext of the single
    file under `data/corpus/cvs/` whose name starts with `PRIMARY_`.

    Supports .pdf / .docx / .md / .txt via the same readers as corpus_loader.
    Raises FileNotFoundError if zero or multiple PRIMARY_ files exist, or if
    the file is unreadable. The scorer catches this and refuses to score —
    callers must never see a silent fallback to a thinner profile.
    """
    from .profile_distiller.corpus_loader import (
        CorpusError, SUPPORTED_SUFFIXES, _read_doc,
    )

    cvs_dir = (corpus_root or REPO_ROOT / "data" / "corpus") / "cvs"
    if not cvs_dir.exists():
        raise FileNotFoundError(f"corpus CV directory missing: {cvs_dir}")

    candidates = [
        p for p in cvs_dir.iterdir()
        if p.is_file()
        and p.name.startswith("PRIMARY_")
        and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    if not candidates:
        raise FileNotFoundError(
            f"no PRIMARY_ CV in {cvs_dir} — add exactly one PRIMARY_* file "
            f"(.pdf/.docx/.md/.txt)"
        )
    if len(candidates) > 1:
        names = ", ".join(sorted(p.name for p in candidates))
        raise FileNotFoundError(
            f"multiple PRIMARY_ CV files in {cvs_dir}: {names}. Keep exactly one."
        )

    try:
        text = _read_doc(candidates[0])
    except CorpusError as exc:
        raise FileNotFoundError(f"could not extract text from {candidates[0]}: {exc}") from exc
    text = (text or "").strip()
    if not text:
        raise FileNotFoundError(f"primary CV {candidates[0]} extracted to empty text")
    return text
