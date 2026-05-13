"""The apply runner picks adapters in a fixed order; this file pins:
  1. Recruitee is registered ahead of the GenericAdapter fallback.
  2. Each adapter has the public method shape (`name`, `matches`,
     `fill`, `submit`) the runner depends on.
  3. `matches()` returns True for the URL substring each adapter owns
     and False for an unrelated URL.

We deliberately do NOT exercise Playwright here — those calls happen
inside `fill()` / `submit()`. The static contract is what protects us
from accidentally dropping an adapter during a refactor.
"""
from __future__ import annotations

from jobbot.applier.runner import _load_adapters


class _FakePage:
    """Tiny stub for the matches() URL-substring check — none of the
    adapter matches() implementations we test here touch the page object
    when the URL substring is enough on its own, but some fall through
    to `page.locator(...)`. The stub returns a locator with `.count() == 0`
    so those paths take the negative branch."""
    def __init__(self):
        pass

    def locator(self, _selector: str):
        class _Loc:
            def count(self):
                return 0
        return _Loc()


def test_recruitee_registered_before_generic_fallback():
    names = [a.name for a in _load_adapters()]
    assert "recruitee" in names, f"recruitee adapter missing from registry: {names}"
    # Generic is the dry-run-only fallback — must be LAST so anything more
    # specific wins.
    assert names[-1] == "generic", (
        f"generic must be last in adapter order; got {names}"
    )
    assert names.index("recruitee") < names.index("generic")


def test_each_adapter_has_required_public_methods():
    for a in _load_adapters():
        for attr in ("name", "matches", "fill", "submit"):
            assert hasattr(a, attr), f"{type(a).__name__} missing {attr!r}"
        assert isinstance(a.name, str) and a.name


def test_recruitee_matches_recruitee_urls():
    from jobbot.applier.adapters.recruitee import RecruiteeAdapter
    a = RecruiteeAdapter()
    page = _FakePage()
    assert a.matches("https://gtowizard.recruitee.com/o/product-manager-3", page)
    assert a.matches("https://anyorg.recruitee.com/o/some-role", page)
    assert not a.matches("https://example.com/jobs/123", page)


def test_greenhouse_matches_both_modern_and_legacy_hosts():
    from jobbot.applier.adapters.greenhouse import GreenhouseAdapter
    a = GreenhouseAdapter()
    page = _FakePage()
    assert a.matches("https://boards.greenhouse.io/acme/jobs/12345", page)
    assert a.matches("https://job-boards.greenhouse.io/backblaze/jobs/5210076008", page)
    assert not a.matches("https://example.com/jobs/123", page)


def test_greenhouse_does_not_match_recruitee_url():
    """Defensive: the runner picks the first matching adapter, so a stray
    cross-match between Greenhouse and Recruitee URLs would silently route
    a Recruitee job through the Greenhouse adapter."""
    from jobbot.applier.adapters.greenhouse import GreenhouseAdapter
    a = GreenhouseAdapter()
    page = _FakePage()
    assert not a.matches("https://gtowizard.recruitee.com/o/product-manager-3", page)


def test_recruitee_does_not_match_greenhouse_url():
    """Mirror of the above — Recruitee must not falsely claim a Greenhouse URL."""
    from jobbot.applier.adapters.recruitee import RecruiteeAdapter
    a = RecruiteeAdapter()
    page = _FakePage()
    assert not a.matches("https://job-boards.greenhouse.io/backblaze/jobs/5210076008", page)
