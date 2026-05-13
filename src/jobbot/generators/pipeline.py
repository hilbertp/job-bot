"""Generate the outgoing application bundle for a single job.

Per-job CV + cover letter are both tailored via Sonnet, then rendered to
HTML + PDF (WeasyPrint). The static `config.cv_pdf_path` (e.g.
`data/general CV.pdf`) is used ONLY as a fallback: if the tailor call or
WeasyPrint render fails, the static PDF is copied into the per-job output
directory so the application is never sent without a CV attachment.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from anthropic import Anthropic
from markdown_it import MarkdownIt

from ..config import REPO_ROOT, Config, Secrets
from ..models import GeneratedDocs, JobPosting
from ..profile import Profile

PROMPTS = REPO_ROOT / "prompts"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _render_html(md: str) -> str:
    """Markdown → HTML for the standalone cv.html / cover_letter.html.

    Editorial typography matching the opus-application reference PDF:
    serif headlines (Newsreader from Google Fonts), italic role tag in
    accent rust, § small-caps section markers with hairline rules above,
    contact line in spaced small-caps sans. This is intentionally the
    same design system as `_render_application_html` (the unified
    package), minus the package-only banners and roman-numeral section
    dividers, so that a click on "cv.html" in the dashboard lands the
    user in the same visual language as the full application package.
    """
    body = MarkdownIt().render(md)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400;1,6..72,500;1,6..72,600&family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --ink:        #1a1814;
    --ink-soft:   #58544b;
    --ink-mute:   #8c877d;
    --accent:     #8d2b1c;
    --rule:       #d8d4cb;
    --paper:      #fdfcfa;
    --serif:      'Newsreader', 'EB Garamond', Georgia, 'Times New Roman', serif;
    --sans:       'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}

  @page {{ size: A4; margin: 20mm 22mm; }}

  body {{
    font-family: var(--serif);
    color: var(--ink);
    background: var(--paper);
    line-height: 1.6;
    font-size: 11pt;
    max-width: 780px;
    margin: 2.2rem auto;
    padding: 0 1rem;
  }}

  /* Name — large editorial serif with italic role tag */
  h1 {{
    font-family: var(--serif);
    font-size: 2.4rem;
    font-weight: 500;
    line-height: 1.08;
    letter-spacing: -0.012em;
    margin: 0 0 0.6rem 0;
    color: var(--ink);
  }}
  h1 em {{ font-style: italic; font-weight: 500; color: var(--ink); }}

  /* "Senior Product Owner" / positioning line under the name */
  h1 + p {{
    font-family: var(--serif);
    font-size: 1.05rem;
    color: var(--ink-soft);
    margin: 0 0 1.2rem 0;
  }}
  h1 + p em {{ color: var(--accent); font-style: italic; }}
  h1 + p strong:only-child {{ font-weight: 500; color: var(--ink-soft); }}

  /* Contact line (third paragraph): small caps sans, spaced */
  h1 + p + p {{
    font-family: var(--sans);
    color: var(--ink-mute);
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0;
  }}

  /* § SECTION markers: small-caps sans, warm gray, hairline above */
  h2 {{
    font-family: var(--sans);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--ink-mute);
    border-top: 1px solid var(--rule);
    padding-top: 1.6rem;
    margin: 2.2rem 0 1rem 0;
  }}
  h2::before {{ content: "§ "; color: var(--ink-mute); }}

  /* Job/Company heading (serif, slightly heavier) */
  h3 {{
    font-family: var(--serif);
    font-size: 1.2rem;
    font-weight: 500;
    color: var(--ink);
    margin: 1.4rem 0 0.15rem 0;
    line-height: 1.3;
  }}

  /* H4 — sub-label like role title / week label */
  h4 {{
    font-family: var(--serif);
    font-size: 1.05rem;
    font-style: italic;
    font-weight: 500;
    color: var(--ink-soft);
    margin: 0 0 0.3rem 0;
    line-height: 1.35;
  }}

  /* Italics → rust accent (matches opus reference italic emphasis) */
  em {{ font-style: italic; color: var(--accent); }}
  p > em:only-child {{ font-size: 0.95em; }}

  /* Body paragraphs */
  p {{ margin: 0.5rem 0; }}

  /* Bullets — middle-dot marker, soft warm gray */
  ul {{ padding-left: 1.1rem; margin: 0.45rem 0 0.7rem 0; }}
  li {{ margin: 0.2rem 0; }}
  li::marker {{ color: var(--ink-mute); }}

  /* Two-column treatment: any UL preceded by a small italic intro
     paragraph (e.g. "Daily tools, not buzzwords.") gets columnised,
     matching the opus reference's tools / tech-stack grids. */
  p em:only-child + ul,
  p > em:only-child ~ ul {{ column-count: 2; column-gap: 2.2rem; }}

  /* Horizontal rules from `---` in markdown */
  hr {{ border: 0; border-top: 1px solid var(--rule); margin: 1.8rem 0; }}
  hr + h2 {{ border-top: 0; padding-top: 0; margin-top: 0.6rem; }}

  strong {{ font-weight: 600; color: var(--ink); }}
  code {{
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.88em;
    color: var(--ink-soft);
  }}

  a {{ color: var(--ink); text-decoration: underline; text-decoration-color: var(--rule); }}
  a:hover {{ text-decoration-color: var(--accent); }}
</style></head>
<body>
{body}
</body></html>"""


def _render_application_html(md: str, job: JobPosting | None = None) -> str:
    """Markdown → HTML for the unified application package.

    Editorial typography matching the opus reference: serif headlines
    (Newsreader from Google Fonts), italic role tag, top + bottom small-caps
    banners, § section markers with hairlines, two-column AI-native stack,
    week cards in "How I would work", roman-numeral section dividers for the
    Cover Letter (I) and Curriculum Vitae (II) blocks.

    Post-render passes:
    - First H1 → hero block (large serif, italic role tag).
    - H1 starting with "I  " or "II  " → roman-numeral section divider.
    """
    body = MarkdownIt().render(md)

    # Hoist banner strings before the hero H1 so the LLM-generated content
    # opens with the editorial header line: "APPLICATION · COMPANY" / "ROLE".
    job_company = (job.company if job else "") or ""
    job_title = (job.title if job else "") or ""
    top_banner = (
        f'<div class="package-banner top">'
        f'<span class="banner-left">APPLICATION · {job_company.upper()}</span>'
        f'<span class="banner-right">{job_title.upper()}</span>'
        f"</div>"
    )

    # Roman-numeral section dividers (I, II) get rewritten with a leading
    # big numeral square + small-caps section title.
    def _section_divider(match: "re.Match[str]") -> str:
        numeral = match.group(1)
        title = match.group(2).strip()
        return (
            f'<div class="section-divider">'
            f'<span class="section-numeral">{numeral}</span>'
            f'<span class="section-title">{title}</span>'
            f"</div>"
        )

    body = re.sub(
        r"<h1>(I{1,3})\s+([^<]+)</h1>",
        _section_divider,
        body,
    )

    # Bottom banner mirrors the top one with TRUE NORTH branding +
    # candidate's email (rendered into the package by the LLM, we just frame
    # it). The actual contact text comes from the trust-anchor footer that
    # _inject_trust_anchors appended, so this banner is decorative.
    bottom_banner = (
        f'<div class="package-banner bottom">'
        f'<span class="banner-left">TRUE NORTH · APPLICATION PACKAGE'
        f"{' · ' + job_company.upper() if job_company else ''}"
        f"</span>"
        f'<span class="banner-right">→</span>'
        f"</div>"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400;1,6..72,500;1,6..72,600&family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --ink:        #1a1814;
    --ink-soft:   #58544b;
    --ink-mute:   #8c877d;
    --accent:     #8d2b1c;
    --rule:       #d8d4cb;
    --paper:      #fdfcfa;
    --serif:      'Newsreader', 'EB Garamond', Georgia, 'Times New Roman', serif;
    --sans:       'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}

  @page {{ size: A4; margin: 22mm 22mm 22mm 22mm; }}

  body {{
    font-family: var(--serif);
    color: var(--ink);
    background: var(--paper);
    line-height: 1.6;
    font-size: 11pt;
    max-width: 820px;
    margin: 2rem auto;
    padding: 0 1rem;
  }}

  .package-banner {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-family: var(--sans);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--ink-mute);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--rule);
    padding-bottom: 0.7rem;
    margin-bottom: 1.8rem;
  }}
  .package-banner.bottom {{
    border-bottom: 0;
    border-top: 1px solid var(--rule);
    padding-top: 0.7rem;
    margin-top: 3rem;
    margin-bottom: 0;
  }}
  .package-banner .banner-right {{ color: var(--ink-soft); }}

  /* Hero: Name as large serif with italic role tag */
  h1 {{
    font-family: var(--serif);
    font-size: 2.4rem;
    font-weight: 500;
    line-height: 1.08;
    letter-spacing: -0.012em;
    margin: 0 0 0.6rem 0;
    color: var(--ink);
  }}
  h1 em {{
    font-style: italic;
    font-weight: 500;
    color: var(--ink);
  }}
  /* First paragraph after the hero is the "Positioning," pitch */
  h1 + p {{
    font-family: var(--serif);
    font-size: 1.05rem;
    color: var(--ink-soft);
    margin: 0 0 1.2rem 0;
  }}
  h1 + p em {{ color: var(--accent); font-style: italic; }}
  /* The contact line (h1 + p + p): small caps, mute, spaced */
  h1 + p + p {{
    font-family: var(--sans);
    color: var(--ink-mute);
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0;
  }}

  /* Section markers: § SECTION NAME — small caps, warm gray, hairline above */
  h2 {{
    font-family: var(--sans);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--ink-mute);
    border-top: 1px solid var(--rule);
    padding-top: 1.6rem;
    margin: 2.2rem 0 1rem 0;
  }}
  h2::before {{ content: "§ "; color: var(--ink-mute); }}

  /* Subsection heading (Week 1, Job title, etc.) */
  h3 {{
    font-family: var(--serif);
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--ink-mute);
    margin: 1.2rem 0 0.2rem 0;
  }}

  /* H4 — the role label inside a week card or the sub-tagline */
  h4 {{
    font-family: var(--serif);
    font-size: 1.15rem;
    font-weight: 500;
    color: var(--ink);
    margin: 0 0 0.3rem 0;
    line-height: 1.35;
  }}

  /* Italics → rust accent (matches opus pull quotes / tags) */
  em {{ font-style: italic; color: var(--accent); }}

  /* Body paragraphs */
  p {{ margin: 0.45rem 0; }}

  /* Bullets */
  ul {{ padding-left: 1.1rem; margin: 0.4rem 0 0.6rem 0; }}
  li {{ margin: 0.18rem 0; }}
  li::marker {{ color: var(--ink-mute); }}

  /* Horizontal rules */
  hr {{ border: 0; border-top: 1px solid var(--rule); margin: 1.8rem 0; }}
  hr + h2, hr + .section-divider {{ border-top: 0; padding-top: 0; margin-top: 0.6rem; }}

  /* AI-native stack: bullets after `§ AI-NATIVE STACK` go two-column */
  h2[id="ai-native-stack"] + p + ul,
  h2 + p + ul.two-col,
  h2.two-col + p + ul {{ /* fallback selector */
    column-count: 2;
    column-gap: 2.2rem;
  }}
  /* Generic two-column heuristic: any UL with >= 6 items immediately after
     an `<em>` pull-quote paragraph gets the two-column treatment. The
     AI-native stack and Technical environment sections both qualify. */
  p > em:only-child + ul, p em + ul {{ column-count: 2; column-gap: 2.2rem; }}

  strong {{ font-weight: 600; color: var(--ink); }}
  code {{ font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em; color: var(--ink-soft); }}

  /* Section dividers I / II — large roman numeral + small-caps title */
  .section-divider {{
    display: flex;
    align-items: baseline;
    gap: 0.9rem;
    border-top: 1px solid var(--rule);
    padding-top: 1.4rem;
    margin: 2.6rem 0 1.2rem 0;
  }}
  .section-numeral {{
    font-family: var(--serif);
    font-size: 1.6rem;
    font-style: italic;
    color: var(--ink);
    font-weight: 500;
  }}
  .section-title {{
    font-family: var(--sans);
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--ink-mute);
  }}

  a {{ color: var(--ink); text-decoration: underline; text-decoration-color: var(--rule); }}
  a:hover {{ text-decoration-color: var(--accent); }}
</style></head>
<body>
{top_banner}
{body}
{bottom_banner}
</body></html>"""


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
    from ..state import connect, record_llm_usage

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


def _call_sonnet(
    client: Anthropic,
    system_prompt: str,
    user_payload: str,
    *,
    run_id: int | None = None,
    phase: str,
    job_id: str | None = None,
) -> str:
    model = "claude-sonnet-4-6"
    # max_tokens=4096: the unified application_package output covers cover
    # letter + full CV (6+ roles) + opus-style sections (Why X, AI-native
    # stack, Technical environment, Side project, How I would work,
    # Honest framing, Languages). At 2000 tokens the CV was truncating
    # mid-sentence inside the second Professional Experience entry. The
    # opus reference PDF runs ~3500 words of output; 4096 tokens leaves
    # comfortable headroom without inflating cost meaningfully (Sonnet
    # output tokens dominate cost, but the per-job add is ~$0.03).
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_payload}],
    )
    _record_usage_if_present(msg, run_id=run_id, phase=phase, job_id=job_id, model=model)
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def _resolve_static_cv(config: Config) -> Path | None:
    """Resolve the configured static CV PDF to an absolute path, or None if
    the option is disabled or the file doesn't exist on disk."""
    rel = (config.cv_pdf_path or "").strip()
    if not rel:
        return None
    p = (REPO_ROOT / rel).resolve()
    return p if p.is_file() else None


def _write_pdf_failure_artifact(target: Path, label: str, error: Exception) -> str:
    """Write a visible placeholder PDF plus a sidecar error note.

    The PDF intentionally starts with a PDF header so downstream code has a
    concrete artifact to inspect instead of a silent missing path.
    """
    safe_error = f"{type(error).__name__}: {error}".replace("\n", " ")
    target.write_bytes(
        b"%PDF-1.4\n"
        + f"% jobbot failed to render {label}: {safe_error}\n".encode("utf-8")
        + b"%%EOF\n"
    )
    target.with_suffix(".render_error.txt").write_text(
        f"Failed to render {label} PDF\n{safe_error}\n"
    )
    return str(target)


def _trust_anchor_line(profile: Profile) -> str | None:
    """Build the one-line "online presence" trust band — LinkedIn, GitHub,
    personal site (e.g. true-north.berlin), plus the YouTube English-language
    sample link when present. Empty links are skipped.

    Returns markdown like "[LinkedIn](url) · [GitHub](url) · [site](url) ·
    [YouTube (EN sample)](url)", or None if the profile has no links at all
    (don't inject an empty band)."""
    links = (profile.personal or {}).get("links") or {}
    entries: list[tuple[str, str]] = []
    if links.get("linkedin"):
        entries.append(("LinkedIn", links["linkedin"]))
    if links.get("github"):
        entries.append(("GitHub", links["github"]))
    if links.get("website"):
        label = links["website"].split("://", 1)[-1].rstrip("/")
        entries.append((label, links["website"]))
    if links.get("youtube_english_sample"):
        entries.append(("YouTube (EN sample)", links["youtube_english_sample"]))
    if not entries:
        return None
    return " · ".join(f"[{label}]({url})" for label, url in entries)


def _inject_trust_anchors(cv_md: str, profile: Profile) -> str:
    """Make LinkedIn / GitHub / personal-site links prominently visible at
    BOTH the top (right after the H1 header block) and the bottom of every
    tailored CV. The LLM is told not to invent facts, so we add these as a
    deterministic post-process — they're guaranteed to appear regardless of
    what the model did with the base CV."""
    line = _trust_anchor_line(profile)
    if not line:
        return cv_md
    lines = cv_md.splitlines()
    # Insert at the first horizontal-rule divider — the conventional end of
    # the CV's header block (name + role + contact-line). If the model
    # dropped the divider, fall back to inserting after the H1 + any
    # immediately-following non-blank lines (subtitle, contact line).
    insert_at: int | None = None
    for i, raw in enumerate(lines):
        if raw.strip() == "---":
            insert_at = i
            break
    if insert_at is None:
        for i, raw in enumerate(lines):
            if raw.startswith("# "):
                insert_at = i + 1
                while insert_at < len(lines) and lines[insert_at].strip():
                    insert_at += 1
                break
    if insert_at is None:
        insert_at = len(lines)
    lines[insert_at:insert_at] = ["", line, ""]
    return "\n".join(lines + ["", "---", "", line, ""])


_SEC_COVER_LETTER_RE = re.compile(
    r"^#\s+I\s+Cover letter\s*$.*?(?=^#\s+II\s+|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_SEC_CURRICULUM_VITAE_RE = re.compile(
    r"^#\s+II\s+Curriculum vitae\s*$.*",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _extract_section(pattern: "re.Pattern[str]", text: str) -> str:
    """Pull a roman-numeral-marked section out of the unified package.
    Returns the matched section verbatim (heading + body) or "" if not found."""
    m = pattern.search(text)
    return m.group(0).strip() if m else ""


def _extract_hero(package_md: str) -> str:
    """Pull the editorial hero block from the start of the unified package:
    `# {Name}. *{Role tag}*` + the positioning line + contact strip,
    everything up to (but not including) the first `## ` section heading.

    Why: the standalone cv.html / cover_letter.html — generated by
    rendering the `II Curriculum vitae` / `I Cover letter` sub-section —
    lacks an H1 hero, so it renders as a wall of body text with no
    editorial header. Prepending the hero gives every standalone
    artefact the same opus visual signature as the unified package.
    """
    # Take from the first `# ` H1 line up to the line BEFORE the first `## ` H2.
    m = re.match(r"\A\s*(#\s+[^\n]+\n+.*?)(?=^##\s)", package_md, re.DOTALL | re.MULTILINE)
    if not m:
        return ""
    hero = m.group(1).rstrip()
    # Drop trailing horizontal-rule markdown (`---`) that often sits between
    # the hero and the first section — the standalone consumer doesn't need
    # a leading divider.
    hero = re.sub(r"\n+-{3,}\s*$", "", hero)
    return hero.strip()


_SECTION_HEADING_RE = re.compile(
    r"^#\s+I{1,3}\s+[^\n]+\n+",
    re.MULTILINE | re.IGNORECASE,
)


def _strip_section_heading(md: str) -> str:
    """Remove the leading "# I  Cover letter" / "# II  Curriculum vitae"
    heading from an extracted sub-section.

    Why: the unified application_package layout uses those H1s as visual
    section dividers in the polished PDF. But when the cover-letter
    sub-section is used standalone (the email body, the cover_letter.md
    artifact, the dashboard preview), the heading leaks through as a
    weird `<h1>I Cover letter</h1>` at the top of the recipient's view.
    The section body is what the consumer actually wants."""
    return _SECTION_HEADING_RE.sub("", md, count=1).lstrip()


def generate_application_package(
    job: JobPosting, profile: Profile, base_cv: str,
    secrets: Secrets, config: Config,
    *,
    run_id: int | None = None,
) -> GeneratedDocs:
    """Produce a single opus-style application package as one Markdown
    document, render it to HTML + PDF via WeasyPrint, and split out the
    cover-letter and CV sections so existing consumers (ATS form adapters,
    dashboard previews) keep working.

    The package layout matches the user's reference PDF:
    - Top banner ("APPLICATION · <COMPANY>" / "<ROLE>")
    - Hero (name + italic role tag)
    - § Why <company>
    - § Honest framing (conditional)
    - § AI-native stack (two-column)
    - § Technical environment
    - § Side project (conditional)
    - § How I would work at <company> (Week 1 / 2 / 3+ cards)
    - I  Cover letter
    - II  Curriculum vitae (bearing, core strengths, experience, founders, langs)
    - Bottom banner + trust-anchor band (LinkedIn / GitHub / true-north / YouTube)
    """
    client = Anthropic(api_key=secrets.anthropic_api_key)

    package_prompt = (PROMPTS / "application_package.md").read_text()
    payload = (
        f"# Job\n\n## {job.title} — {job.company}\n\n{job.description}\n\n"
        f"# Profile\n\n```yaml\n{profile.model_dump_json(indent=2)}\n```\n\n"
        f"# Base CV\n\n{base_cv}\n"
    )

    package_md = _call_sonnet(
        client, package_prompt, payload,
        run_id=run_id, phase="generate_application_package", job_id=job.id,
    )
    # Pin trust anchors top + bottom so the band is guaranteed regardless of
    # what the LLM emitted in the hero block.
    package_md = _inject_trust_anchors(package_md, profile)

    # Extract the cover-letter and CV sub-sections so the existing consumers
    # (ATS form adapters expecting cv.pdf / cover_letter.pdf, dashboard
    # previews of cv.md / cover_letter.md) keep working unchanged.
    cl_md = _extract_section(_SEC_COVER_LETTER_RE, package_md) or package_md
    cv_md = _extract_section(_SEC_CURRICULUM_VITAE_RE, package_md) or package_md
    # Strip the "# I  Cover letter" / "# II  Curriculum vitae" dividers —
    # they're fine in the unified package as visual section markers but
    # render as a confusing H1 at the top of the standalone view.
    cl_md = _strip_section_heading(cl_md)
    cv_md = _strip_section_heading(cv_md)
    # Prepend the package's hero block (name + role tag + positioning +
    # contact line) so the standalone CV / cover-letter views carry the
    # same opus-style editorial header as the unified package. Without
    # this the standalone cv.html opens cold at "## Bearing" with no
    # name or context, which looks like a stripped-down draft instead
    # of a finished application artefact.
    hero_md = _extract_hero(package_md)
    if hero_md:
        cv_md = f"{hero_md}\n\n---\n\n{cv_md}"
        cl_md = f"{hero_md}\n\n---\n\n{cl_md}"

    out_root = REPO_ROOT / config.output_dir / date.today().isoformat()
    job_dir = out_root / f"{job.source}__{_slug(job.company)}__{_slug(job.title)}"
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "application_package.md").write_text(package_md)
    (job_dir / "cv.md").write_text(cv_md)
    (job_dir / "cover_letter.md").write_text(cl_md)

    package_html = _render_application_html(package_md, job=job)
    cv_html = _render_html(cv_md)
    cl_html = _render_html(cl_md)
    (job_dir / "application_package.html").write_text(package_html)
    (job_dir / "cv.html").write_text(cv_html)
    (job_dir / "cover_letter.html").write_text(cl_html)

    package_pdf_path: str | None = None
    cv_pdf_path: str | None = None
    cl_pdf_path: str | None = None
    package_pdf_dest = job_dir / "application_package.pdf"
    cv_pdf_dest = job_dir / "cv.pdf"
    cl_pdf_dest = job_dir / "cover_letter.pdf"
    try:
        from weasyprint import HTML as WP
    except Exception as e:
        package_err = cv_err = cl_err = e
        WP = None
    else:
        package_err = cv_err = cl_err = None
        try:
            WP(string=package_html).write_pdf(str(package_pdf_dest))
            package_pdf_path = str(package_pdf_dest)
        except Exception as e:
            package_err = e
        try:
            WP(string=cv_html).write_pdf(str(cv_pdf_dest))
            cv_pdf_path = str(cv_pdf_dest)
        except Exception as e:
            cv_err = e
        try:
            WP(string=cl_html).write_pdf(str(cl_pdf_dest))
            cl_pdf_path = str(cl_pdf_dest)
        except Exception as e:
            cl_err = e

    # Fallbacks: copy static CV if the tailored CV render failed; write a
    # visible placeholder when nothing else is available so downstream code
    # has a concrete artifact instead of a missing path.
    if cv_pdf_path is None:
        static_cv = _resolve_static_cv(config)
        if static_cv is not None:
            shutil.copyfile(static_cv, cv_pdf_dest)
            cv_pdf_path = str(cv_pdf_dest)
            if cv_err is not None:
                cv_pdf_dest.with_suffix(".render_error.txt").write_text(
                    f"Tailored CV PDF render failed; copied static CV fallback.\n"
                    f"{type(cv_err).__name__}: {cv_err}\n"
                )
        elif cv_err is not None:
            cv_pdf_path = _write_pdf_failure_artifact(cv_pdf_dest, "CV", cv_err)
    if cl_pdf_path is None and cl_err is not None:
        cl_pdf_path = _write_pdf_failure_artifact(cl_pdf_dest, "cover letter", cl_err)
    if package_pdf_path is None and package_err is not None:
        package_pdf_path = _write_pdf_failure_artifact(
            package_pdf_dest, "application package", package_err,
        )

    return GeneratedDocs(
        cv_md=cv_md, cv_html=cv_html,
        cover_letter_md=cl_md, cover_letter_html=cl_html,
        output_dir=str(job_dir),
        cv_pdf=cv_pdf_path,
        cover_letter_pdf=cl_pdf_path,
        application_package_md=package_md,
        application_package_html=package_html,
        application_package_pdf=package_pdf_path,
    )


def generate_documents(
    job: JobPosting, profile: Profile, base_cv: str,
    secrets: Secrets, config: Config,
    *,
    run_id: int | None = None,
) -> GeneratedDocs:
    client = Anthropic(api_key=secrets.anthropic_api_key)

    cv_prompt = (PROMPTS / "cv_tailor.md").read_text()
    cl_prompt = (PROMPTS / "cover_letter.md").read_text()
    payload = (
        f"# Job\n\n## {job.title} — {job.company}\n\n{job.description}\n\n"
        f"# Profile\n\n```yaml\n{profile.model_dump_json(indent=2)}\n```\n\n"
        f"# Base CV\n\n{base_cv}\n"
    )

    cv_md = _call_sonnet(
        client, cv_prompt, payload,
        run_id=run_id, phase="generate_cv", job_id=job.id,
    )
    # Pin LinkedIn / GitHub / personal-site links visibly at top + bottom of
    # every tailored CV. Done post-LLM so the bands are guaranteed regardless
    # of what the model chose to keep from the base CV's header.
    cv_md = _inject_trust_anchors(cv_md, profile)
    cl_md = _call_sonnet(
        client, cl_prompt, payload,
        run_id=run_id, phase="generate_cover_letter", job_id=job.id,
    )

    out_root = REPO_ROOT / config.output_dir / date.today().isoformat()
    job_dir = out_root / f"{job.source}__{_slug(job.company)}__{_slug(job.title)}"
    job_dir.mkdir(parents=True, exist_ok=True)

    (job_dir / "cv.md").write_text(cv_md)
    (job_dir / "cover_letter.md").write_text(cl_md)
    cv_html = _render_html(cv_md)
    cl_html = _render_html(cl_md)
    (job_dir / "cv.html").write_text(cv_html)
    (job_dir / "cover_letter.html").write_text(cl_html)

    cv_pdf_path: str | None = None
    cl_pdf_path: str | None = None
    cv_pdf_dest = job_dir / "cv.pdf"
    cl_pdf_dest = job_dir / "cover_letter.pdf"
    try:
        from weasyprint import HTML as WP
    except Exception as e:
        cv_render_error = cl_render_error = e
        WP = None
    else:
        cv_render_error = cl_render_error = None
        try:
            WP(string=cv_html).write_pdf(str(cv_pdf_dest))
            cv_pdf_path = str(cv_pdf_dest)
        except Exception as e:
            cv_render_error = e
        try:
            WP(string=cl_html).write_pdf(str(cl_pdf_dest))
            cl_pdf_path = str(cl_pdf_dest)
        except Exception as e:
            cl_render_error = e

    # Fallback: if the tailored CV PDF didn't render, copy the static
    # general CV.pdf in so the application is still attachable. If no static
    # fallback exists, write a visible placeholder artifact plus sidecar note
    # so the failure is not silently hidden.
    if cv_pdf_path is None:
        static_cv = _resolve_static_cv(config)
        if static_cv is not None:
            shutil.copyfile(static_cv, cv_pdf_dest)
            cv_pdf_path = str(cv_pdf_dest)
            if cv_render_error is not None:
                cv_pdf_dest.with_suffix(".render_error.txt").write_text(
                    f"Tailored CV PDF render failed; copied static CV fallback.\n"
                    f"{type(cv_render_error).__name__}: {cv_render_error}\n"
                )
        elif cv_render_error is not None:
            cv_pdf_path = _write_pdf_failure_artifact(cv_pdf_dest, "CV", cv_render_error)

    if cl_pdf_path is None and cl_render_error is not None:
        cl_pdf_path = _write_pdf_failure_artifact(
            cl_pdf_dest, "cover letter", cl_render_error,
        )

    return GeneratedDocs(
        cv_md=cv_md, cv_html=cv_html,
        cover_letter_md=cl_md, cover_letter_html=cl_html,
        output_dir=str(job_dir),
        cv_pdf=cv_pdf_path,
        cover_letter_pdf=cl_pdf_path,
    )
