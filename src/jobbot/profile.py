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
