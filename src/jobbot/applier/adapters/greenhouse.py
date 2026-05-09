"""Greenhouse-hosted application forms (boards.greenhouse.io / job-boards.greenhouse.io)."""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile


class GreenhouseAdapter:
    name = "greenhouse"

    def matches(self, url: str, page: "Page") -> bool:
        return "greenhouse.io" in url or page.locator("form#application_form").count() > 0

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal
        page.fill("input[name='job_application[first_name]']", p["full_name"].split()[0])
        page.fill("input[name='job_application[last_name]']",  p["full_name"].split()[-1])
        page.fill("input[name='job_application[email]']",      p["email"])
        page.fill("input[name='job_application[phone]']",      p.get("phone", ""))

        # Resume upload
        if docs.cv_pdf:
            resume_loc = page.locator(
                "input[type=file][name*='resume'], input[type=file][name*='cv']"
            )
            if resume_loc.count() > 0:
                resume_loc.first.set_input_files(docs.cv_pdf)

        # Cover letter upload (not always present)
        if docs.cover_letter_pdf:
            cl_loc = page.locator(
                "input[type=file][name*='cover_letter'], input[type=file][name*='cover']"
            )
            if cl_loc.count() > 0:
                cl_loc.first.set_input_files(docs.cover_letter_pdf)

    def submit(self, page: "Page") -> str:
        page.click("input[type=submit], button[type=submit]")
        page.wait_for_load_state("networkidle")
        return page.url
