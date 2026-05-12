"""Two-stage matcher: cheap heuristic prefilter, then Claude Sonnet for the survivors.

PRD §7.5 FR-SCO-01..05. The scorer enforces three hard preconditions before
calling the LLM. If any fail, it raises `CannotScore` with the reason —
callers persist this as a `cannot_score:*` status instead of a numeric score:
  1. enrichment ran AND the body it stored is >= MIN_BODY_WORDS (100).
     A long *listing-card* description is not enough — a posting can carry
     a 250-word teaser on the search page while its detail body was never
     fetched. The caller must therefore pass `description_scraped=True`
     explicitly, and word_count is recomputed against `job.description`.
  2. primary CV loaded successfully from data/corpus/cvs/PRIMARY_*.
  3. (caller-provided) Anthropic API key present

Cost note: this routes to claude-sonnet-4-6 (max_tokens=800). At expected
volume (~120 postings/day) that's ~€150-200/mo of LLM spend versus ~€40/mo
on the prior Haiku setup — roughly 5x per call. The user explicitly
approved this trade-off in exchange for substantially more accurate
scoring, since Haiku was clustering most matches in a narrow 60-80 band
and missing real signal in the top tier.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from anthropic import Anthropic

from .config import REPO_ROOT, Config, Secrets
from .models import JobPosting, ScoreResult
from .profile import Profile, load_primary_cv

PROMPT_PATH = REPO_ROOT / "prompts" / "match_score.md"
PROFILE_YAML_PATH = REPO_ROOT / "data" / "profile.yaml"

# PRD §7.5 FR-SCO-01: a posting needs a substantive body before scoring.
# Below this threshold the description is just a snippet (LinkedIn search
# previews, Stepstone teaser cards) and the scorer would hallucinate.
MIN_BODY_WORDS = 100

# Cap the primary CV at 18k chars (~3-4k tokens). Sonnet handles much more,
# but the marginal context past this point is mostly formatting noise.
_PRIMARY_CV_CAP = 18000
# Cap the job body at 12k chars (~2k tokens). Postings rarely exceed this
# and trimming long company-boilerplate tails is a feature, not a bug.
_JOB_BODY_CAP = 12000


class CannotScore(Exception):
    """A hard precondition for LLM scoring is not satisfied. The caller must
    persist `status='cannot_score:<reason>'` rather than calling the LLM."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

# Deal-breaker keywords describing role seniority. When the job *title* clearly
# signals a senior+ role, these are scoped to the title only — a "Junior Team
# Lead" hiring contact in the body of a Senior PM posting should not filter it.
_SENIORITY_DEAL_BREAKERS = {
    "junior", "jr", "jr.",
    "entry level", "entry-level",
    "intern", "internship", "praktikum", "praktikant",
    "werkstudent", "student", "trainee",
}
_SENIOR_TITLE_RE = re.compile(
    r"\b(senior|sr\.?|lead|staff|principal|head|director|chief|vp)\b",
    re.IGNORECASE,
)


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
    title_lower = (job.title or "").lower()
    text = ((job.description or "") + " " + (job.title or "")).lower()
    title_is_senior = bool(_SENIOR_TITLE_RE.search(job.title or ""))

    # Deal-breaker keywords. Seniority-related keywords are scoped to the title
    # only when the title signals a senior+ role — see _SENIORITY_DEAL_BREAKERS.
    for kw in profile.deal_breakers.get("keywords", []):
        kw_norm = (kw or "").strip().lower()
        scope = title_lower if (kw_norm in _SENIORITY_DEAL_BREAKERS and title_is_senior) else text
        if _contains_keyword(scope, kw_norm):
            return False, f"deal-breaker keyword: {kw}"

    # Industry deal-breakers (tag-based)
    for ind in profile.deal_breakers.get("industries", []):
        if _contains_keyword(text, ind):
            return False, f"deal-breaker industry: {ind}"

    # Remote/on-site is not a heuristic deal-breaker. Substring matches like the
    # German "vor Ort" are too generic ("Termine vor Ort", "Kunden vor Ort",
    # "Teams vor Ort in Deutschland") and produced false positives across
    # hybrid/remote-friendly postings. The LLM scorer judges remote fit with
    # the full job text + CV in scope.

    # At least one must-have skill mentioned
    must = [s.lower() for s in profile.must_have_skills]
    if must and not any(_contains_keyword(text, s) for s in must):
        return False, "no must-have skill mentioned"

    return True, ""


def _build_user_message(
    job: JobPosting,
    profile: Profile,
    base_cv: str,
    *,
    cv_section_label: str = "Primary CV (source of truth)",
    extra_section: tuple[str, str] | None = None,
) -> str:
    """PRD §7.5 FR-SCO-01: assemble the scoring prompt's user message in the
    exact ordering the rubric expects:
      1. Primary CV (source of truth)   ← labelled per `cv_section_label`
      2. Compiled profile (yaml)
      3. Hard preferences (from data/profile.yaml)
      4. Job description
      5. Job metadata

    For the Stage-3 rescore, callers substitute the tailored CV markdown for
    `base_cv` (with a different label) and pass `extra_section` to inject
    a "Cover letter (tailored)" block between profile and job description.
    """
    compiled = {
        "must_have_skills": profile.must_have_skills,
        "nice_to_have_skills": profile.nice_to_have_skills,
        "capabilities": profile.capabilities,
        "domains": profile.domains,
        "achievements": profile.achievements,
        "seniority_signals": profile.seniority_signals,
        "languages": profile.languages,
    }
    hard_prefs = {
        "preferences": profile.preferences,
        "deal_breakers": profile.deal_breakers,
    }
    # Use yaml.safe_dump for sections 2/3 — model parses YAML reliably and it
    # reads better in the prompt than escaped JSON.
    compiled_yaml = yaml.safe_dump(compiled, sort_keys=False, allow_unicode=True).strip()
    hard_prefs_yaml = yaml.safe_dump(hard_prefs, sort_keys=False, allow_unicode=True).strip()

    metadata = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "url": str(job.url),
    }
    metadata_yaml = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()

    body = (job.description or "").strip()[:_JOB_BODY_CAP]
    cv = base_cv.strip()[:_PRIMARY_CV_CAP]

    extra_block = ""
    if extra_section:
        title, text = extra_section
        extra_block = f"# {title}\n\n{text.strip()}\n\n"

    return (
        f"# {cv_section_label}\n\n"
        f"{cv}\n\n"
        "# Compiled profile (yaml)\n\n"
        "```yaml\n"
        f"{compiled_yaml}\n"
        "```\n\n"
        "# Hard preferences (yaml)\n\n"
        "```yaml\n"
        f"{hard_prefs_yaml}\n"
        "```\n\n"
        f"{extra_block}"
        "# Job description\n\n"
        f"{body}\n\n"
        "# Job metadata\n\n"
        "```yaml\n"
        f"{metadata_yaml}\n"
        "```\n"
    )


def _invoke_scorer(
    secrets: Secrets,
    user_message: str,
    *,
    run_id: int | None = None,
    phase: str = "score_base",
    job_id: str | None = None,
) -> ScoreResult:
    """Shared LLM call + response parsing for both base and tailored scoring."""
    client = Anthropic(api_key=secrets.anthropic_api_key)
    prompt = PROMPT_PATH.read_text()
    model = "claude-sonnet-4-6"
    msg = client.messages.create(
        model=model,
        max_tokens=800,
        system=prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    _record_usage_if_present(msg, run_id=run_id, phase=phase, job_id=job_id, model=model)
    text = "".join(b.text for b in msg.content if b.type == "text")
    data = _parse_score_json(text)
    score = int(data["score"])
    reason = str(data.get("reason", ""))

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


def _usage_int(usage: object, name: str) -> int:
    if isinstance(usage, dict):
        value = usage.get(name, 0)
    else:
        value = getattr(usage, name, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record_usage_if_present(
    msg: object,
    *,
    run_id: int | None,
    phase: str,
    job_id: str | None,
    model: str,
) -> None:
    if run_id is None:
        return
    usage = getattr(msg, "usage", None)
    if usage is None:
        return
    from .state import connect, record_llm_usage

    with connect() as conn:
        record_llm_usage(
            conn,
            run_id=run_id,
            phase=phase,
            job_id=job_id,
            model=model,
            input_tokens=_usage_int(usage, "input_tokens"),
            output_tokens=_usage_int(usage, "output_tokens"),
            cache_creation_input_tokens=_usage_int(usage, "cache_creation_input_tokens"),
            cache_read_input_tokens=_usage_int(usage, "cache_read_input_tokens"),
        )


def llm_score_tailored(
    job: JobPosting,
    profile: Profile,
    secrets: Secrets,
    tailored_cv_md: str,
    tailored_cover_letter_md: str,
    *,
    run_id: int | None = None,
    phase: str = "tailored_rescore",
) -> ScoreResult:
    """Score the posting AGAIN using the tailored CV + cover letter the
    generator produced for it. Returns a ScoreResult — does not touch the
    DB. Caller persists via `update_score_tailored`.

    The tailored CV replaces the base-CV slot (section 1 of the prompt),
    and the tailored cover letter is injected as a new section between the
    hard preferences and the job description. Both are explicitly labelled
    "(tailored)" so the model knows it's evaluating an actual submission
    rather than the candidate's background.

    No body-length precondition here — by definition the caller is invoking
    this after Stage-3 generation succeeded, so the body must already pass.
    """
    if not (tailored_cv_md or "").strip():
        raise CannotScore("no_tailored_cv: empty tailored CV markdown")
    if not (tailored_cover_letter_md or "").strip():
        raise CannotScore("no_tailored_cl: empty tailored cover letter markdown")

    user_message = _build_user_message(
        job, profile, tailored_cv_md,
        cv_section_label="Tailored CV (this application's CV)",
        extra_section=("Cover letter (tailored)", tailored_cover_letter_md),
    )
    return _invoke_scorer(
        secrets, user_message,
        run_id=run_id, phase=phase, job_id=job.id,
    )


def llm_score(
    job: JobPosting,
    profile: Profile,
    secrets: Secrets,
    *,
    description_scraped: bool,
    user_feedback: str | None = None,
    run_id: int | None = None,
    phase: str = "score_base",
) -> ScoreResult:
    """Ask the LLM for a 0-100 fit score. Returns a ScoreResult.

    Raises `CannotScore` if a hard precondition fails (see module docstring).
    The caller must translate that into the matching `cannot_score:*` status.

    `description_scraped` is required and reflects the row's enrichment
    state: True only when the scraper's `fetch_detail` returned a real
    body. A listing-card snippet that happens to be 200+ words still
    fails the gate when this flag is False — the scorer must never trust
    a body the enrichment phase did not vouch for.

    `user_feedback`, when set, is injected as an extra prompt section
    ("Candidate feedback on previous score") between the hard preferences
    and the job description. Used by the feedback-driven rescore flow so
    the model can reconsider an earlier score in light of context the
    candidate provided after the fact (e.g. "I am willing to relocate to
    Freiburg", "I have hands-on Finanzbuchhaltung experience from a prior
    role not in my CV").
    """
    if not description_scraped:
        raise CannotScore(
            "no_body: description_scraped flag is false — enrichment "
            "never returned a real body for this posting"
        )

    body = (job.description or "").strip()
    word_count = len(body.split())
    if word_count < MIN_BODY_WORDS:
        raise CannotScore(f"no_body: description has {word_count} words, need >= {MIN_BODY_WORDS}")

    try:
        primary_cv = load_primary_cv()
    except (OSError, FileNotFoundError) as e:
        raise CannotScore(f"no_primary_cv: {e}") from e
    if not primary_cv.strip():
        raise CannotScore("no_primary_cv: primary CV extracted to empty text")

    extra: tuple[str, str] | None = None
    if user_feedback and user_feedback.strip():
        extra = ("Candidate feedback on previous score", user_feedback.strip())

    user_message = _build_user_message(
        job, profile, primary_cv, extra_section=extra,
    )
    return _invoke_scorer(
        secrets, user_message,
        run_id=run_id, phase=phase, job_id=job.id,
    )
