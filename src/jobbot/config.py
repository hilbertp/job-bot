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
    # PRD §7.7 — outbound application channel uses a dedicated business
    # mailbox at hilbert@true-north.berlin (NOT the Gmail digest address).
    # All four fields must be set together for the email channel to send;
    # if any is missing, the channel forces dry-run regardless of config.
    truenorth_smtp_host: str = ""
    truenorth_smtp_port: int = 587
    truenorth_smtp_user: str = ""
    truenorth_smtp_pass: str = ""


class ApplyConfig(BaseModel):
    dry_run: bool = True
    confirm_each: bool = False
    per_run_limit: int = 5
    screener_min_confidence: float = 0.8


class OtpConfig(BaseModel):
    poll_interval_s: int = 5
    timeout_s: int = 120


class CaptchaConfig(BaseModel):
    timeout_s: int = 90
    max_retries: int = 2


class DigestConfig(BaseModel):
    generate_docs_above_score: int = 70
    max_per_email: int = 100


class EnrichmentConfig(BaseModel):
    per_run_cap: int = 100


class SourceConfig(BaseModel):
    enabled: bool = True
    auto_submit: bool = False
    queries: list[dict] = Field(default_factory=list)


class Config(BaseModel):
    score_threshold: int = 70
    max_jobs_per_run: int = 50
    output_dir: str = "output"
    # Path (relative to repo root) to a pre-designed static CV PDF. When this
    # file exists, the generator skips per-job CV tailoring and attaches this
    # PDF as-is — the cover letter remains tailored. Set to None / empty to
    # restore per-job Markdown→HTML→PDF tailoring.
    cv_pdf_path: str | None = "data/general CV.pdf"
    digest: DigestConfig = Field(default_factory=DigestConfig)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    apply: ApplyConfig = Field(default_factory=ApplyConfig)
    otp: OtpConfig = Field(default_factory=OtpConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)


def load_secrets(env_file: Path | None = None) -> Secrets:
    load_dotenv(env_file or REPO_ROOT / ".env")
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
    )


def load_config(path: Path | None = None) -> Config:
    p = path or REPO_ROOT / "data" / "config.yaml"
    if not p.exists():
        # Fall back to the example so a fresh checkout still runs --help.
        p = REPO_ROOT / "data" / "config.example.yaml"
    return Config.model_validate(yaml.safe_load(p.read_text()))
