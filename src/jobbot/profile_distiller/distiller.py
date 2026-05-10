"""Call Claude Sonnet once with the full corpus to produce
`data/profile.compiled.yaml`.

PRD §7.4 FR-PRO-02.

Output schema (the LLM must produce exactly this shape):

    voice:
      tone_descriptors: [str, ...]   # e.g. "calm", "direct", "earned-confidence"
      sample_phrases:   [str, ...]   # 5-10 phrases the candidate actually uses
      avoid_phrases:    [str, ...]   # filler we know he never writes

    capabilities:
      - skill: str
        years: int
        sources: [path-relative, ...]   # which CVs mention it

    domains:
      - name: str            # e.g. "fintech", "DeFi", "security"
        depth: low | mid | deep
        years: int

    achievements:
      - text: str            # verbatim quote from a CV / CL
        company: str
        metric: str | null

    seniority_signals:
      title_progression: [str, ...]
      team_size_managed: int | null
      scope_keywords:    [str, ...]

    languages: [str, ...]    # claimed in CVs

    compiled_at: ISO timestamp
    corpus_fingerprint: str  # hash of (file paths + sizes), for staleness detection

Hard rules baked into the prompt:
- The PRIMARY CV is authoritative for facts. Conflicts with non-primary CVs
  resolve in favor of PRIMARY.
- Cover letters contribute ONLY to `voice.*`, never to `capabilities` or
  `achievements`.
- Website pages contribute to `voice` and `domains` but never override CV facts.
- Never invent. If a field cannot be filled, write `null` or `[]`.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from anthropic import Anthropic

from ..config import REPO_ROOT, Secrets
from .corpus_loader import CorpusBundle, load_corpus


SONNET_MODEL = "claude-sonnet-4-6"


def _strip_fenced_yaml(text: str) -> str:
  """PRD §7.4 FR-PRO-02: accept YAML returned inside markdown fences."""
  cleaned = (text or "").strip()
  if cleaned.startswith("```"):
    lines = cleaned.splitlines()
    if len(lines) >= 3 and lines[-1].strip().startswith("```"):
      cleaned = "\n".join(lines[1:-1]).strip()
  return cleaned


def _relative_to_repo(path: Path) -> str:
  """PRD §7.4 FR-PRO-02: persist source paths as repository-relative strings."""
  try:
    return str(path.relative_to(REPO_ROOT))
  except ValueError:
    return str(path)


def _corpus_fingerprint(corpus_root: Path) -> str:
  """PRD §7.4 FR-PRO-02: hash corpus file paths and sizes for staleness checks."""
  parts: list[str] = []
  for path in sorted(corpus_root.rglob("*"), key=lambda p: str(p).lower()):
    if not path.is_file() or any(part.startswith(".") for part in path.parts):
      continue
    rel = _relative_to_repo(path)
    parts.append(f"{rel}:{path.stat().st_size}")
  return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _bundle_for_prompt(bundle: CorpusBundle) -> dict[str, Any]:
  """PRD §7.4 FR-PRO-02: construct one prompt payload containing full corpus."""
  return {
    "primary_cv": bundle.primary_cv,
    "other_cvs": [
      {"path": _relative_to_repo(doc.path), "text": doc.text}
      for doc in bundle.other_cvs
    ],
    "cover_letters": [
      {"path": _relative_to_repo(doc.path), "text": doc.text}
      for doc in bundle.cover_letters
    ],
    "website_pages": [
      {"path": _relative_to_repo(doc.path), "text": doc.text}
      for doc in bundle.website_pages
    ],
  }


def _ensure_list_str(value: Any) -> list[str]:
  """PRD §7.4 FR-PRO-02: normalize list-of-string fields."""
  if not isinstance(value, list):
    return []
  out: list[str] = []
  for item in value:
    if item is None:
      continue
    out.append(str(item))
  return out


def _normalize_profile(data: dict[str, Any]) -> dict[str, Any]:
  """PRD §7.4 FR-PRO-02: force output into required schema with safe defaults."""
  voice = data.get("voice") if isinstance(data.get("voice"), dict) else {}
  seniority = (
    data.get("seniority_signals")
    if isinstance(data.get("seniority_signals"), dict)
    else {}
  )

  capabilities_in = data.get("capabilities") if isinstance(data.get("capabilities"), list) else []
  capabilities: list[dict[str, Any]] = []
  for item in capabilities_in:
    if not isinstance(item, dict):
      continue
    years_value = item.get("years")
    try:
      years = int(years_value)
    except (TypeError, ValueError):
      years = 0
    capabilities.append(
      {
        "skill": str(item.get("skill", "")),
        "years": years,
        "sources": _ensure_list_str(item.get("sources", [])),
      }
    )

  domains_in = data.get("domains") if isinstance(data.get("domains"), list) else []
  domains: list[dict[str, Any]] = []
  for item in domains_in:
    if not isinstance(item, dict):
      continue
    years_value = item.get("years")
    try:
      years = int(years_value)
    except (TypeError, ValueError):
      years = 0
    depth = str(item.get("depth", "low"))
    if depth not in {"low", "mid", "deep"}:
      depth = "low"
    domains.append({"name": str(item.get("name", "")), "depth": depth, "years": years})

  achievements_in = data.get("achievements") if isinstance(data.get("achievements"), list) else []
  achievements: list[dict[str, Any]] = []
  for item in achievements_in:
    if not isinstance(item, dict):
      continue
    metric = item.get("metric")
    achievements.append(
      {
        "text": str(item.get("text", "")),
        "company": str(item.get("company", "")),
        "metric": None if metric in (None, "") else str(metric),
      }
    )

  team_size_value = seniority.get("team_size_managed")
  try:
    team_size_managed: int | None = int(team_size_value) if team_size_value is not None else None
  except (TypeError, ValueError):
    team_size_managed = None

  return {
    "voice": {
      "tone_descriptors": _ensure_list_str(voice.get("tone_descriptors", [])),
      "sample_phrases": _ensure_list_str(voice.get("sample_phrases", [])),
      "avoid_phrases": _ensure_list_str(voice.get("avoid_phrases", [])),
    },
    "capabilities": capabilities,
    "domains": domains,
    "achievements": achievements,
    "seniority_signals": {
      "title_progression": _ensure_list_str(seniority.get("title_progression", [])),
      "team_size_managed": team_size_managed,
      "scope_keywords": _ensure_list_str(seniority.get("scope_keywords", [])),
    },
    "languages": _ensure_list_str(data.get("languages", [])),
  }


def _call_sonnet(corpus_payload: dict[str, Any], api_key: str) -> dict[str, Any]:
  """PRD §7.4 FR-PRO-02: perform a single Sonnet call for full-profile distillation."""
  system_prompt = (
    "You distill a candidate profile from supplied corpus documents. "
    "Return YAML only, no markdown fences, with exact top-level keys: "
    "voice, capabilities, domains, achievements, seniority_signals, languages. "
    "Rules: PRIMARY CV is authoritative for facts. Cover letters contribute only to voice.*. "
    "Website pages contribute to voice/domains only and never override CV facts. "
    "Never invent facts; use null or [] when unknown."
  )
  user_payload = json.dumps(corpus_payload)

  client = Anthropic(api_key=api_key)
  msg = client.messages.create(
    model=SONNET_MODEL,
    max_tokens=3500,
    system=system_prompt,
    messages=[{"role": "user", "content": user_payload}],
  )
  text = "".join(block.text for block in msg.content if block.type == "text")
  parsed = yaml.safe_load(_strip_fenced_yaml(text))
  if not isinstance(parsed, dict):
    raise ValueError("Distiller model output was not a YAML object")
  return parsed


def rebuild_compiled_profile(
    corpus_root: Path | None = None,
    output_path: Path | None = None,
    secrets: Secrets | None = None,
) -> Path:
    """Read the corpus, call Sonnet, write `profile.compiled.yaml`. Return path.

    Defaults: corpus_root = REPO_ROOT/data/corpus,
              output_path = REPO_ROOT/data/profile.compiled.yaml.
    Idempotent: same corpus → same output (modulo `compiled_at` timestamp).
    """
    corpus_root = corpus_root or (REPO_ROOT / "data" / "corpus")
    output_path = output_path or (REPO_ROOT / "data" / "profile.compiled.yaml")
    api_key = secrets.anthropic_api_key if secrets is not None else os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
      raise ValueError("ANTHROPIC_API_KEY is required for profile distillation")

    bundle = load_corpus(corpus_root)
    payload = _bundle_for_prompt(bundle)
    distilled = _call_sonnet(payload, api_key=api_key)
    normalized = _normalize_profile(distilled)
    normalized["compiled_at"] = datetime.now(tz=timezone.utc).isoformat()
    normalized["corpus_fingerprint"] = _corpus_fingerprint(corpus_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(normalized, sort_keys=False, allow_unicode=False)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path
