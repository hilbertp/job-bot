"""Two-stage matcher: cheap heuristic prefilter, then Claude Haiku for the survivors."""
from __future__ import annotations

import json
import re
from pathlib import Path

from anthropic import Anthropic

from .config import REPO_ROOT, Config, Secrets
from .models import JobPosting, ScoreResult
from .profile import Profile

PROMPT_PATH = REPO_ROOT / "prompts" / "match_score.md"


def _contains_keyword(text: str, keyword: str) -> bool:
    """Match standalone keywords to avoid false positives like 'intern' in 'internal'."""
    needle = (keyword or "").strip().lower()
    if not needle:
        return False
    if " " in needle:
        return needle in text
    if needle.isalnum():
        return re.search(rf"\b{re.escape(needle)}\b", text) is not None
    return needle in text


def _parse_score_json(text: str) -> dict:
    """Parse model output that may include markdown fences around JSON."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model response is not a JSON object")
    return data


def passes_heuristic(job: JobPosting, profile: Profile) -> tuple[bool, str]:
    """Cheap, no-LLM filter. Returns (passes, reason_if_not)."""
    text = (job.description + " " + job.title).lower()

    # Deal-breaker keywords
    for kw in profile.deal_breakers.get("keywords", []):
        if _contains_keyword(text, kw):
            return False, f"deal-breaker keyword: {kw}"

    # Industry deal-breakers (tag-based)
    for ind in profile.deal_breakers.get("industries", []):
        if _contains_keyword(text, ind):
            return False, f"deal-breaker industry: {ind}"

    # Remote requirement
    if profile.preferences.get("remote") and profile.deal_breakers.get("on_site_only"):
        if any(s in text for s in ["on-site only", "on site only", "vor ort"]):
            return False, "on-site only role"

    # At least one must-have skill mentioned
    must = [s.lower() for s in profile.must_have_skills]
    if must and not any(_contains_keyword(text, s) for s in must):
        return False, "no must-have skill mentioned"

    return True, ""


def llm_score(
    job: JobPosting,
    profile: Profile,
    secrets: Secrets,
    cv_markdown: str | None = None,
) -> ScoreResult:
    """Ask Haiku for a 0-100 fit score. Returns a ScoreResult.

    If `cv_markdown` is provided (the full base CV), include it in the payload
    so the model can score against actual experience and tooling, not just the
    thin profile_summary.
    """
    client = Anthropic(api_key=secrets.anthropic_api_key)
    prompt = PROMPT_PATH.read_text()
    payload: dict = {
        "job_title": job.title,
        "company": job.company,
        "job_description": job.description[:8000],  # cap input
        "profile_summary": {
            "must_have_skills": profile.must_have_skills,
            "nice_to_have_skills": profile.nice_to_have_skills,
            "preferences": profile.preferences,
        },
    }
    if cv_markdown:
        payload["cv_markdown"] = cv_markdown[:12000]
    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        system=prompt,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    data = _parse_score_json(text)
    score = int(data["score"])
    reason = str(data.get("reason", ""))

    # Prefer a transparent breakdown string when the model provides criterion scores.
    breakdown = data.get("breakdown")
    if isinstance(breakdown, dict):
        def _to_int(key: str) -> int | None:
            val = breakdown.get(key)
            try:
                return int(val)
            except (TypeError, ValueError):
                return None

        role = _to_int("role_match")
        skills = _to_int("skills_match")
        loc = _to_int("location_remote_fit")
        seniority = _to_int("seniority_fit")
        if all(v is not None for v in (role, skills, loc, seniority)):
            reason = (
                f"role={role}, skills={skills}, location={loc}, seniority={seniority}; "
                f"{reason}"
            )

    return ScoreResult(score=score, reason=reason)
