"""Recruitee-hosted application forms (`{org}.recruitee.com/o/{slug}`).

Recruitee is a common European ATS — used by GTO Wizard and many other
mid-size European tech companies. Layout pattern (verified live against
`gtowizard.recruitee.com/o/product-manager-3`):

- The posting page opens on a "Job details" tab; a sibling **"Application"
  tab** must be clicked to reveal the form (button id of the form
  `tabs--*--tab--1` with visible text "Application" or "Apply").
- Core fields:
  - `input[name='candidate.name']`         — full name (one field, not split)
  - `input[name='candidate.email']`        — email
  - `input[name='candidate.cv']` (type=file) — CV upload (REQUIRED, * marker)
  - No standard cover-letter slot.
- Per-posting custom questions:
  `input[name='candidate.openQuestionAnswers.<numeric-id>.content']`
  Each one has a `<label>` carrying the question prompt; the numeric id
  varies per posting. We fill these heuristically by reading the label
  and matching against the candidate's profile (location, salary,
  portfolio, LinkedIn, notice period, etc.).
- Submit: a button at the form's foot. Wording varies by language
  ("Apply now", "Send application", "Bewerbung absenden"). The
  `submit()` step tries a handful of selectors in order.

The adapter never throws on missing optional fields and never clicks
submit on its own — the runner's outer dry-run gate decides.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile


class RecruiteeAdapter:
    name = "recruitee"

    def matches(self, url: str, page: "Page") -> bool:
        return (
            "recruitee.com" in url
            or page.locator("input[name='candidate.email']").count() > 0
        )

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal

        # Reveal the form: Recruitee posts open on "Job details"; the form
        # lives under the sibling "Application" / "Apply" tab. Clicking it
        # is idempotent — if we're already on it, nothing changes.
        for sel in [
            "button:has-text('Application')",
            "button:has-text('Apply')",
            # German posting variants
            "button:has-text('Bewerbung')",
            "button:has-text('Bewerben')",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=5_000)
                    # Wait for the actual form input to mount before we try
                    # to fill it.
                    page.locator("input[name='candidate.email']").first.wait_for(timeout=10_000)
                    break
            except Exception:
                continue

        # Core fields — single full-name input (not split), email, CV.
        self._fill_if(page, "input[name='candidate.name']", p["full_name"])
        self._fill_if(page, "input[name='candidate.email']", p["email"])
        if "phone" in p:
            # Phone slot exists on some postings; skip silently otherwise.
            self._fill_if(page, "input[name='candidate.phone']", p["phone"])

        # CV is a REQUIRED file upload on every Recruitee posting we've seen.
        if docs.cv_pdf:
            cv = page.locator("input[name='candidate.cv']")
            if cv.count() > 0:
                cv.first.set_input_files(docs.cv_pdf)

        # Recruitee doesn't have a standard cover-letter slot the way
        # Greenhouse does. If the posting added one as a custom file
        # input, the user would have to wire it manually.

        # Custom per-posting questions ----------------------------------
        self._fill_custom_questions(page, profile)

    def submit(self, page: "Page") -> str:
        # The footer button on Recruitee has variable wording. Try the
        # common ones in order; fall back to any submit-type button.
        candidates = [
            "button:has-text('Send application')",
            "button:has-text('Apply now')",
            "button:has-text('Submit application')",
            "button:has-text('Bewerbung absenden')",
            "button:has-text('Jetzt bewerben')",
            "button[type=submit]",
            "input[type=submit]",
        ]
        for sel in candidates:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                page.wait_for_load_state("networkidle", timeout=30_000)
                return page.url
        raise RuntimeError("no submit button found on recruitee form")

    # ------------------------------------------------------------------

    @staticmethod
    def _fill_if(page: "Page", selector: str, value: str) -> None:
        if not value:
            return
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.fill(value, timeout=5_000)
        except Exception:
            pass

    def _fill_custom_questions(self, page: "Page", profile: Profile) -> None:
        """Recruitee's per-posting open questions sit under
        `candidate.openQuestionAnswers.<id>.content`. We pull the label
        text for each, match heuristically against profile fields, and
        fill what we can confidently answer. Anything we don't recognise
        is left blank — Recruitee will surface a validation error on
        submit and the user can complete it manually."""
        try:
            questions = page.evaluate("""() => {
                return [...document.querySelectorAll(
                    "input[name^='candidate.openQuestionAnswers.'], textarea[name^='candidate.openQuestionAnswers.']"
                )].map(el => ({
                    name: el.name,
                    type: el.type,
                    label: (el.labels && el.labels[0]) ? el.labels[0].textContent.trim() : '',
                }));
            }""")
        except Exception:
            return

        p = profile.personal
        prefs = profile.preferences
        for q in questions:
            if not q["name"].endswith(".content"):
                continue
            label_lc = (q.get("label") or "").lower()
            value = ""
            if "linkedin" in label_lc:
                value = p.get("links", {}).get("linkedin", "")
            elif "portfolio" in label_lc or "website" in label_lc or "github" in label_lc:
                value = (p.get("links", {}).get("website")
                         or p.get("links", {}).get("github", ""))
            elif "located" in label_lc or "location" in label_lc or "city" in label_lc:
                loc = p.get("location", {})
                value = f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", ")
            elif "salary" in label_lc:
                rng = prefs.get("desired_salary_eur", {})
                if isinstance(rng, dict) and rng.get("min"):
                    if q["type"] == "number":
                        # Monthly figure — Recruitee number fields often ask
                        # for monthly EUR. Divide annual by 12 and round to
                        # the nearest hundred for readability.
                        monthly = (rng["min"] // 100) * 100 // 12 * 100
                        value = str(int(rng["min"] / 12))
                    else:
                        value = f"{rng['min']}-{rng.get('max', '')} EUR/year"
            elif "notice" in label_lc:
                value = f"{prefs.get('notice_period_weeks', 4)} weeks"
            elif "sponsor" in label_lc or "visa" in label_lc:
                value = "No, EU citizen"
            elif "remote" in label_lc:
                value = "Yes" if prefs.get("remote") else "No"

            if not value:
                continue
            try:
                page.locator(f"input[name='{q['name']}'], textarea[name='{q['name']}']").first.fill(
                    str(value), timeout=3_000,
                )
            except Exception:
                pass
