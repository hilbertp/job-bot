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


def test_runner_supervised_does_not_call_adapter_submit():
    """The supervised path must NOT call `adapter.submit(page)` — the
    user does that click manually in the visible browser. If a refactor
    accidentally re-introduces the auto-click, supervised mode stops
    being supervised."""
    from jobbot.applier import runner as runner_mod
    src = inspect.getsource(runner_mod)
    # Find the supervised block (between the `if supervised:` marker and
    # the next `confirmation_url = adapter.submit(page)` line, which is
    # the headless path's submit call).
    sup_marker = src.index("if supervised:")
    headless_submit = src.index("confirmation_url = adapter.submit(page)", sup_marker)
    supervised_block = src[sup_marker:headless_submit]
    assert "adapter.submit" not in supervised_block, (
        "supervised mode must not call adapter.submit — the human is "
        "responsible for the final click"
    )
    # And the supervised block must poll for success.
    assert "_verify_post_submit" in supervised_block, (
        "supervised mode must poll _verify_post_submit to detect when "
        "the human-driven submission lands"
    )
