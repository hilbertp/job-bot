"""Top-level apply flow: pick adapter → fill → handle captcha/OTP → optionally submit."""
from __future__ import annotations

from pathlib import Path

from ..captcha import get_captcha_solver
from ..config import Config, Secrets
from ..models import ApplyResult, GeneratedDocs, JobPosting, JobStatus
from ..otp.imap import OtpFetcher
from ..profile import Profile


# Words / phrases that appear on a real "thank you, we received your
# application" page. Multi-language because Recruitee + JOIN + scope-
# recruiting all show German variants on German postings. Match is
# case-insensitive substring.
_SUCCESS_TEXT_NEEDLES = (
    "thank you",
    "thanks for applying",
    "application received",
    "application sent",
    "successfully submitted",
    "we received your application",
    "we've received your application",
    "vielen dank",
    "bewerbung eingegangen",
    "bewerbung erhalten",
)

# Selectors for common CAPTCHA implementations. If any of these is
# present AFTER the submit click, the application is NOT submitted —
# the candidate is at a bot-detection wall and needs to finish manually.
_CAPTCHA_SELECTORS = (
    ".g-recaptcha",
    ".h-captcha",
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[title*='recaptcha' i]",
    "iframe[title*='captcha' i]",
    "[class*='captcha' i]",
    "[id*='captcha' i]",
)


def _verify_post_submit(page) -> str:
    """Inspect the post-submit page state and return one of:
      - "captcha":  a CAPTCHA wall is up; submission is NOT complete.
      - "success":  a recognised success-indicator text was found.
      - "unknown":  page changed but we can't tell — surface to user.

    The runner uses this to refuse claiming APPLY_SUBMITTED on weak
    signals (URL change alone, click-didn't-raise alone). Documented in
    feedback memory `feedback_no_overclaiming_success.md` after a real
    incident on 2026-05-13 where a Recruitee captcha was mistaken for
    a successful submission.
    """
    # CAPTCHA wins over success-text — if a CAPTCHA is on the page,
    # the application is NOT actually submitted regardless of what
    # other text might be visible.
    for sel in _CAPTCHA_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return "captcha"
        except Exception:
            continue
    # Look for a success-indicator phrase anywhere in body text.
    try:
        body_text = page.evaluate(
            "() => document.body ? document.body.innerText.toLowerCase() : ''"
        )
        for needle in _SUCCESS_TEXT_NEEDLES:
            if needle in body_text:
                return "success"
    except Exception:
        pass
    return "unknown"


# URL path patterns that indicate a job listing was pulled. When the
# apply_url redirects to one of these (or matches one of them directly),
# the listing is no longer accepting applications. Consensys's Greenhouse
# 'jobs/{id}' page redirects to `consensys.io/open-roles` once a role
# closes; same pattern with `/careers`, `/jobs/search`, `/positions`,
# generic 404 pages, etc.
_EXPIRED_URL_PATTERNS = (
    "/open-roles",
    "/openings",
    "/careers/index",
    "/jobs/search",
    "/jobs/all",
    "/job-search",
    "/job-not-found",
    "/job_expired",
    "expired",
    "no-longer-available",
    "404",
)


def _is_expired_listing(final_url: str, response_status: int) -> tuple[bool, str]:
    """Return (is_expired, reason) for a listing whose apply_url no longer
    resolves to an application form. Two signals:

      1. HTTP 403 / 404 / 410 on the apply_url (the job was deleted).
      2. The URL after redirects lands on a known "generic" path —
         /open-roles, /careers/index, /jobs/search, etc. — meaning the
         specific posting redirected to the company's hiring index.

    Both signals are strong; if either fires the runner should NOT try
    to fill any form and should mark the row LISTING_EXPIRED so the
    dashboard surfaces an ⏱ pill.
    """
    if response_status in (403, 404, 410):
        return True, f"HTTP {response_status} from apply_url"
    if final_url:
        lower = final_url.lower()
        for needle in _EXPIRED_URL_PATTERNS:
            if needle in lower:
                # Avoid false positives on /jobs/{id} URLs that legitimately
                # contain the substring 'jobs' — we require a generic
                # PATH segment, not a numeric job-id suffix.
                if needle == "404" and "/404" not in lower:
                    continue
                return True, f"apply_url redirected to a generic page ({final_url})"
    return False, ""


def _load_adapters():
    """Lazy — only when auto-apply actually runs (avoids Playwright import cost).

    Order matters: more-specific adapters first, GenericAdapter last as
    the dry-run-only fallback. Recruitee is listed before Generic so the
    GTO-Wizard-style postings get the real adapter; everything truly
    unknown still falls through to Generic.
    """
    from .adapters.generic import GenericAdapter
    from .adapters.greenhouse import GreenhouseAdapter
    from .adapters.lever import LeverAdapter
    from .adapters.recruitee import RecruiteeAdapter
    from .adapters.workday import WorkdayAdapter
    return [
        GreenhouseAdapter(),
        LeverAdapter(),
        WorkdayAdapter(),
        RecruiteeAdapter(),
        GenericAdapter(),
    ]


def apply_to_job(
    job: JobPosting, profile: Profile, docs: GeneratedDocs,
    secrets: Secrets, config: Config,
) -> ApplyResult:
    # Route to the email channel first when the enrichment step extracted
    # a careers/jobs/bewerbung mailbox from the posting — sending an email
    # is simpler and more reliable than driving a web form, and matches
    # PRD §7.7 FR-APP-02. The email channel itself enforces dry-run when
    # SMTP creds are missing, so this is safe even before the operator
    # finishes wiring TRUENORTH_SMTP_*.
    if job.apply_email:
        from .email_channel import send_email_application
        return send_email_application(job, profile, docs, secrets, config)

    if not job.apply_url:
        return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                           needs_review_reason="no apply_url on posting")

    # Lazy import — only required for sources where auto_submit is true.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ApplyResult(status=JobStatus.APPLY_NEEDS_REVIEW,
                           needs_review_reason="playwright not installed; run `playwright install chromium`")

    # PRE-FLIGHT: is the listing still live? An HTTP HEAD against the
    # apply_url is cheap and saves us launching Chromium / consuming a
    # supervised slot when the role has been pulled. Detects 403 / 404 /
    # 410 directly, and redirect-to-generic-careers via the final URL.
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=10) as client:
            head = client.head(str(job.apply_url))
            expired, reason = _is_expired_listing(str(head.url), head.status_code)
            if expired:
                return ApplyResult(
                    status=JobStatus.LISTING_EXPIRED,
                    needs_review_reason=f"listing expired — {reason}",
                )
    except Exception:
        # Network blip on the HEAD shouldn't kill the apply; only mark
        # expired when we have positive evidence. Carry on to the
        # browser launch.
        pass

    captcha = get_captcha_solver(secrets, config)
    otp = OtpFetcher(secrets, config)
    ADAPTERS = _load_adapters()

    supervised = bool(config.apply.supervised)

    with sync_playwright() as pw:
        if supervised:
            # Persistent-context launch with the user's dedicated profile:
            # cookies/cache survive across runs so the 2nd visit to a site
            # looks like a returning user. Non-headless so the human can
            # eyeball + intervene (CAPTCHA, 2FA, login wall). The init
            # script papers over the most obvious automation tell —
            # `navigator.webdriver` defaulting to `true` under Playwright.
            user_data_dir = (
                config.apply.user_data_dir
                or str(Path.home() / ".jobbot" / "chrome-profile")
            )
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            browser = None  # nothing to close; ctx.close() handles it in finally
        else:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15",
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

        try:
            # `networkidle` is too strict for SPA-heavy ATSes (Recruitee fires
            # continuous analytics/heartbeat traffic and never reaches a quiet
            # state). `domcontentloaded` gets us past the initial HTML parse;
            # the adapter then waits for its specific form input to mount
            # before filling. Net: more reliable across modern ATS hosts,
            # same behaviour for static/inline forms.
            page.goto(str(job.apply_url), wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)  # let SPA framework settle

            # POST-NAVIGATE EXPIRED CHECK — some ATSes redirect via JS
            # after the initial HTML loads (Greenhouse 7551395 → consensys.io/open-roles).
            # The HEAD-based pre-flight catches HTTP-level redirects; this
            # catches the JS-level ones.
            expired_now, expired_reason = _is_expired_listing(page.url, 200)
            if expired_now:
                return ApplyResult(
                    status=JobStatus.LISTING_EXPIRED,
                    needs_review_reason=f"listing expired — {expired_reason}",
                )

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

            # SUPERVISED MODE — "watch the bot do everything" semantics.
            # The bot fills the form AND clicks Send. The user is watching
            # the visible Chrome window and only intervenes if a CAPTCHA
            # or other gate appears (in which case they solve it in-window;
            # the bot's success-polling will detect when the page advances
            # to a thank-you state and record APPLY_SUBMITTED).
            #
            # Earlier this mode pre-filled but did NOT click Send; user
            # corrected the design on 2026-05-15: *"i dont send my self,
            # the bot needs to send while i watch"*.
            if supervised:
                timeout_s = config.apply.supervised_timeout_seconds
                print(
                    f"\n  ⏳ SUPERVISED: form pre-filled at {page.url}.\n"
                    f"     The bot is about to click Send. Watch the Chrome\n"
                    f"     window — if a CAPTCHA appears, solve it in-place;\n"
                    f"     the bot will detect the success page and finish.\n"
                    f"     Polling for success up to {timeout_s}s ...\n"
                )
                # Bot clicks Send. Any post-click wait inside the adapter
                # already tolerates timeouts via the success-text wait.
                try:
                    confirmation_url = adapter.submit(page)
                except Exception as submit_err:
                    # Submit may raise if the button selector misses or
                    # the page state is unexpected — surface the error
                    # but keep polling: the user might still be able to
                    # click Send manually inside the visible window.
                    print(f"     ! adapter.submit raised: {submit_err}")
                    confirmation_url = page.url

                import time as _time
                deadline = _time.monotonic() + timeout_s
                final_verdict = "unknown"
                while _time.monotonic() < deadline:
                    try:
                        v = _verify_post_submit(page)
                    except Exception:
                        v = "unknown"
                    if v == "success":
                        final_verdict = "success"; break
                    _time.sleep(3)
                # Capture the final state regardless of outcome.
                page.screenshot(path=screenshot_path, full_page=True)
                confirmation_url = page.url
                if final_verdict == "success":
                    return ApplyResult(
                        status=JobStatus.APPLY_SUBMITTED,
                        submitted=True,
                        screenshot_path=screenshot_path,
                        confirmation_url=confirmation_url,
                    )
                return ApplyResult(
                    status=JobStatus.APPLY_NEEDS_REVIEW,
                    needs_review_reason=(
                        "supervised: bot clicked Send but no success "
                        "indicator appeared within the timeout. If a "
                        "CAPTCHA is on screen and you can solve it, do "
                        "so — the polling stopped but the page may still "
                        "complete. Otherwise re-run."
                    ),
                    screenshot_path=screenshot_path,
                    confirmation_url=confirmation_url,
                )

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

            # Capture the post-submit state regardless of outcome — this
            # is the screenshot the user reviews in Stage 4.
            page.screenshot(path=screenshot_path, full_page=True)

            # POST-SUBMIT VERIFICATION — a URL change or HTTP 200 is NOT
            # proof of submission. We confirm only when the receiving
            # platform shows positive evidence (a success indicator on the
            # post-submit page) AND there's no CAPTCHA wall blocking the
            # next step.
            verdict = _verify_post_submit(page)
            if verdict == "captcha":
                return ApplyResult(
                    status=JobStatus.APPLY_NEEDS_REVIEW,
                    needs_review_reason=(
                        "submit click fired, page advanced, but a CAPTCHA "
                        "blocks the next step. Manual completion required."
                    ),
                    screenshot_path=screenshot_path,
                    confirmation_url=confirmation_url,
                )
            if verdict == "success":
                return ApplyResult(
                    status=JobStatus.APPLY_SUBMITTED,
                    submitted=True,
                    screenshot_path=screenshot_path,
                    confirmation_url=confirmation_url,
                )
            # Default: unknown post-submit state. Don't claim submission;
            # surface to the user for manual review.
            return ApplyResult(
                status=JobStatus.APPLY_NEEDS_REVIEW,
                needs_review_reason=(
                    "submit click fired and page advanced, but no success "
                    "indicator was found on the post-submit page. Check "
                    "manually for a confirmation email or visit the URL "
                    "to verify."
                ),
                screenshot_path=screenshot_path,
                confirmation_url=confirmation_url,
            )

        except Exception as e:  # noqa: BLE001
            # ALWAYS try to capture a post-failure screenshot so the user
            # has evidence of what state the page was in at the moment of
            # error. Without this, a submit click that fired but then
            # timed out on a post-click wait looks identical to a submit
            # click that never happened — and we have no way to tell the
            # user "your application probably went through, here's what
            # the success page looked like". The screenshot may overwrite
            # the pre-submit one, which is acceptable: the post-failure
            # state is strictly more diagnostic.
            failure_screenshot = None
            try:
                if docs and docs.output_dir:
                    failure_screenshot = str(Path(docs.output_dir) / "apply_failure.png")
                    page.screenshot(path=failure_screenshot, full_page=True)
            except Exception:
                pass
            return ApplyResult(
                status=JobStatus.APPLY_FAILED,
                error=str(e),
                screenshot_path=failure_screenshot,
            )
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            # `browser` is None in supervised mode (persistent context owns
            # its own browser process). Headless mode keeps the explicit
            # browser reference so we can close it here.
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass


def _sender_for(adapter_name: str) -> str:
    return {
        "greenhouse": "greenhouse.io",
        "lever":      "lever.co",
        "workday":    "myworkday.com",
    }.get(adapter_name, "")
