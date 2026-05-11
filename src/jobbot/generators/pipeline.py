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
    """Markdown → HTML for both browser preview and WeasyPrint PDF output.

    Styling notes — this is the editorial template, scoped per user feedback:
    keep the H1 (name) typography untouched (system sans), but lift the rest
    of the document with warm color tokens, hairline section dividers,
    small-caps section markers, and an accent color on italics. The headline
    foundry serif from the opus reference PDF is deliberately NOT attempted
    here — it's a paid typeface and free substitutes don't carry the feel.
    """
    body = MarkdownIt().render(md)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  /* --- design tokens (warm editorial palette) --- */
  :root {{
    --ink:        #1a1814;  /* primary text */
    --ink-soft:   #58544b;  /* secondary text, tech notes */
    --ink-mute:   #8c877d;  /* section markers, contact line */
    --accent:     #8d2b1c;  /* rust — used on italics for emphasis */
    --rule:       #d8d4cb;  /* hairline dividers */
    --paper:      #fdfcfa;  /* off-white background */
  }}

  /* --- page setup (WeasyPrint reads @page; harmless in browsers) --- */
  @page {{
    size: A4;
    margin: 20mm 22mm;
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                 Helvetica, Arial, sans-serif;
    color: var(--ink);
    background: var(--paper);
    line-height: 1.55;
    font-size: 10.5pt;
    /* Browser-only outer frame; WeasyPrint uses @page margins instead. */
    max-width: 780px;
    margin: 2.2rem auto;
    padding: 0 1rem;
  }}

  /* --- name (left untouched per design scope: system sans, heavy weight) --- */
  h1 {{
    font-size: 1.9rem;
    line-height: 1.15;
    margin: 0 0 0.15rem 0;
    color: var(--ink);
    font-weight: 700;
    letter-spacing: -0.01em;
  }}

  /* --- "Senior Product Owner" line that sits right under the name --- */
  h1 + p strong:only-child {{
    font-weight: 500;
    color: var(--ink-soft);
  }}

  /* --- contact line (third paragraph, plain text) --- */
  h1 + p + p {{
    color: var(--ink-mute);
    font-size: 0.92em;
    margin-bottom: 0;
  }}

  /* --- section markers: § SECTION, small-caps, warm gray, hairline above --- */
  h2 {{
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--ink-mute);
    border-top: 1px solid var(--rule);
    padding-top: 1.4rem;
    margin: 2rem 0 0.9rem 0;
  }}
  h2::before {{
    content: "§ ";
    color: var(--ink-mute);
  }}

  /* --- subsection title (company — role) --- */
  h3 {{
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--ink);
    margin: 1.3rem 0 0.1rem 0;
    line-height: 1.3;
  }}

  /* --- date range / tech note: italic in accent rust --- */
  em {{
    font-style: italic;
    color: var(--accent);
  }}
  /* A standalone italic paragraph (date range or tech note) gets reduced
     leading so it pairs tightly with the H3 above it. */
  p > em:only-child {{
    font-size: 0.9em;
  }}

  /* --- body paragraphs --- */
  p {{
    margin: 0.45rem 0;
  }}

  /* --- bullets: square-ish marker in soft warm gray --- */
  ul {{
    padding-left: 1.1rem;
    margin: 0.4rem 0 0.6rem 0;
  }}
  li {{
    margin: 0.18rem 0;
  }}
  li::marker {{
    color: var(--ink-mute);
  }}

  /* --- horizontal rules from `---` in markdown --- */
  hr {{
    border: 0;
    border-top: 1px solid var(--rule);
    margin: 1.8rem 0;
  }}
  /* When an hr immediately precedes a section heading, the heading's own
     border-top would create a double-line. Suppress one. */
  hr + h2 {{
    border-top: 0;
    padding-top: 0;
    margin-top: 0.6rem;
  }}

  /* --- inline strong: same color, just weight --- */
  strong {{
    font-weight: 600;
    color: var(--ink);
  }}

  /* --- inline code, just in case --- */
  code {{
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.88em;
    color: var(--ink-soft);
  }}
</style></head>
<body>
{body}
</body></html>"""


def _call_sonnet(client: Anthropic, system_prompt: str, user_payload: str) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_payload}],
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def _resolve_static_cv(config: Config) -> Path | None:
    """Resolve the configured static CV PDF to an absolute path, or None if
    the option is disabled or the file doesn't exist on disk."""
    rel = (config.cv_pdf_path or "").strip()
    if not rel:
        return None
    p = (REPO_ROOT / rel).resolve()
    return p if p.is_file() else None


def generate_documents(
    job: JobPosting, profile: Profile, base_cv: str,
    secrets: Secrets, config: Config,
) -> GeneratedDocs:
    client = Anthropic(api_key=secrets.anthropic_api_key)

    cv_prompt = (PROMPTS / "cv_tailor.md").read_text()
    cl_prompt = (PROMPTS / "cover_letter.md").read_text()
    payload = (
        f"# Job\n\n## {job.title} — {job.company}\n\n{job.description}\n\n"
        f"# Profile\n\n```yaml\n{profile.model_dump_json(indent=2)}\n```\n\n"
        f"# Base CV\n\n{base_cv}\n"
    )

    cv_md = _call_sonnet(client, cv_prompt, payload)
    cl_md = _call_sonnet(client, cl_prompt, payload)

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
    try:
        from weasyprint import HTML as WP
        _cv_pdf = job_dir / "cv.pdf"
        _cl_pdf = job_dir / "cover_letter.pdf"
        WP(string=cv_html).write_pdf(str(_cv_pdf))
        WP(string=cl_html).write_pdf(str(_cl_pdf))
        cv_pdf_path = str(_cv_pdf)
        cl_pdf_path = str(_cl_pdf)
    except Exception:
        pass  # WeasyPrint optional; fall back below.

    # Fallback: if the tailored CV PDF didn't render, copy the static
    # general CV.pdf in so the application is still attachable. The cover
    # letter has no static fallback — adapters skip the file upload if
    # cl_pdf_path is None.
    if cv_pdf_path is None:
        static_cv = _resolve_static_cv(config)
        if static_cv is not None:
            cv_pdf_dest = job_dir / "cv.pdf"
            shutil.copyfile(static_cv, cv_pdf_dest)
            cv_pdf_path = str(cv_pdf_dest)

    return GeneratedDocs(
        cv_md=cv_md, cv_html=cv_html,
        cover_letter_md=cl_md, cover_letter_html=cl_html,
        output_dir=str(job_dir),
        cv_pdf=cv_pdf_path,
        cover_letter_pdf=cl_pdf_path,
    )
