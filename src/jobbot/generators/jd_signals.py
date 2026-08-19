"""Deterministic job-description signal extraction for the CV personalizer.

Everything here is regex + set intersection, no LLM calls, so it runs on
every generation for free and its outputs are verifiable after the fact
(see `generators.qa`). Three signal families, each grounded in how
screening actually works (research dossier, 2026-08):

- `language`: cover letters must match the posting's language; the
  package prompt needs the decision made for it, not inferred per call.
- `mirror_terms`: recruiters retrieve candidates by searching parsed
  fields for the posting's exact vocabulary, and ranking layers key on
  the same tokens. A term only qualifies when it appears in BOTH the
  posting and the candidate's own material (base CV / profile), so the
  generator can mirror it truthfully; terms the candidate cannot back
  are never suggested.
- `directives`: postings embed application instructions ("include the
  word X", "Referenznummer angeben", "start your letter with...") partly
  as attention traps for unattended AI agents. A pipeline that misses
  one self-identifies as a bot, so they are extracted here and enforced
  in QA.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import JobPosting
from ..profile import Profile


@dataclass(frozen=True)
class Directive:
    """One application instruction found in the posting body."""

    instruction: str
    # Verbatim token whose presence in the cover letter QA can verify.
    # None for directives that are real but not string-checkable
    # (e.g. "answer this question: ...").
    must_contain: str | None = None


@dataclass(frozen=True)
class JdSignals:
    language: str  # "de" | "en"
    posting_title: str
    mirror_terms: list[str] = field(default_factory=list)
    directives: list[Directive] = field(default_factory=list)


# --- language -----------------------------------------------------------

_DE_STOPWORDS = re.compile(
    r"\b(und|der|die|das|mit|für|wir|nicht|eine?|werden|sind|dein(?:e|em|en)?|"
    r"unser(?:e|em|en)?|bei|über|auf|als|zum|zur|aufgaben|anforderungen|"
    r"kenntnisse|erfahrung|bewerbung)\b",
    re.IGNORECASE,
)
_EN_STOPWORDS = re.compile(
    r"\b(the|and|with|for|you|we|our|are|will|your|of|to|in|as|on|team|"
    r"experience|requirements|responsibilities|skills|role)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    """German vs English by function-word frequency; ties default to English.

    Postings on German boards frequently mix an English title with a German
    body (or vice versa), so single-marker heuristics misfire; counting
    function words over the whole text is stable against that.
    """
    de = len(_DE_STOPWORDS.findall(text))
    en = len(_EN_STOPWORDS.findall(text))
    return "de" if de > en else "en"


# --- directives ---------------------------------------------------------

# Each entry: (compiled pattern, instruction template, capture-is-token).
# Patterns are deliberately narrow: a false directive pollutes the cover
# letter, so precision beats recall here. `{}` receives the captured text.
_DIRECTIVE_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    (
        re.compile(
            r"include\s+the\s+(?:word|phrase)\s+[\"'“„]?"
            r"([\w][\w -]{1,39})[\"'“”]?",
            re.IGNORECASE,
        ),
        'include the exact word/phrase "{}" in the cover letter',
        True,
    ),
    (
        re.compile(
            r"(?:start|begin)\s+your\s+(?:cover\s+letter|application|message|"
            r"email)\s+with\s+[\"'“„]?([^\"'“”\n.]{2,60})",
            re.IGNORECASE,
        ),
        'start the cover letter with "{}"',
        True,
    ),
    (
        re.compile(
            r"beginnen?\s+Sie\s+Ihr(?:e)?\s+(?:Anschreiben|Bewerbung|Nachricht)"
            r"\s+mit\s+[\"'“„]?([^\"'“”\n.]{2,60})",
            re.IGNORECASE,
        ),
        'start the cover letter with "{}"',
        True,
    ),
    (
        re.compile(
            r"mention\s+(?:the\s+word\s+)?[\"'“„]"
            r"([^\"'“”\n]{2,40})[\"'“”]",
            re.IGNORECASE,
        ),
        'mention "{}" in the cover letter',
        True,
    ),
    (
        re.compile(
            r"\b(?:reference\s+(?:number|code)|ref\.?\s*no\.?|Referenznummer|"
            r"Kennziffer|Kennwort|Stellen-?ID|Job-?ID)\s*[:#]\s*"
            r"([A-Za-z0-9][A-Za-z0-9/_-]{1,24})",
            re.IGNORECASE,
        ),
        'quote the reference code "{}" in the cover letter',
        True,
    ),
    (
        re.compile(
            r"(?:in\s+your\s+(?:cover\s+letter|application)[,:]?\s+)?"
            r"(?:please\s+)?(?:answer|tell\s+us|let\s+us\s+know)[:,]?\s+"
            r"([^\n]{10,160}\?)",
            re.IGNORECASE,
        ),
        'answer this question from the posting in the cover letter: "{}"',
        False,
    ),
]

_MAX_DIRECTIVES = 5


def extract_directives(text: str) -> list[Directive]:
    found: list[Directive] = []
    seen: set[str] = set()
    for pattern, template, capture_is_token in _DIRECTIVE_PATTERNS:
        for m in pattern.finditer(text):
            token = m.group(1).strip()
            key = token.lower()
            if not token or key in seen:
                continue
            seen.add(key)
            found.append(
                Directive(
                    instruction=template.format(token),
                    must_contain=token if capture_is_token else None,
                )
            )
            if len(found) >= _MAX_DIRECTIVES:
                return found
    return found


# --- mirror terms -------------------------------------------------------

# Single words too generic to be worth mirroring on their own. Multi-word
# phrases ("Product Management", "Stakeholder Management") always qualify.
_GENERIC_SINGLES = {
    "product", "management", "team", "teams", "experience", "work",
    "working", "tools", "skills", "business", "software", "company",
    "role", "roles", "years", "strong", "senior", "und", "mit", "the",
    "and", "for", "with", "digital", "agile",
}

_BOLD_RE = re.compile(r"\*\*([^*\n]{2,60})\*\*")


def _candidate_vocabulary(profile: Profile, base_cv: str) -> list[str]:
    """Skill/tool/domain terms the candidate can truthfully claim.

    Sources: the compiled profile's structured lists plus the base CV's
    bold group labels and their comma-separated tool lists (the
    "What I can do" shape: `**Group label**, tool1, tool2`).
    """
    vocab: list[str] = []
    for item in profile.capabilities:
        vocab.append(str(item.get("skill", "")))
    for item in profile.domains:
        vocab.append(str(item.get("name", "")))
    vocab.extend(profile.must_have_skills)
    vocab.extend(profile.nice_to_have_skills)

    for line in base_cv.splitlines():
        bolds = _BOLD_RE.findall(line)
        if not bolds:
            continue
        vocab.extend(bolds)
        # Tool list after the bold label: "**Label**, Jira, Confluence"
        rest = _BOLD_RE.sub("", line)
        for chunk in re.split(r"[,·|]", rest):
            vocab.append(chunk.strip(" -:*"))

    cleaned: list[str] = []
    for term in vocab:
        term = " ".join(term.split())
        if not (2 <= len(term) <= 40):
            continue
        if term.replace(".", "").isdigit():
            continue
        if " " not in term and term.lower() in _GENERIC_SINGLES:
            continue
        cleaned.append(term)
    return cleaned


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])", re.IGNORECASE)


_MAX_MIRROR_TERMS = 15


def extract_mirror_terms(
    description: str, profile: Profile, base_cv: str
) -> list[str]:
    """Terms present in BOTH the posting and the candidate's own material.

    These are the safe-to-mirror tokens: the candidate can truthfully claim
    them, and the posting proves the employer searches/ranks on them. Sorted
    by first occurrence in the posting; the spelling returned is the
    POSTING's spelling, because that is the string recruiters filter on.
    """
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for term in _candidate_vocabulary(profile, base_cv):
        key = term.lower()
        if key in seen:
            continue
        m = _term_pattern(term).search(description)
        if not m:
            continue
        seen.add(key)
        hits.append((m.start(), m.group(0)))
    hits.sort()
    return [t for _, t in hits[:_MAX_MIRROR_TERMS]]


# --- assembly -----------------------------------------------------------


def build_signals(job: JobPosting, profile: Profile, base_cv: str) -> JdSignals:
    text = f"{job.title or ''}\n{job.description or ''}"
    return JdSignals(
        language=detect_language(text),
        posting_title=(job.title or "").strip(),
        mirror_terms=extract_mirror_terms(job.description or "", profile, base_cv),
        directives=extract_directives(job.description or ""),
    )


def render_signal_block(signals: JdSignals) -> str:
    """The `# Application signals` payload section the generator prompts read.

    Instructions live in the system prompts; this block only carries the
    extracted data, so a posting cannot inject behavior through it beyond
    the narrow, template-shaped directive strings.
    """
    lines = [
        "# Application signals",
        "",
        "Extracted deterministically from the posting. Apply them exactly as",
        "the system prompt's targeting rules instruct.",
        "",
        f"- posting_title: {signals.posting_title}",
        f"- language: {signals.language}",
    ]
    if signals.mirror_terms:
        lines.append(f"- mirror_terms: {', '.join(signals.mirror_terms)}")
    else:
        lines.append("- mirror_terms: (none found)")
    if signals.directives:
        lines.append("- directives:")
        lines.extend(f"  - MUST {d.instruction}" for d in signals.directives)
    else:
        lines.append("- directives: (none found)")
    return "\n".join(lines)
