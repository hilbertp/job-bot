"""Workday — large enterprise ATS, multi-step flow. Hardest to automate.

Workday tenants live at <company>.myworkdayjobs.com and require:
  - account creation (often) or sign-in via email link
  - multi-page form: profile / experience / questions / review / submit
This adapter handles the simplest case (already-signed-in single-page apply).
For first-time applications, mark NEEDS_REVIEW.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile


class WorkdayAdapter:
    name = "workday"

    def matches(self, url: str, page: "Page") -> bool:
        return "myworkdayjobs.com" in url

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        # Require account — Workday always needs one; if signup visible, bail.
        if page.locator("text=Create Account, text=Sign In").count() > 0:
            raise NotImplementedError("Workday login/signup wall — needs human")

        p = profile.personal
        # Step 1 — Personal info (selectors stable across most tenants)
        _fill_if_present(page, "[data-automation-id='legalNameSection_firstName']",
                         p["full_name"].split()[0])
        _fill_if_present(page, "[data-automation-id='legalNameSection_lastName']",
                         p["full_name"].split()[-1])
        _fill_if_present(page, "[data-automation-id='email']", p["email"])
        _fill_if_present(page, "[data-automation-id='phone-number']", p.get("phone", ""))
        _fill_if_present(page, "input[data-automation-id*='address']",
                         p.get("location", {}).get("city", "") if isinstance(p.get("location"), dict)
                         else "")

        # Resume upload (Workday has a dedicated "My Experience" file input)
        if docs.cv_pdf:
            resume_loc = page.locator(
                "[data-automation-id='file-upload-input-ref'], "
                "input[type=file][name*='resume'], input[type=file]"
            )
            if resume_loc.count() > 0:
                resume_loc.first.set_input_files(docs.cv_pdf)

        # Try to advance past the first page ("Next" button)
        next_btn = page.locator(
            "[data-automation-id='bottom-navigation-next-button'], "
            "button:has-text('Next'), button:has-text('Weiter')"
        )
        if next_btn.count() > 0:
            next_btn.first.click()
            page.wait_for_load_state("networkidle")

    def submit(self, page: "Page") -> str:
        page.click(
            "[data-automation-id='bottom-navigation-next-button']:has-text('Submit'), "
            "button[data-automation-id='submit'], "
            "button:has-text('Submit')"
        )
        page.wait_for_load_state("networkidle")
        return page.url


def _fill_if_present(page: "Page", selector: str, value: str) -> None:
    if not value:
        return
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.fill(value)
    except Exception:
        pass
