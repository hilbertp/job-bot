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
    user_facts: list[str] = Field(default_factory=list)
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


def append_user_fact(
    fact: str,
    *,
    profile_path: Path | None = None,
) -> Path:
    """Append a single fact to the `user_facts` list in `data/profile.yaml`.

    Used by the Stage-2 disagree-and-rescore flow: when the user writes
    a comment to challenge a low score, that comment is also persisted
    as a durable fact about the candidate so ALL future scoring runs
    pick it up (not just the one job being rescored).

    Idempotent, duplicate facts (case-insensitive, whitespace-collapsed)
    are not appended a second time.

    The write is performed against the RAW user-edited `profile.yaml`
    (not the merged `profile.compiled.yaml`), so the distiller can be
    rerun without trampling these facts.

    Returns the path written.
    """
    fact = (fact or "").strip()
    if not fact:
        raise ValueError("append_user_fact: refusing to append empty fact")

    p = profile_path or REPO_ROOT / "data" / "profile.yaml"
    if not p.exists():
        # Don't silently fall back to profile.example.yaml, that would write
        # the user's private fact into a shipped example file.
        raise FileNotFoundError(f"profile.yaml not found at {p}")

    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        data = {}
    facts = data.get("user_facts") or []
    if not isinstance(facts, list):
        facts = []

    def _normalize(s: str) -> str:
        return " ".join(s.split()).casefold()

    if _normalize(fact) in {_normalize(str(f)) for f in facts if f}:
        return p  # already present, no-op

    facts.append(fact)
    data["user_facts"] = facts
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return p


def apply_profile_patch(
    patch: dict,
    *,
    profile_path: Path | None = None,
) -> dict:
    """Apply a structured patch produced by
    `scoring.extract_profile_updates_from_feedback` to `data/profile.yaml`.

    Recognised keys on `patch`:
      - "add_to_must_have_skills": list[str]
      - "add_to_nice_to_have_skills": list[str]
      - "add_to_user_facts": list[str]
      - "preference_updates": dict[str, Any], only writes keys already
        present on the profile's preferences dict (no schema drift).

    Returns a summary of what was *actually* applied (after dedup/skipping
    pre-existing entries) so the caller can show "learned X, Y" in the UI.

    Idempotent: calling twice with the same patch produces one new entry,
    not two.
    """
    p = profile_path or REPO_ROOT / "data" / "profile.yaml"
    if not p.exists():
        raise FileNotFoundError(f"profile.yaml not found at {p}")

    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        data = {}

    def _normalize(s: Any) -> str:
        return " ".join(str(s).split()).casefold()

    summary: dict[str, Any] = {
        "added_must_have_skills": [],
        "added_nice_to_have_skills": [],
        "added_facts": [],
        "updated_preferences": {},
    }

    for src_key, dest_key, summary_key in [
        ("add_to_must_have_skills", "must_have_skills", "added_must_have_skills"),
        ("add_to_nice_to_have_skills", "nice_to_have_skills", "added_nice_to_have_skills"),
    ]:
        items = patch.get(src_key) or []
        if not isinstance(items, list):
            continue
        existing = data.get(dest_key) or []
        if not isinstance(existing, list):
            existing = []
        existing_norm = {_normalize(x) for x in existing if x}
        for raw in items:
            item = str(raw).strip()
            if not item or _normalize(item) in existing_norm:
                continue
            existing.append(item)
            existing_norm.add(_normalize(item))
            summary[summary_key].append(item)
        data[dest_key] = existing

    new_facts = patch.get("add_to_user_facts") or []
    if isinstance(new_facts, list):
        facts = data.get("user_facts") or []
        if not isinstance(facts, list):
            facts = []
        facts_norm = {_normalize(f) for f in facts if f}
        for raw in new_facts:
            fact = str(raw).strip()
            if not fact or _normalize(fact) in facts_norm:
                continue
            facts.append(fact)
            facts_norm.add(_normalize(fact))
            summary["added_facts"].append(fact)
        data["user_facts"] = facts

    pref_updates = patch.get("preference_updates") or {}
    if isinstance(pref_updates, dict):
        prefs = data.get("preferences") or {}
        if not isinstance(prefs, dict):
            prefs = {}
        for k, v in pref_updates.items():
            # Only write keys that already exist on the profile so the
            # extractor can't accidentally introduce new schema fields.
            if k in prefs and prefs[k] != v:
                prefs[k] = v
                summary["updated_preferences"][k] = v
        data["preferences"] = prefs

    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return summary


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
    the file is unreadable. The scorer catches this and refuses to score, callers must never see a silent fallback to a thinner profile.
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
            f"no PRIMARY_ CV in {cvs_dir}, add exactly one PRIMARY_* file "
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
