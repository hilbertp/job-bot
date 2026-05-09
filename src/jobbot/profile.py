"""Profile + base CV loader."""
from __future__ import annotations

from pathlib import Path

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


def load_profile(path: Path | None = None) -> Profile:
    p = path or REPO_ROOT / "data" / "profile.yaml"
    if not p.exists():
        p = REPO_ROOT / "data" / "profile.example.yaml"
    return Profile.model_validate(yaml.safe_load(p.read_text()))


def load_base_cv(path: Path | None = None) -> str:
    p = path or REPO_ROOT / "data" / "base_cv.md"
    if not p.exists():
        p = REPO_ROOT / "data" / "base_cv.example.md"
    return p.read_text()
