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
    msg = client.messages.create(
        model=model,
        max_tokens=2000,
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
