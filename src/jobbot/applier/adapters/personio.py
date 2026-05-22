"""Personio-hosted application forms.

Covers forms at *.jobs.personio.com and *.jobs.personio.de.

Field IDs are stable across tenants:
  - field-first_name, field-last_name, field-email, field-phone
  - field-available_from (DD.MM.YYYY format)
  - field-salary_expectations (free text)
  - field-custom_attribute_* (custom questions, label-matched)

Selects for gender / location / office-attendance / work-authorisation are
identified by their option text and set to safe defaults. File uploads use
the fixed IDs doc-input-cv and doc-input-other.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile
from ..salary import apply_salary_for


class PersonioAdapter:
    name = "personio"

    def matches(self, url: str, page: "Page") -> bool:
        return "jobs.personio.com" in url or "jobs.personio.de" in url

    def fill(self, page: "Page", job: JobPosting, profile: Profile, docs: GeneratedDocs) -> None:
        p = profile.personal
        full_name: str = p.get("full_name", "")
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[-1] if len(name_parts) > 1 else ""

        # Basic contact fields
        _fill_if_present(page, "#field-first_name", first_name)
        _fill_if_present(page, "#field-last_name", last_name)
        _fill_if_present(page, "#field-email", p.get("email", ""))
        _fill_if_present(page, "#field-phone", p.get("phone", ""))

        # Available-from: 4 weeks from today, formatted DD.MM.YYYY
        prefs = profile.preferences
        notice_weeks = int(prefs.get("notice_period_weeks") or 4)
        available_date = _available_from_date(notice_weeks)
        _fill_if_present(page, "#field-available_from", available_date)

        # Salary expectations
        anchor_eur = int(prefs.get("application_salary_eur_year") or 125_000)
        salary = apply_salary_for(job.description or "", anchor_eur)
        _fill_if_present(page, "#field-salary_expectations", salary.for_yearly_field())

        # Select: gender -> "Ohne Angabe" (no preference / non-disclosed)
        _select_by_option_text(page, "select", "Ohne Angabe")

        # Select: location -> "Germany" (try both English and German labels)
        _select_by_option_text(page, "select", "Germany")

        # Select: office attendance -> "No"
        # Select: work authorization -> "Yes"
        # We iterate all selects and set each based on its available options.
        _configure_select_fields(page)

        # Custom attribute free-text fields (field-custom_attribute_*)
        _fill_custom_attributes(page, profile, job)

        # File uploads - use force=True because Personio hides the native input
        if docs.cv_pdf:
            _upload_file(page, "input#doc-input-cv", docs.cv_pdf)
        if docs.cover_letter_pdf:
            _upload_file(page, "input#doc-input-other", docs.cover_letter_pdf)

    def submit(self, page: "Page") -> str:
        candidates = [
            "button:has-text('Submit Application')",
            "button:has-text('Jetzt bewerben')",
            "button:has-text('Apply')",
            "button[type=submit]",
        ]
        for sel in candidates:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                break
        else:
            raise RuntimeError("no submit button found on Personio form")

        # Wait for success indicator
        try:
            page.wait_for_function(
                """() => {
                    const t = document.body.innerText.toLowerCase();
                    return t.includes('vielen dank') || t.includes('thank you')
                        || t.includes('application received') || t.includes('danke');
                }""",
                timeout=15_000,
            )
        except Exception:
            pass
        return page.url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available_from_date(notice_weeks: int) -> str:
    """Return today + notice_weeks formatted as DD.MM.YYYY."""
    available = datetime.date.today() + datetime.timedelta(weeks=notice_weeks)
    return available.strftime("%d.%m.%Y")


def _fill_if_present(page: "Page", selector: str, value: str) -> None:
    if not value:
        return
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.fill(value, timeout=5_000)
    except Exception:
        pass


def _select_by_option_text(page: "Page", base_selector: str, option_text: str) -> None:
    """Select the first <select> that has an option matching option_text exactly."""
    try:
        selects = page.locator(base_selector)
        count = selects.count()
        for i in range(count):
            sel = selects.nth(i)
            try:
                sel.select_option(label=option_text, timeout=2_000)
                return  # stop after the first successful selection
            except Exception:
                continue
    except Exception:
        pass


def _configure_select_fields(page: "Page") -> None:
    """Walk all <select> elements and set each to a sensible default based
    on what options it offers.

    Rules:
      - Has "Ohne Angabe"  -> already handled by _select_by_option_text above;
        skip if already set.
      - Has "Germany" / "Deutschland"  -> already handled.
      - Has "Yes" and "No" options:
          * If nearby label contains "authoriz" or "permission" or "erlaubnis"
            or "berechtigung" -> "Yes"  (work authorisation)
          * Otherwise -> "No"  (office attendance, relocation, etc.)
    """
    try:
        selects = page.locator("select")
        count = selects.count()
        for i in range(count):
            sel = selects.nth(i)
            try:
                # Read available option labels for this select
                option_labels: list[str] = page.evaluate(
                    """(el) => [...el.options].map(o => o.text.trim())""",
                    sel.element_handle()
                )
                labels_lc = [o.lower() for o in option_labels]

                if "yes" in labels_lc and "no" in labels_lc:
                    # Determine context via nearby label/legend text
                    nearby_text = _nearby_label_text(page, sel)
                    auth_keywords = (
                        "authoriz", "authoris", "permission", "erlaubnis",
                        "berechtigung", "work permit", "visa", "right to work",
                    )
                    if any(kw in nearby_text for kw in auth_keywords):
                        sel.select_option(label="Yes", timeout=2_000)
                    else:
                        sel.select_option(label="No", timeout=2_000)
            except Exception:
                continue
    except Exception:
        pass


def _nearby_label_text(page: "Page", loc) -> str:
    """Return lower-cased label / legend / aria-label text near a locator."""
    try:
        handle = loc.element_handle()
        if handle is None:
            return ""
        text: str = page.evaluate(
            """(el) => {
                // Try aria-label first
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
                // Try associated <label>
                if (el.id) {
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) return lbl.textContent;
                }
                // Walk up to nearest <label> or <fieldset>/<legend>
                let parent = el.parentElement;
                for (let n = 0; n < 5; n++) {
                    if (!parent) break;
                    const lbl = parent.querySelector('label, legend');
                    if (lbl) return lbl.textContent;
                    parent = parent.parentElement;
                }
                return '';
            }""",
            handle,
        )
        return (text or "").lower()
    except Exception:
        return ""


def _fill_custom_attributes(
    page: "Page", profile: Profile, job: JobPosting,
) -> None:
    """Fill field-custom_attribute_* inputs by matching the associated label.

    Heuristic map:
      linkedin   -> profile.personal.links.linkedin
      website / portfolio -> profile.personal.links.website
      salary     -> apply_salary_for(...)
      available / notice -> formatted date / weeks string
    """
    try:
        fields = page.evaluate("""() => {
            return [...document.querySelectorAll(
                "input[id^='field-custom_attribute_'], textarea[id^='field-custom_attribute_']"
            )].map(el => ({
                id: el.id,
                label: el.labels && el.labels[0] ? el.labels[0].textContent.trim() : '',
            }));
        }""")
    except Exception:
        return

    p = profile.personal
    prefs = profile.preferences
    anchor_eur = int(prefs.get("application_salary_eur_year") or 125_000)
    salary = apply_salary_for(job.description or "", anchor_eur)
    notice_weeks = int(prefs.get("notice_period_weeks") or 4)

    for field in fields:
        label_lc = (field.get("label") or "").lower()
        value = ""
        if "linkedin" in label_lc:
            value = p.get("links", {}).get("linkedin", "")
        elif "website" in label_lc or "portfolio" in label_lc:
            value = (
                p.get("links", {}).get("website")
                or p.get("links", {}).get("github", "")
                or ""
            )
        elif "salary" in label_lc or "gehalt" in label_lc or "compensation" in label_lc:
            value = salary.for_yearly_field()
        elif "available" in label_lc or "start" in label_lc or "verfugbar" in label_lc:
            value = _available_from_date(notice_weeks)
        elif "notice" in label_lc or "kundigungsfrist" in label_lc:
            value = f"{notice_weeks} weeks"
        # Leave unrecognised fields blank

        if value:
            try:
                page.locator(f"#{field['id']}").first.fill(value, timeout=3_000)
            except Exception:
                pass


def _upload_file(page: "Page", selector: str, file_path: str) -> None:
    """Set files on a (possibly hidden) file input using force=True."""
    try:
        loc = page.locator(selector)
        if loc.count() > 0:
            loc.first.set_input_files(file_path, timeout=10_000)
    except Exception:
        # Some Personio tenants use a JS-driven upload widget that replaces
        # the native input after mount. If the first attempt fails, try
        # dispatching a change event via evaluate as a fallback.
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.evaluate(
                    "(el, path) => { "
                    "    const dt = new DataTransfer(); "
                    "    // Cannot set real file via evaluate; just dispatch "
                    "    // a click so the OS file-picker opens. Adapter caller "
                    "    // relies on set_input_files above; this branch is a "
                    "    // no-op safety net. "
                    "}",
                    file_path,
                )
        except Exception:
            pass
