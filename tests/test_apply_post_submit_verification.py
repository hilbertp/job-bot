"""`_verify_post_submit` is the function the apply runner uses to decide
whether to claim APPLY_SUBMITTED or downgrade to APPLY_NEEDS_REVIEW
after the submit click. It's the single most important guardrail
against the runner overclaiming success on weak signals (URL change
alone is not proof — the page might be a CAPTCHA wall or an unknown
state).

This pins the three return values it should produce, against fake page
objects that simulate the post-submit page states we've seen live.
"""
from __future__ import annotations

from jobbot.applier.runner import _verify_post_submit


class _FakeLocator:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class _FakePage:
    """Minimal stub of a Playwright page that exposes the two interfaces
    `_verify_post_submit` reaches for: `locator(sel).count()` and
    `evaluate(js)` (we only call one JS expression — reading body text)."""

    def __init__(self, body_text: str = "", captcha_selectors: tuple = ()):
        self._body = body_text
        self._captcha_hits = set(captcha_selectors)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(1 if selector in self._captcha_hits else 0)

    def evaluate(self, js: str) -> str:
        # The function passes ONLY the body-text-read JS.
        return self._body.lower()


def test_captcha_present_returns_captcha():
    """A CAPTCHA on the post-submit page means NOT submitted, no matter
    what other text is visible. This was the GTO Wizard regression on
    2026-05-13: URL had advanced to /c/new, body even said 'thank you',
    but the page was overlaid with a custom CAPTCHA — application
    was not actually accepted."""
    page = _FakePage(
        body_text="Thank you for your application",
        captcha_selectors=(".g-recaptcha",),
    )
    assert _verify_post_submit(page) == "captcha"


def test_recaptcha_iframe_treated_as_captcha():
    page = _FakePage(captcha_selectors=("iframe[src*='recaptcha']",))
    assert _verify_post_submit(page) == "captcha"


def test_hcaptcha_iframe_treated_as_captcha():
    page = _FakePage(captcha_selectors=("iframe[src*='hcaptcha']",))
    assert _verify_post_submit(page) == "captcha"


def test_success_text_returns_success():
    page = _FakePage(body_text="We received your application! We'll be in touch.")
    assert _verify_post_submit(page) == "success"


def test_german_success_text_returns_success():
    """Recruitee + JOIN show German success copy on German postings."""
    page = _FakePage(body_text="Vielen Dank für Ihre Bewerbung")
    assert _verify_post_submit(page) == "success"


def test_no_evidence_returns_unknown():
    """Empty page or a generic next-step page with no captcha and no
    success text should return 'unknown' — the runner then surfaces to
    the user as APPLY_NEEDS_REVIEW rather than claiming submission."""
    page = _FakePage(body_text="Please continue to the next step")
    assert _verify_post_submit(page) == "unknown"


def test_empty_body_returns_unknown():
    page = _FakePage(body_text="")
    assert _verify_post_submit(page) == "unknown"
