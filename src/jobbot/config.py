"""Configuration loading: .env (secrets) + data/config.yaml (behavior)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]


class Secrets(BaseModel):
    anthropic_api_key: str
    gmail_address: str
    gmail_app_password: str
    notify_to: str
    captcha_provider: str = "twocaptcha"
    captcha_api_key: str = ""
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    # PRD §7.7, outbound application channel uses a dedicated business
    # mailbox at hilbert@true-north.berlin (NOT the Gmail digest address).
    # All four fields must be set together for the email channel to send;
    # if any is missing, the channel forces dry-run regardless of config.
    truenorth_smtp_host: str = ""
    truenorth_smtp_port: int = 587
    truenorth_smtp_user: str = ""
    truenorth_smtp_pass: str = ""
    # IMAP for the outbound mailbox, the inbox scanner reads replies +
    # bounces here and auto-advances the dashboard cards. Same login as
    # SMTP on IONOS; defaults to imap.ionos.de:993.
    truenorth_imap_host: str = "imap.ionos.de"
    truenorth_imap_port: int = 993


class ApplyConfig(BaseModel):
    dry_run: bool = True
    confirm_each: bool = False
    per_run_limit: int = 5
    screener_min_confidence: float = 0.8
    # Supervised mode: launch a VISIBLE Chrome/Brave window using a
    # persistent profile, fill the form, but do NOT click submit, the
    # human is in the loop for that final click + any CAPTCHA / 2FA / login
    # wall. Cookies persist across runs in `user_data_dir` so the second
    # visit to the same site looks like a returning user (bot-detection
    # is much less likely to fire). Default off, preserves the legacy
    # headless behaviour for backwards compat.
    supervised: bool = False
    # Where Playwright's persistent context stores cookies, cache,
    # extensions. Default is `~/.jobbot/chrome-profile` (resolved at
    # use-time so the path adapts to the running user's $HOME). The
    # directory is created on first use; subsequent runs reuse the
    # same cookies and fingerprint.
    user_data_dir: str = ""
    # Max time the supervised runner waits for the user to click Send
    # and the page to show a success-indicator. 10 min is generous for
    # solving a CAPTCHA; reducing it makes the runner give up faster.
    supervised_timeout_seconds: int = 600
    # Chrome DevTools Protocol endpoint of the user's REAL browser
    # (Brave launched with --remote-debugging-port=9222). When set, the
    # runner ATTACHES to that browser via connect_over_cdp instead of
    # launching a fresh Playwright Chromium, so applies run inside the
    # user's logged-in session, real cookies, real fingerprint, human
    # history. This defeats bot-detection / CAPTCHAs that flag the empty
    # "Chrome for Testing" profile. Also settable via the CDP_URL env var.
    # Empty = fall back to supervised/headless launch.
    cdp_url: str = ""


class OtpConfig(BaseModel):
    poll_interval_s: int = 5
    timeout_s: int = 120


class CaptchaConfig(BaseModel):
    timeout_s: int = 90
    max_retries: int = 2


class DigestConfig(BaseModel):
    generate_docs_above_score: int = 70
    max_per_email: int = 100
    # PRD §7.6 / product journey stage 4: only the top-N highest-scoring
    # postings per run get tailored CV + cover letter generation. Everything
    # else above `generate_docs_above_score` stays in the shortlist (visible
    # in the digest + dashboard) without burning LLM calls. User controls
    # how often they trigger a run, there is no daily cap.
    generate_top_n: int = 5


class EnrichmentConfig(BaseModel):
    per_run_cap: int = 100


class PublishConfig(BaseModel):
    """Static-site publishing (GitHub Pages) + local Downloads export.

    `jobbot publish` reads the SQLite state, renders a self-contained
    static dashboard (index.html + data.json + generated PDFs), commits it
    to the working copy at `pages_repo_dir`, and pushes to
    `pages_repo_url`. It also copies each generated CV / cover letter /
    application package into `downloads_dir` exactly once.
    """
    enabled: bool = True
    site_title: str = "Job Bot: Daily Matches"
    # Only rows with a base score >= min_score appear on the site.
    min_score: int = 60
    # Only rows first seen within this many days appear on the site.
    max_age_days: int = 45
    # Hard cap on rows in data.json / index.html, highest score first.
    max_jobs: int = 300
    # Git remote of the GitHub Pages repo (e.g. the user-site repo
    # https://github.com/<user>/<user>.github.io.git). Empty = build the
    # site locally but skip the git publish step.
    pages_repo_url: str = ""
    # Local working copy used for the publish commit. Empty = ~/.jobbot/pages-repo.
    pages_repo_dir: str = ""
    pages_branch: str = "main"
    # Copy generated PDFs into the site's docs/ tree so the dashboard can
    # link them. The user-site Pages repo is PUBLIC; set false to keep
    # documents off the web and rely on the Downloads export instead.
    include_documents: bool = True
    # Where generated documents are exported locally. Empty = ~/Downloads/jobbot.
    downloads_dir: str = ""
    downloads_enabled: bool = True


class SourceConfig(BaseModel):
    enabled: bool = True
    auto_submit: bool = False
    queries: list[dict] = Field(default_factory=list)


class Config(BaseModel):
    score_threshold: int = 70
    max_jobs_per_run: int = 50
    output_dir: str = "output"
    # Hard salary floor in EUR/year. When a posting STATES a salary range
    # whose top end (after currency + period normalisation to EUR/year)
    # falls below this number, the row is filtered out before LLM scoring,
    # so we never spend scoring/generation cycles on a role that pays well
    # under the candidate's level. Postings that state no salary are left
    # alone (we don't penalise unknown comp). 0 disables the filter.
    salary_floor_eur_year: int = 0
    # Sources whose comp is hourly (freelance projects), not an annual
    # salary. These are EXEMPT from salary_floor_eur_year (a "800 EUR/Tag"
    # day-rate would otherwise be misread as 800 EUR/year and wrongly
    # dropped). Instead they're held to `freelance_hourly_floor_eur`.
    freelance_sources: list[str] = Field(default_factory=list)
    # Minimum acceptable freelance rate in EUR/hour. Postings on a
    # freelance source whose stated rate is below this are filtered;
    # postings that state no rate pass through. 0 disables.
    freelance_hourly_floor_eur: float = 0.0
    # Apply-path research: during enrichment, for rows whose only apply
    # link is a paywalled aggregator, web-search for the canonical
    # employer apply URL (one Anthropic web_search call per researched
    # row). Off by default; adds per-row LLM + search cost. The per-run
    # cap bounds spend/latency. Rows that already have a usable
    # non-paywalled route are skipped.
    apply_research_enabled: bool = False
    apply_research_max_per_run: int = 50
    # When False (default), the generation step REUSES an existing CV +
    # cover letter on disk instead of re-calling the LLM, so daily runs
    # don't re-spend on profiles already produced. Set True to force
    # regeneration (e.g. after updating the base CV or prompts).
    regenerate_existing_docs: bool = False
    # Path (relative to repo root) to a pre-designed static CV PDF. When this
    # file exists, the generator skips per-job CV tailoring and attaches this
    # PDF as-is, the cover letter remains tailored. Set to None / empty to
    # restore per-job Markdown→HTML→PDF tailoring.
    cv_pdf_path: str | None = "data/general CV.pdf"
    digest: DigestConfig = Field(default_factory=DigestConfig)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    apply: ApplyConfig = Field(default_factory=ApplyConfig)
    otp: OtpConfig = Field(default_factory=OtpConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)


def load_secrets(env_file: Path | None = None) -> Secrets:
    # override=True: `.env` is this project's canonical config. A stale
    # shell env var (e.g. ANTHROPIC_API_KEY='' inherited from some prior
    # tool) must NOT silently shadow the real key in .env. Without
    # override the dashboard's rescore endpoint dies with the Anthropic
    # SDK error "Could not resolve authentication method".
    load_dotenv(env_file or REPO_ROOT / ".env", override=True)
    return Secrets(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        gmail_address=os.environ["GMAIL_ADDRESS"],
        gmail_app_password=os.environ["GMAIL_APP_PASSWORD"],
        notify_to=os.environ.get("NOTIFY_TO", os.environ["GMAIL_ADDRESS"]),
        captcha_provider=os.environ.get("CAPTCHA_PROVIDER", "twocaptcha"),
        captcha_api_key=os.environ.get("CAPTCHA_API_KEY", ""),
        imap_host=os.environ.get("IMAP_HOST", "imap.gmail.com"),
        imap_port=int(os.environ.get("IMAP_PORT", "993")),
        truenorth_smtp_host=os.environ.get("TRUENORTH_SMTP_HOST", ""),
        truenorth_smtp_port=int(os.environ.get("TRUENORTH_SMTP_PORT", "587")),
        truenorth_smtp_user=os.environ.get("TRUENORTH_SMTP_USER", ""),
        truenorth_smtp_pass=os.environ.get("TRUENORTH_SMTP_PASS", ""),
        truenorth_imap_host=os.environ.get("TRUENORTH_IMAP_HOST", "imap.ionos.de"),
        truenorth_imap_port=int(os.environ.get("TRUENORTH_IMAP_PORT", "993")),
    )


def load_config(path: Path | None = None) -> Config:
    p = path or REPO_ROOT / "data" / "config.yaml"
    if not p.exists():
        # Fall back to the example so a fresh checkout still runs --help.
        p = REPO_ROOT / "data" / "config.example.yaml"
    return Config.model_validate(yaml.safe_load(p.read_text()))
