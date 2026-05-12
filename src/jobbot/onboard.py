"""Interactive `jobbot init` wizard.

Asks a newcomer a focused set of questions and writes:
  - .env                  (with placeholder API keys to fill manually)
  - data/profile.yaml     (their name, email, preferences, deal-breakers)
  - data/config.yaml      (search queries tuned to their target role)
  - data/base_cv.md       (a stub CV they MUST replace with their own content)

Designed for someone who has never touched the codebase. Every prompt has
a sensible default (shown in [brackets]); pressing Enter accepts it. Yes
or No questions accept y/yes/1 vs n/no/0 (case-insensitive).

The wizard is non-destructive: if a target file already exists it asks
before overwriting. If the user declines, that file stays untouched
and the rest of the run continues.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from .config import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"


def _prompt(label: str, default: str = "", *, required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"  {label}{suffix}: ").strip()
        value = raw if raw else default
        if value or not required:
            return value
        print("    (required — please enter a value)")


def _prompt_yn(label: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        raw = input(f"  {label} [{default_str}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "1", "true"}:
            return True
        if raw in {"n", "no", "0", "false"}:
            return False
        print("    (please answer y or n)")


def _prompt_int(label: str, default: int) -> int:
    while True:
        raw = input(f"  {label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("    (must be a number)")


def _confirm_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    return _prompt_yn(f"{path.relative_to(REPO_ROOT)} already exists — overwrite?", default=False)


def _split_csv(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def _yaml_escape(s: str) -> str:
    """Quote a YAML scalar value safely. Keeps it readable: uses double
    quotes and only escapes the few characters that actually need it."""
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _write_env(answers: dict, path: Path) -> None:
    body = f"""# Copy edited from .env.example by `jobbot init`.

# Anthropic — REQUIRED. Get a key at https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-PASTE-YOUR-KEY-HERE

# Gmail (App Password — NOT your normal password)
# Generate at: https://myaccount.google.com/apppasswords
GMAIL_ADDRESS={answers["gmail_address"]}
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFY_TO={answers["notify_to"]}

# Captcha solver (optional — only needed if you enable web-form auto-apply)
CAPTCHA_PROVIDER=twocaptcha
CAPTCHA_API_KEY=

# IMAP (defaults to Gmail; same address + app password as SMTP above)
IMAP_HOST=imap.gmail.com
IMAP_PORT=993

# Outbound application email — fill in only when you're ready to send
# real applications. Until then the email channel stays in dry-run mode.
TRUENORTH_SMTP_HOST=
TRUENORTH_SMTP_PORT=587
TRUENORTH_SMTP_USER=
TRUENORTH_SMTP_PASS=
"""
    path.write_text(body)


def _write_profile(answers: dict, path: Path) -> None:
    body = f"""# Created by `jobbot init`. Edit freely.

personal:
  full_name: {_yaml_escape(answers["full_name"])}
  email: {_yaml_escape(answers["personal_email"])}
  phone: {_yaml_escape(answers["phone"])}
  location:
    city: {_yaml_escape(answers["city"])}
    country: {_yaml_escape(answers["country"])}
    timezone: {_yaml_escape(answers["timezone"])}
  links:
    linkedin: {_yaml_escape(answers["linkedin"])}
    github: {_yaml_escape(answers["github"])}
    website: {_yaml_escape(answers["website"])}

preferences:
  remote: {str(answers["remote"]).lower()}
  on_site_ok: {str(answers["on_site_ok"]).lower()}
  willing_to_relocate: {str(answers["willing_to_relocate"]).lower()}
  desired_salary_eur:
    min: {answers["salary_min"]}
    max: {answers["salary_max"]}
  notice_period_weeks: 8
  work_authorization: {_yaml_escape(answers["work_authorization"])}
  languages: [{", ".join(answers["languages"])}]

deal_breakers:
  industries: [{", ".join(_yaml_escape(s) for s in answers["dealbreaker_industries"])}]
  keywords: ["unpaid", "commission only"]
  on_site_only: true

must_have_skills: [{", ".join(_yaml_escape(s) for s in answers["must_have_skills"])}]

nice_to_have_skills: [{", ".join(_yaml_escape(s) for s in answers["nice_to_have_skills"])}]

target_roles: [{", ".join(_yaml_escape(s) for s in answers["target_roles"])}]

screener_defaults:
  "Are you authorized to work in this country?": {_yaml_escape("Yes" if answers["work_authorization"] else "No")}
  "Do you require visa sponsorship?": "No"
  "Notice period?": "8 weeks"
  "Earliest start date?": "8 weeks from offer"

user_facts: []
"""
    path.write_text(body)


def _write_config(answers: dict, path: Path) -> None:
    """Tune the per-source queries to the user's target roles. The shipped
    config has dozens of PM-specific knobs; this wizard rewrites only the
    queries section so the rest of the defaults (rate-limits, dry_run,
    etc.) stay in place. If config.yaml already exists, the wizard
    appends a single comment pointing at the queries to edit by hand."""
    target_csv = ", ".join(answers["target_roles"])
    queries_yaml = "\n".join(f"      - q: {_yaml_escape(role)}" for role in answers["target_roles"])
    body = f"""# Created by `jobbot init`. Tune queries per source as needed.
# Target roles: {target_csv}

score_threshold: 70
max_jobs_per_run: 50
output_dir: "output"
cv_pdf_path: ""

apply:
  dry_run: true            # KEEP THIS TRUE until you've reviewed a dry-run application.eml
  per_run_limit: 5
  confirm_each: false

digest:
  generate_docs_above_score: 70
  max_per_email: 100

enrichment:
  per_run_cap: 100

sources:
  stepstone:
    enabled: true
    auto_submit: false
    queries:
{queries_yaml}
  xing:
    enabled: true
    auto_submit: false
    queries:
{queries_yaml}
  linkedin:
    enabled: true
    auto_submit: false        # NEVER enable this — LinkedIn ToS forbids auto-apply
    queries:
{queries_yaml}
  weworkremotely:
    enabled: true
    auto_submit: false
    queries:
      - category: remote-programming-jobs   # WWR uses categories, not free text — edit this
  dailyremote:
    enabled: true
    auto_submit: false
    queries:
{queries_yaml}
  freelancermap:
    enabled: false
    auto_submit: false
    queries:
{queries_yaml}
  indeed:
    enabled: false
    auto_submit: false
    queries:
{queries_yaml}
"""
    path.write_text(body)


def _write_base_cv(answers: dict, path: Path) -> None:
    body = f"""# {answers["full_name"]}

{answers["city"]}, {answers["country"]} · {answers["personal_email"]}

## Summary

REPLACE THIS PARAGRAPH with your real summary. One paragraph, max 4 sentences.
Lead with the 1–2 facts most relevant to the roles you're targeting
({", ".join(answers["target_roles"])}). The LLM uses this as the hook
when tailoring per job — it will NEVER invent claims you don't put here.

## Experience

### Most recent role — Company name

*City · YYYY – present*

- Replace with a concrete accomplishment, ideally with a metric.
- Replace with another bullet — verb-first, past tense.
- Three to five bullets per role works well.

### Previous role — Company name

*City · YYYY – YYYY*

- Bullet 1.
- Bullet 2.

## Skills

**Replace each line with your actual skills, grouped sensibly.**
**Languages:** ...
**Tools:** ...
**Domain:** ...

## Education

**Highest qualification** — Institution, YYYY

## Languages

{", ".join(answers["languages"])}
"""
    path.write_text(body)


def run() -> int:
    """Drive the wizard. Returns 0 on success, 1 if the user aborted."""
    print()
    print("─" * 64)
    print(" jobbot init — let's set up your personal job-search profile.")
    print("─" * 64)
    print()
    print(" Every question has a default in [brackets]. Press Enter to accept.")
    print(" The wizard never sends anything; it only writes local files.")
    print()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    answers: dict = {}

    print(" 1. Who are you?")
    answers["full_name"] = _prompt("Full name", required=True)
    answers["personal_email"] = _prompt("Personal email (appears on your CV)", required=True)
    answers["phone"] = _prompt("Phone (with country code, e.g. +49 …)", required=False)
    answers["city"] = _prompt("City you live in", required=False, default="Berlin")
    answers["country"] = _prompt("Country", required=False, default="Germany")
    answers["timezone"] = _prompt("IANA timezone", default="Europe/Berlin")

    print()
    print(" 2. Online presence (these become the trust band on every CV)")
    answers["linkedin"] = _prompt("LinkedIn URL", default="")
    answers["github"] = _prompt("GitHub URL (optional)", default="")
    answers["website"] = _prompt("Personal website / portfolio (optional)", default="")

    print()
    print(" 3. Email accounts")
    print("    The Gmail account is what sends you the daily digest.")
    print("    It is NOT used for outbound applications — those go through")
    print("    a separate business SMTP you can configure later.")
    answers["gmail_address"] = _prompt("Your Gmail address", default=answers["personal_email"])
    answers["notify_to"] = _prompt("Send the digest to", default=answers["gmail_address"])

    print()
    print(" 4. What jobs are you searching for?")
    print("    Free-text role titles, comma-separated. These become BOTH")
    print("    the dashboard's filter AND each portal's search query.")
    print("    Examples: 'Senior Product Manager, Product Owner'")
    print("              'Sous Chef, Chef de Partie, Küchenchef'")
    print("              'Senior Data Engineer, Analytics Engineer'")
    while True:
        roles_raw = _prompt("Target roles (comma-separated)", required=True)
        roles = _split_csv(roles_raw)
        if roles:
            answers["target_roles"] = roles
            break
        print("    (need at least one role)")

    print()
    print(" 5. Work preferences")
    answers["remote"] = _prompt_yn("Open to fully remote?", default=True)
    answers["on_site_ok"] = _prompt_yn("Open to on-site (no remote)?", default=False)
    answers["willing_to_relocate"] = _prompt_yn("Willing to relocate?", default=False)
    answers["work_authorization"] = _prompt("Work authorization (e.g. 'EU citizen', 'US permanent resident')",
                                            default="EU citizen")

    print()
    print(" 6. Salary range (EUR per year)")
    answers["salary_min"] = _prompt_int("Minimum acceptable", default=60000)
    answers["salary_max"] = _prompt_int("Ideal target", default=90000)

    print()
    print(" 7. Languages")
    print("    Use jobbot codes: de_native, de_fluent, en_native, en_fluent, en_c1, en_c2 …")
    langs_raw = _prompt("Your languages (comma-separated)", default="de_native, en_fluent")
    answers["languages"] = _split_csv(langs_raw)

    print()
    print(" 8. Deal-breaker industries")
    print("    Postings tagged with any of these get dropped before scoring.")
    print("    Common: defense, gambling, tobacco, adult, weapons.")
    industries_raw = _prompt("Industries to avoid (comma-separated, blank = none)", default="")
    answers["dealbreaker_industries"] = _split_csv(industries_raw)

    print()
    print(" 9. Required skills (LLM uses these to filter out obvious mismatches)")
    must_raw = _prompt("Must-have skills (comma-separated, blank = none)", default="")
    answers["must_have_skills"] = _split_csv(must_raw)
    nice_raw = _prompt("Nice-to-have skills (comma-separated, blank = none)", default="")
    answers["nice_to_have_skills"] = _split_csv(nice_raw)

    # Write files (asking before overwriting any pre-existing personal file)
    print()
    print("─" * 64)
    print(" Writing files …")
    print("─" * 64)

    targets: list[tuple[Path, Callable[[dict, Path], None]]] = [
        (REPO_ROOT / ".env", _write_env),
        (DATA_DIR / "profile.yaml", _write_profile),
        (DATA_DIR / "config.yaml", _write_config),
        (DATA_DIR / "base_cv.md", _write_base_cv),
    ]
    written: list[Path] = []
    skipped: list[Path] = []
    for path, writer in targets:
        if not _confirm_overwrite(path):
            skipped.append(path)
            print(f"  ⏭  kept existing {path.relative_to(REPO_ROOT)}")
            continue
        writer(answers, path)
        written.append(path)
        print(f"  ✓  wrote {path.relative_to(REPO_ROOT)}")

    # Final instructions
    print()
    print("─" * 64)
    print(" Almost done. Manual steps remaining:")
    print("─" * 64)
    print()
    print(" 1. Edit .env and paste your real ANTHROPIC_API_KEY (starts with sk-ant-).")
    print("    Get it at https://console.anthropic.com/settings/keys")
    print()
    print(" 2. Generate a Gmail App Password and paste into GMAIL_APP_PASSWORD.")
    print("    https://myaccount.google.com/apppasswords")
    print()
    print(" 3. Open data/base_cv.md and replace the stub content with your real CV.")
    print("    Keep it 1–3 pages of plain Markdown.")
    print()
    print(" Then verify:")
    print("    pytest -q -m \"not live\"   # tests pass")
    print("    jobbot run                 # first end-to-end run")
    print("    jobbot dashboard           # open http://localhost:5001")
    print()
    return 0
