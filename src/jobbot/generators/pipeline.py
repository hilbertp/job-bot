"""Generate tailored CV + cover letter for a single job, write to disk as md + html."""
from __future__ import annotations

import re
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
    body = MarkdownIt().render(md)
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #111; line-height: 1.5; }}
  h1, h2, h3 {{ line-height: 1.2; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.2rem; margin-top: 1.5rem; }}
  ul {{ padding-left: 1.2rem; }}
  em {{ color: #6b7280; }}
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

    # Generate PDFs via WeasyPrint (required for file-upload adapters)
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
        pass  # PDF is optional; adapters fall back to no-upload if None

    return GeneratedDocs(
        cv_md=cv_md, cv_html=cv_html,
        cover_letter_md=cl_md, cover_letter_html=cl_html,
        output_dir=str(job_dir),
        cv_pdf=cv_pdf_path,
        cover_letter_pdf=cl_pdf_path,
    )
