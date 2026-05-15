"""Greenhouse-hosted application forms.

Covers the modern `job-boards.greenhouse.io/{org}/jobs/{id}` host as well
as the legacy `boards.greenhouse.io` host. The two surface different
field schemas:

- **Legacy (`boards.greenhouse.io`)** uses Rails-style nested input names:
  `input[name='job_application[first_name]']`, etc. The form is inline
  on page load.
- **Modern (`job-boards.greenhouse.io`)** uses flat `id` attributes:
  `#first_name`, `#last_name`, `#email`, `#phone`, `#country`,
  `#candidate-location`, `#resume`, `#cover_letter`, plus per-posting
  custom questions of the form `#question_<numeric-id>` whose `<label>`
  carries the prompt. **The form is gated behind a top-of-page
  `button[aria-label="Apply"]` click**, after which the inputs are
  rendered into the DOM.

The adapter handles both, prefers the modern path, and never throws
on missing optional fields (phone / cover_letter / custom questions).
The runner enforces dry-run vs. submit at the outer level, `submit()`
is only invoked when the runner has confirmed it's allowed to click.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile
from ..salary import apply_salary_for


class GreenhouseAdapter:
    name = "greenhouse"

    def matches(self, url: str, page: "Page") -> bool:
        return (
            "greenhouse.io" in url
            or page.locator("form#application_form").count() > 0
            or page.locator("button[aria-label='Apply']").count() > 0
        )

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal
        first_name = p["full_name"].split()[0]
        last_name = p["full_name"].split()[-1]

        # Modern job-boards host: the form is hidden until "Apply" is clicked.
        # The legacy boards.greenhouse.io page renders the form inline so
        # the click is a no-op (the locator just won't find a match).
        try:
            apply_btn = page.locator("button[aria-label='Apply']").first
            if apply_btn.count() > 0:
                apply_btn.click(timeout=5_000)
                # Wait for the form's first input to actually exist before we
                # try to fill it. Without this the network may still be
                # racing to mount the form.
                page.locator("#first_name, input[name='job_application[first_name]']").first.wait_for(timeout=10_000)
        except Exception:
            pass  # fall through, the inline / legacy form may already be visible

        # Try modern selectors first, fall back to legacy. `fill_if` skips
        # silently when neither locator matches so we never block on a
        # missing optional field.
        self._fill_if(page,
                      ["#first_name", "input[name='job_application[first_name]']"],
                      first_name)
        self._fill_if(page,
                      ["#last_name", "input[name='job_application[last_name]']"],
                      last_name)
        self._fill_if(page,
                      ["#email", "input[name='job_application[email]']"],
                      p["email"])
        self._fill_if(page,
                      ["#phone", "input[name='job_application[phone]']"],
                      p.get("phone", ""))
        # City/state location, the modern form has a separate
        # candidate-location input; legacy doesn't always.
        self._fill_if(page, ["#candidate-location"],
                      f"{p.get('location', {}).get('city', '')}, "
                      f"{p.get('location', {}).get('country', '')}".strip(", "))

        # Resume upload (modern: #resume; legacy: name contains 'resume')
        if docs.cv_pdf:
            for sel in ["#resume", "input[type=file][name*='resume']",
                        "input[type=file][name*='cv']"]:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.set_input_files(docs.cv_pdf)
                    break

        # Cover letter upload (optional on most postings)
        if docs.cover_letter_pdf:
            for sel in ["#cover_letter", "input[type=file][name*='cover_letter']",
                        "input[type=file][name*='cover']"]:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.set_input_files(docs.cover_letter_pdf)
                    break

        # Per-posting custom questions (modern host only). Each one's id is
        # `question_<numeric>` and the prompt sits in the associated
        # <label>. We do heuristic matching against the label text and
        # fill from profile where there's a confident match; questions
        # we don't recognise are left blank for the user to fill.
        self._fill_custom_questions(page, profile, job)

    def submit(self, page: "Page") -> str:
        # Modern submit is a <button> with text "Submit application" near
        # the bottom of the form. Legacy uses input[type=submit].
        candidates = [
            "button:has-text('Submit application')",
            "button[type=submit]",
            "input[type=submit]",
        ]
        for sel in candidates:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                break
        else:
            raise RuntimeError("no submit button found on greenhouse form")
        # Post-click wait: Greenhouse can be SPA-heavy; networkidle is
        # unreliable. Wait for a success indicator or a fixed timeout;
        # the runner captures a screenshot on either outcome.
        try:
            page.wait_for_function(
                """() => {
                    const t = document.body.innerText.toLowerCase();
                    return t.includes('thank you') || t.includes('application received')
                        || t.includes('successfully') || t.includes('we received your application');
                }""",
                timeout=15_000,
            )
        except Exception:
            pass
        return page.url

    # ------------------------------------------------------------------

    @staticmethod
    def _fill_if(page: "Page", selectors: list[str], value: str) -> None:
        """Try each selector in order; fill the first match. Skip
        gracefully when nothing matches or the value is empty."""
        if not value:
            return
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.fill(value, timeout=5_000)
                    return
            except Exception:
                continue

    def _fill_custom_questions(
        self, page: "Page", profile: Profile, job: JobPosting,
    ) -> None:
        """Walk every `#question_<numeric>` input on the page, read its
        label, and fill from profile where the heuristic gives a high
        confidence match. Anything ambiguous is left blank, the user
        can complete it manually before the submit step.

        Salary is resolved via `apply_salary_for(job.description, …)`
        which prefers the employer's stated low-end when the JD names a
        range, else falls back to the candidate's profile anchor.
        """
        try:
            questions = page.evaluate("""() => {
                return [...document.querySelectorAll("input[id^='question_'], textarea[id^='question_']")]
                  .map(el => ({
                    id: el.id,
                    label: (el.labels && el.labels[0]) ? el.labels[0].textContent.trim() : '',
                  }));
            }""")
        except Exception:
            return

        prefs = profile.preferences
        p = profile.personal
        # Resolve the salary once per page, same number reused if there
        # are multiple salary fields on the form.
        anchor_eur = int(prefs.get("application_salary_eur_year") or 125_000)
        salary = apply_salary_for(job.description or "", anchor_eur)
        for q in questions:
            label_lc = (q.get("label") or "").lower()
            value = ""
            if "linkedin" in label_lc:
                value = p.get("links", {}).get("linkedin", "")
            elif "website" in label_lc or "portfolio" in label_lc or "github" in label_lc:
                value = (p.get("links", {}).get("website")
                         or p.get("links", {}).get("github", ""))
            elif "salary" in label_lc:
                value = salary.for_yearly_field()
            elif "city" in label_lc or "state" in label_lc or "located" in label_lc:
                loc = p.get("location", {})
                value = f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", ")
            elif "sponsorship" in label_lc or "visa" in label_lc:
                value = "No"
            elif "notice" in label_lc:
                value = f"{prefs.get('notice_period_weeks', 4)} weeks"
            if value:
                try:
                    page.locator(f"#{q['id']}").first.fill(value, timeout=3_000)
                except Exception:
                    pass
