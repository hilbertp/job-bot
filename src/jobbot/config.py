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


class SourceConfig(BaseModel):
    enabled: bool = True
    auto_submit: bool = False
    queries: list[dict] = Field(default_factory=list)


class Config(BaseModel):
    score_threshold: int = 70
    max_jobs_per_run: int = 50
    output_dir: str = "output"
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    apply: ApplyConfig = Field(default_factory=ApplyConfig)
    otp: OtpConfig = Field(default_factory=OtpConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)


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
    )


def load_config(path: Path | None = None) -> Config:
    p = path or REPO_ROOT / "data" / "config.yaml"
    if not p.exists():
        # Fall back to the example so a fresh checkout still runs --help.
        p = REPO_ROOT / "data" / "config.example.yaml"
    return Config.model_validate(yaml.safe_load(p.read_text()))
