"""Top-level apply flow: pick adapter → fill → handle captcha/OTP → optionally submit."""
from __future__ import annotations

from pathlib import Path

from ..captcha import get_captcha_solver
from ..config import Config, Secrets
from ..models import ApplyResult, GeneratedDocs, JobPosting, JobStatus
from ..otp.imap import OtpFetcher
from ..profile import Profile


def _load_adapters():
    """Lazy — only when auto-apply actually runs (avoids Playwright import cost)."""
    from .adapters.generic import GenericAdapter
    from .adapters.greenhouse import GreenhouseAdapter
    from .adapters.lever import LeverAdapter
    from .adapters.workday import WorkdayAdapter
    return [GreenhouseAdapter(), LeverAdapter(), WorkdayAdapter(), GenericAdapter()]


def apply_to_job(
    job: JobPosting, profile: Profile, docs: GeneratedDocs,
    secrets: Secrets, config: Config,
) -> ApplyResult:
    if not job.apply_url:
        return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                           needs_review_reason="no apply_url on posting")

    # Lazy import — only required for sources where auto_submit is true.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                           needs_review_reason="playwright not installed; run `playwright install chromium`")

    captcha = get_captcha_solver(secrets, config)
    otp = OtpFetcher(secrets, config)
    ADAPTERS = _load_adapters()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        try:
            page.goto(str(job.apply_url), wait_until="networkidle", timeout=30_000)

            adapter = next((a for a in ADAPTERS if a.matches(str(job.apply_url), page)), None)
            if adapter is None:
                return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                                   needs_review_reason="no adapter matched")

            adapter.fill(page, job, profile, docs)

            # Captcha if present (heuristic: a g-recaptcha or hcaptcha element)
            if page.locator(".g-recaptcha, .h-captcha, iframe[src*='recaptcha']").count() > 0:
                ok = captcha.solve_on_page(page, str(job.apply_url))
                if not ok:
                    return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                                       needs_review_reason="captcha not solved in time")

            screenshot_path = str(Path(docs.output_dir) / "apply_preview.png")
            page.screenshot(path=screenshot_path, full_page=True)

            if config.apply.dry_run:
                return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                                   dry_run=True, screenshot_path=screenshot_path,
                                   needs_review_reason="dry-run mode")

            confirmation_url = adapter.submit(page)

            # If the form requires email OTP confirmation after submit
            if "verify" in confirmation_url.lower() or page.locator("input[name*='code']").count() > 0:
                code = otp.wait_for_code(sender_domain=_sender_for(adapter.name))
                if not code:
                    return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                                       needs_review_reason="OTP not received in time",
                                       screenshot_path=screenshot_path)
                page.fill("input[name*='code'], input[name*='otp']", code)
                page.click("button[type=submit]")
                confirmation_url = page.url

            page.screenshot(path=screenshot_path, full_page=True)
            return ApplyResult(status=JobStatus.APPLY_SUBMITTED,
                               submitted=True, screenshot_path=screenshot_path,
                               confirmation_url=confirmation_url)

        except Exception as e:  # noqa: BLE001
            return ApplyResult(status=JobStatus.APPLY_FAILED, error=str(e))
        finally:
            ctx.close()
            browser.close()


def _sender_for(adapter_name: str) -> str:
    return {
        "greenhouse": "greenhouse.io",
        "lever":      "lever.co",
        "workday":    "myworkday.com",
    }.get(adapter_name, "")
