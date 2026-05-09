"""Lever-hosted application forms (jobs.lever.co)."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile


class LeverAdapter:
    name = "lever"

    def matches(self, url: str, page: "Page") -> bool:
        return "lever.co" in url or page.locator("form.application-form").count() > 0

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal
        page.fill("input[name='name']",  p["full_name"])
        page.fill("input[name='email']", p["email"])
        page.fill("input[name='phone']", p.get("phone", ""))
        page.fill("input[name='org']",   "")  # current company; may be blank

        # Resume upload
        if docs.cv_pdf:
            resume_loc = page.locator(
                "input[type=file][name*='resume'], input[type=file]"
            )
            if resume_loc.count() > 0:
                resume_loc.first.set_input_files(docs.cv_pdf)

        # Cover letter (Lever sometimes has a textarea instead of file upload)
        cl_file = page.locator("input[type=file][name*='cover'], input[type=file][name*='letter']")
        if cl_file.count() > 0 and docs.cover_letter_pdf:
            cl_file.first.set_input_files(docs.cover_letter_pdf)
        else:
            cl_textarea = page.locator(
                "textarea[name*='cover'], textarea[placeholder*='cover letter' i]"
            )
            if cl_textarea.count() > 0:
                cl_textarea.first.fill(docs.cover_letter_md[:3000])

    def submit(self, page: "Page") -> str:
        page.click("button[data-qa='btn-submit'], button[type=submit]")
        page.wait_for_load_state("networkidle")
        return page.url
