"""Supervised mode: the runner pre-fills a form in a visible Chrome
window using a persistent profile, then waits for the human to click
Send / solve any CAPTCHA. No auto-submit click.

These tests cover the config plumbing + the static expectations of the
runner code; they do NOT exercise a real browser (that requires the
Playwright + Chromium environment and is covered by manual / live
testing). The browser-driven flow is small and well-isolated; the
risk surface this catches is config drift, accidental flag removal,
and the import-not-found cliff.
"""
from __future__ import annotations

import inspect

from jobbot.config import ApplyConfig


def test_supervised_flag_defaults_to_false():
    """Default ApplyConfig stays backwards-compat — supervised mode is
    opt-in. Any change to this default must be explicit in a PR."""
    cfg = ApplyConfig()
    assert cfg.supervised is False
    # Defaults for the other supervised-specific knobs are stable too.
    assert cfg.user_data_dir == ""
    assert cfg.supervised_timeout_seconds == 600


def test_supervised_knobs_round_trip_through_pydantic():
    """A user wiring `supervised: true` in data/config.yaml must be
    able to set the matching dir + timeout without a schema error."""
    cfg = ApplyConfig(
        supervised=True,
        user_data_dir="/tmp/jobbot-test-profile",
        supervised_timeout_seconds=120,
    )
    assert cfg.supervised is True
    assert cfg.user_data_dir == "/tmp/jobbot-test-profile"
    assert cfg.supervised_timeout_seconds == 120


def test_runner_branches_on_supervised_flag():
    """Sanity check: the runner module mentions `supervised` and routes
    through `launch_persistent_context`. Catches the case where a
    refactor accidentally removes the supervised path."""
    from jobbot.applier import runner as runner_mod
    src = inspect.getsource(runner_mod)
    assert "config.apply.supervised" in src, (
        "runner.py must read config.apply.supervised to branch into the "
        "supervised path"
    )
    assert "launch_persistent_context" in src, (
        "supervised path must use launch_persistent_context (persistent "
        "profile that retains cookies across runs); a refactor that loses "
        "this falls back to ephemeral headless and re-trips bot-detection"
    )
    assert "AutomationControlled" in src, (
        "supervised launch must pass --disable-blink-features=AutomationControlled "
        "so the visible Chrome window is less obviously a Playwright instance"
    )
    assert "navigator, 'webdriver'" in src, (
        "supervised path must inject the navigator.webdriver=undefined "
        "init script so common bot-detection heuristics don't fire"
    )


def test_runner_supervised_clicks_submit_and_polls_for_success():
    """Supervised mode = "watch the bot do everything." The bot fills,
    the bot clicks Send, the user just watches. If a CAPTCHA appears,
    the user solves it in the visible window during the post-submit
    polling window — the bot detects the eventual success page.

    Earlier this mode skipped the submit click and waited for the
    human; user corrected the design on 2026-05-15: *"i dont send my
    self, the bot needs to send while i watch"*.
    """
    from jobbot.applier import runner as runner_mod
    src = inspect.getsource(runner_mod)
    # Slice the supervised block. The marker line is `if supervised:`
    # (there are two — the early branch for browser launch + the
    # post-fill branch); we want the SECOND one (the submit-and-poll
    # block). The headless path's own `adapter.submit` call is the
    # next occurrence after the supervised block ends.
    first_if = src.index("if supervised:")
    second_if = src.index("if supervised:", first_if + 1)
    end_of_block = src.index("\n            # ", second_if + 1)
    block = src[second_if:end_of_block]
    # Bot must call adapter.submit inside the supervised block.
    assert "adapter.submit" in block, (
        "supervised mode now drives the submit click itself — the bot "
        "fills AND clicks Send while the user watches"
    )
    # Bot must poll for success (so a CAPTCHA-blocked submit is not
    # incorrectly recorded as APPLY_SUBMITTED).
    assert "_verify_post_submit" in block, (
        "supervised mode must poll _verify_post_submit after the click "
        "so a CAPTCHA wall or unknown post-submit state surfaces as "
        "NEEDS_REVIEW instead of being falsely claimed as submitted"
    )
