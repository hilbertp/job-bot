"""Heuristic fallback for unrecognized forms — best-effort field matching by name/label."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile


class GenericAdapter:
    name = "generic"

    def matches(self, url: str, page: "Page") -> bool:
        return True  # always matches as last resort

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal
        # Try common name/email/phone field patterns; skip silently if not present.
        for selector, value in [
            ("input[name*='name' i][type=text]", p["full_name"]),
            ("input[type=email]",                p["email"]),
            ("input[type=tel]",                  p.get("phone", "")),
        ]:
            try:
                if page.locator(selector).count() > 0:
                    page.fill(selector, value)
            except Exception:
                pass

    def submit(self, page: "Page") -> str:
        # Don't auto-click in generic mode — too risky. Caller will dry-run only.
        raise NotImplementedError("generic adapter is dry-run only")
