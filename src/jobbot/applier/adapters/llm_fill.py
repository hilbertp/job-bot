"""LLM-assisted form-fill adapter, the universal fallback for unknown ATSes.

When an apply page doesn't match Greenhouse / Recruitee / Lever / Workday,
we used to fall through to GenericAdapter, which only filled the three
most obvious selectors (name / email / tel) and refused to submit.
That left European Mittelstand forms (scope-recruiting.de, TeamTailor,
Personio variants, custom built-from-scratch recruiting pages) entirely
manual: 14 German fields filled by hand.

LLMFillAdapter solves the long tail without writing one adapter per ATS:

  1. Scrape every form field on the page (input / textarea / select),
     including label text, placeholder, name, id, type, required flag,
     and option values for selects.
  2. Send the field list plus user profile + job context to Claude with a
     strict mapping prompt.
  3. Claude returns a JSON list of `selector → value` mappings, with each
     entry tagged by kind (text / select_option / file). Anything the
     model can't confidently map is left in a `skipped` bucket so the
     human reviewer sees what's still open.
  4. Apply each mapping via Playwright (fill / select_option /
     set_input_files), tolerating per-field failures so a single missed
     selector doesn't kill the whole pass.

The adapter is conservative on submit: `submit()` raises NotImplementedError
in v1 so the runner falls through to supervised-with-no-auto-submit, giving
the human a final eyeball before send. A future version can flip this once
we have confidence telemetry on real applies.

Field-extraction limitations to be aware of:

  - Fields behind a "reveal" gesture (e.g. file inputs hidden until a
    doc-type select is set) won't appear in the first scrape. The
    adapter does a two-pass: scrape → fill non-file fields → re-scrape
    for file inputs that the select reveal made visible → upload.
  - Forms gated behind an "Apply now" button (TeamTailor pattern) need
    the runner to click that button before the adapter sees the form.
    The adapter's `fill()` does a best-effort click on a small set of
    apply-button selectors, idempotent if already on the form.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from playwright.sync_api import Page

from ...models import GeneratedDocs, JobPosting
from ...profile import Profile

log = structlog.get_logger()


# Selectors clicked before the first scrape to reveal forms gated by
# an "Apply" button (TeamTailor, scope-recruiting.de, Greenhouse v2,
# Personio "Apply for this job", etc.). Both <button> and <a> variants
# since ATSes render the CTA either way. Idempotent: if no button
# matches, nothing happens.
_REVEAL_SELECTORS = (
    "button:has-text('Apply for this job')",   # Personio
    "a:has-text('Apply for this job')",        # Personio (link variant)
    "button:has-text('Apply now')",
    "button:has-text('Apply for this position')",
    "a:has-text('Apply for this position')",
    "button:has-text('Apply')",
    "a:has-text('Apply')",
    "button[aria-label='Apply']",
    "button:has-text('Bewerbung abschicken')",
    "button:has-text('Auf diese Stelle bewerben')",  # Personio (DE)
    "a:has-text('Auf diese Stelle bewerben')",
    "button:has-text('Jetzt bewerben')",
    "a:has-text('Jetzt bewerben')",
    "button:has-text('Bewerben')",
    "a:has-text('Bewerben')",
    "button:has-text('Bewerbung starten')",
    "a:has-text('Apply now')",
)

# Submit / send buttons, EN + DE. Tried in order; first enabled+visible
# match is clicked. type=submit / input[type=submit] are last-resort
# catch-alls guarded by a text blacklist (see _is_non_submit_button).
_SUBMIT_SELECTORS = (
    "button:has-text('Send application')",
    "button:has-text('Submit application')",
    "button:has-text('Submit your application')",
    "button:has-text('Complete application')",
    "button:has-text('Bewerbung absenden')",
    "button:has-text('Bewerbung abschicken')",
    "button:has-text('Jetzt bewerben')",
    "button:has-text('Absenden')",
    "button:has-text('Senden')",
    "button:has-text('Submit')",
    "button:has-text('Send')",
    "button:has-text('Bewerben')",
    "button[type=submit]",
    "input[type=submit]",
)

# "Next / Continue" selectors for multi-step forms (join.com, Workable,
# Personio, custom). Clicked in order when no submit button is found;
# up to _MAX_NEXT_STEPS advances before giving up.
_NEXT_STEP_SELECTORS = (
    "button:has-text('Next')",
    "button:has-text('Weiter')",
    "button:has-text('Continue')",
    "button:has-text('Fortfahren')",
    "button:has-text('Nächster Schritt')",
    "button:has-text('Next step')",
    "button[data-qa='next-button']",
    "button[data-testid='next-button']",
    "button.next",
)
_MAX_NEXT_STEPS = 6  # safety cap to avoid infinite loops

# Texts that disqualify a button[type=submit] catch-all match: these are
# login / search / generic form submits, NOT application-send buttons.
_NON_SUBMIT_TEXT_RE = __import__("re").compile(
    r"^(log\s*in|sign\s*in|sign\s*up|register|create\s*account|search|"
    r"subscribe|newsletter|send\s*message|contact\s*us|reset|forgot|"
    r"save|cancel|back|close|delete|remove|upload|download)$",
    __import__("re").IGNORECASE,
)


class LLMFillAdapter:
    """Universal form filler driven by an LLM mapping pass. Registered
    AFTER specific ATS adapters but BEFORE GenericAdapter so unknown
    forms get the smart treatment and Generic stays the absolute
    last-resort dry-run."""

    name = "llm_fill"

    def __init__(self, *, anthropic_api_key: str | None = None) -> None:
        # Caller can inject the key; in production it comes from secrets.
        self._api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

    # ------------------------------------------------------------------
    # Adapter protocol
    # ------------------------------------------------------------------

    def matches(self, url: str, page: "Page") -> bool:  # noqa: ARG002
        """Match a page that has form fields OR an apply-reveal button.

        The reveal-button case is critical: on Personio / TeamTailor /
        scope-recruiting.de the form is gated behind "Apply for this job"
        and the JD page has NO inputs yet. Adapter selection happens
        before fill() clicks reveal, so without this check the runner
        would fall through to GenericAdapter (which can't reveal or
        submit) and the apply stalls at the JD page. GenericAdapter
        remains the absolute fallback for pages with neither."""
        try:
            if page.locator("input, textarea, select").count() > 0:
                return True
            for sel in _REVEAL_SELECTORS:
                loc = page.locator(sel)
                if loc.count() > 0:
                    return True
            return False
        except Exception:
            return False

    def fill(
        self, page: "Page", job: JobPosting, profile: Profile,
        docs: GeneratedDocs,
    ) -> None:
        if not self._api_key:
            log.warning("llm_fill_no_api_key", note="ANTHROPIC_API_KEY unset; skipping")
            return

        # Store context so _fill_current_page can re-use it during
        # multi-step navigation without threading extra args through submit().
        self._current_fill_ctx = (job, profile, docs)

        self._reveal_form(page)
        fields = self._scrape_fields(page)
        # Single-choice questions rendered as a row of <button>s (Ashby
        # Yes/No work-authorization, segmented controls) are invisible to the
        # input/select scrape, so collect them separately and hand them to
        # the same mapping pass.
        button_groups = self._scrape_button_groups(page)
        radio_groups = self._scrape_radio_groups(page)
        if button_groups or radio_groups:
            log.info(
                "llm_fill_choice_groups_found",
                buttons=len(button_groups), radios=len(radio_groups),
            )
        all_fields = fields + button_groups + radio_groups
        if not all_fields:
            log.info("llm_fill_no_fields_found", url=page.url)
            return

        mapping = self._ask_claude(all_fields, job, profile, docs)
        if mapping is None:
            log.warning("llm_fill_claude_no_mapping", n_fields=len(fields))
            return

        self._apply_mapping(page, mapping)

        # Second pass: selects (e.g. doc-type) may have revealed file
        # inputs that were not present in the first scrape. Re-scrape and
        # ask Claude to fill ONLY the new file inputs from disk paths it
        # was told about.
        new_fields = self._scrape_fields(page, only_files=True)
        if new_fields:
            log.info("llm_fill_second_pass", new_file_inputs=len(new_fields))
            file_mapping = self._ask_claude(
                new_fields, job, profile, docs, second_pass=True,
            )
            if file_mapping is not None:
                self._apply_mapping(page, file_mapping)

    def submit(self, page: "Page") -> str:
        """Click the form's submit/send button and return the post-click URL.

        Multi-step forms (join.com, Workable, etc.) gate the final submit
        behind one or more "Next / Weiter" pages. We walk through up to
        _MAX_NEXT_STEPS pages: on each step, first try the submit selectors;
        if none match, look for a Next button and advance. If we're still on
        a new page after clicking Next, re-run fill() to populate any new
        fields before trying submit again.

        The `button[type=submit]` catch-all is guarded by _NON_SUBMIT_TEXT_RE
        so it never fires on Login / Search / Sign-up buttons.
        """
        for step in range(_MAX_NEXT_STEPS + 1):
            # --- try submit selectors on the current page ---
            for sel in _SUBMIT_SELECTORS:
                try:
                    loc = page.locator(sel).first
                    if loc.count() == 0 or not loc.is_visible():
                        continue
                    if loc.is_disabled():
                        continue
                    txt = (loc.text_content(timeout=1_500) or "").strip()
                    # Guard the type=submit catch-all against non-apply buttons
                    if sel in ("button[type=submit]", "input[type=submit]"):
                        if _NON_SUBMIT_TEXT_RE.match(txt):
                            log.debug(
                                "llm_fill_submit_skip_non_apply",
                                selector=sel, text=txt[:40],
                            )
                            continue
                    loc.click(timeout=8_000)
                    log.info("llm_fill_submit_clicked", selector=sel, text=txt[:40])
                    page.wait_for_timeout(4_000)
                    return page.url
                except Exception as e:
                    log.warning("llm_fill_submit_try_failed", selector=sel,
                                error=str(e)[:80])
                    continue

            if step >= _MAX_NEXT_STEPS:
                break

            # --- no submit found: try advancing to the next step ---
            advanced = False
            for nsel in _NEXT_STEP_SELECTORS:
                try:
                    loc = page.locator(nsel).first
                    if loc.count() == 0 or not loc.is_visible() or loc.is_disabled():
                        continue
                    txt = (loc.text_content(timeout=1_500) or "").strip()
                    loc.click(timeout=5_000)
                    page.wait_for_timeout(2_000)
                    log.info("llm_fill_next_step_clicked",
                             step=step + 1, selector=nsel, text=txt[:30])
                    # Re-fill any new fields that appeared on this step
                    try:
                        self._fill_current_page(page)
                    except Exception as e:
                        log.warning("llm_fill_step_fill_failed",
                                    step=step + 1, error=str(e)[:80])
                    advanced = True
                    break
                except Exception:
                    continue

            if not advanced:
                break  # no next button either — give up

        raise RuntimeError("llm_fill: no enabled submit button found")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fill_current_page(self, page: "Page") -> None:
        """Re-scrape and fill fields visible on the current form step.

        Called after advancing to a new step in a multi-step form so any
        newly revealed fields get populated before the submit attempt.
        Uses the same job/profile/docs context stored on the instance by
        fill() — callers must have called fill() first.
        """
        if not hasattr(self, "_current_fill_ctx"):
            return  # called outside a fill() context; skip silently
        job, profile, docs = self._current_fill_ctx
        fields = self._scrape_fields(page)
        button_groups = self._scrape_button_groups(page)
        radio_groups = self._scrape_radio_groups(page)
        all_fields = fields + button_groups + radio_groups
        if not all_fields:
            return
        mapping = self._ask_claude(all_fields, job, profile, docs)
        if mapping is not None:
            self._apply_mapping(page, mapping)

    def _reveal_form(self, page: "Page") -> None:
        """Click any apply-button that gates the form. Idempotent."""
        for sel in _REVEAL_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=3_000)
                    page.wait_for_timeout(1_500)
                    return
            except Exception:
                continue

    def _scrape_fields(
        self, page: "Page", *, only_files: bool = False,
    ) -> list[dict[str, Any]]:
        """Pull form fields with enough context for the LLM to map them.

        For non-file fields we require visibility (offsetParent !== null)
        to skip csrf tokens and offscreen junk. For FILE inputs we do NOT
        require visibility: ATSes (Personio, Greenhouse, ...) hide the
        real `<input type=file>` behind a styled "Add file" button, so the
        input is offscreen by design. Playwright's set_input_files works
        on a hidden input directly, so we include them."""
        if only_files:
            select_expr = (
                "[...document.querySelectorAll(\"input[type=file]\")]"
            )
        else:
            # Radios are handled as grouped questions by _scrape_radio_groups
            # (they need their question text + sibling options to be mappable),
            # so exclude them here to avoid duplicate, context-free entries.
            select_expr = (
                "[...document.querySelectorAll('input, textarea, select')]"
                ".filter(el => el.offsetParent !== null"
                " && el.type !== 'hidden' && el.type !== 'radio')"
            )
        return page.evaluate(f"""() => {{
            const els = {select_expr};
            return els.map(el => {{
                const lab = el.labels && el.labels[0] ? el.labels[0].textContent.trim() : null;
                const options = el.tagName === 'SELECT'
                    ? [...el.options].map(o => ({{value: o.value, text: o.textContent.trim()}}))
                    : null;
                return {{
                    tag: el.tagName,
                    type: el.type || null,
                    name: el.name || null,
                    id: el.id || null,
                    placeholder: el.placeholder || null,
                    label: lab,
                    required: el.required || false,
                    options: options,
                    accept: el.getAttribute ? (el.getAttribute('accept') || null) : null,
                    checked: el.type === 'checkbox' ? !!el.checked : null,
                }};
            }});
        }}""")

    def _scrape_button_groups(self, page: "Page") -> list[dict[str, Any]]:
        """Scrape single-choice questions rendered as a row of <button>s.

        ATSes like Ashby render boolean / single-select custom questions
        (e.g. "Are you legally authorized to work in Germany?" with Yes / No
        buttons) as button groups, NOT as <select> or <input type=radio>, so
        `_scrape_fields` never sees them and the apply stalls on a required
        field. This finds containers holding 2-6 short-text option buttons,
        tags each with a `data-jobbot-bg` attribute so the apply step can
        target it unambiguously, and returns one entry per group with
        `kind="button_group"`, the group `selector`, the question `label`,
        and the visible `options`.
        """
        try:
            return page.evaluate(r"""() => {
              const groups = [];
              const SKIP = /submit|apply|send|absenden|bewerben|upload|replace|remove|add file|autofill|sign ?in|log ?in|cancel|back|next|continue|previous|close/i;
              const isOption = (b) => {
                const t = (b.innerText || "").trim();
                if (!t || t.length > 40) return false;
                // The real submit/apply CTA is excluded by SKIP (its text).
                // We must NOT exclude by type==="submit": a <button> with no
                // explicit type inside a <form> defaults to type "submit",
                // and Ashby renders its Yes/No option buttons exactly that
                // way (they toggle via JS, they don't submit), so a type
                // check would filter out the very options we need.
                if (SKIP.test(t)) return false;
                if (b.offsetParent === null) return false;
                return true;
              };
              const containers = new Set();
              document.querySelectorAll("button").forEach(b => {
                if (!isOption(b)) return;
                let c = b.parentElement;
                for (let i = 0; i < 4 && c; i++) {
                  const opts = [...c.querySelectorAll("button")].filter(isOption);
                  if (opts.length >= 2) { containers.add(c); break; }
                  c = c.parentElement;
                }
              });
              let idx = 0;
              containers.forEach(c => {
                if (c.hasAttribute("data-jobbot-bg")) return;
                const btns = [...c.querySelectorAll("button")].filter(isOption);
                if (btns.length < 2 || btns.length > 6) return;
                const optTexts = btns.map(b => b.innerText.trim());
                const opts = new Set(optTexts);
                // The question label is often a SIBLING of the button
                // container (Ashby: <label> then <div> of Yes/No buttons),
                // so climb ancestors looking for a <label>/<legend> whose
                // text isn't one of the options.
                let label = "";
                let a = c;
                for (let i = 0; i < 4 && a && !label; i++) {
                  const labs = [...a.querySelectorAll("label, legend")]
                    .map(l => (l.innerText || "").trim())
                    .filter(t => t && !opts.has(t));
                  if (labs.length) label = labs[0];
                  a = a.parentElement;
                }
                if (!label) {
                  const lines = (c.innerText || "").split("\n").map(s => s.trim())
                    .filter(s => s && !opts.has(s));
                  label = lines.length ? lines[0] : "";
                }
                c.setAttribute("data-jobbot-bg", String(idx));
                groups.push({
                  kind: "button_group",
                  selector: "[data-jobbot-bg='" + idx + "']",
                  label: label.slice(0, 140),
                  options: optTexts,
                });
                idx++;
              });
              return groups;
            }""")
        except Exception as e:
            log.warning("llm_fill_button_group_scrape_failed", error=str(e)[:100])
            return []

    def _scrape_radio_groups(self, page: "Page") -> list[dict[str, Any]]:
        """Scrape single-choice questions rendered as native radio inputs.

        `_scrape_fields` skips radios because an individual radio carries
        only its OPTION label (e.g. "Yes"), not the QUESTION it answers, so
        the LLM can't tell which group a radio belongs to. Here we group
        radios by `name`, find the question text (legend / first non-option
        line), tag the group's common-ancestor container with a
        `data-jobbot-rg` attribute, and return one entry per group with
        `kind="radio_group"`, the group `selector`, the question `label`,
        and the option labels. Covers Ashby work-authorization + EEO
        questions, and any ATS using radios for single-choice.
        """
        try:
            return page.evaluate(r"""() => {
              const groups = [];
              const radios = [...document.querySelectorAll("input[type=radio]")]
                .filter(r => r.offsetParent !== null);
              const byName = {};
              radios.forEach(r => { (byName[r.name] = byName[r.name] || []).push(r); });
              let idx = 0;
              Object.keys(byName).forEach(name => {
                const rs = byName[name];
                if (!name || rs.length < 2) return;
                let c = rs[0].parentElement;
                for (let i = 0; i < 6 && c; i++) {
                  if (rs.every(r => c.contains(r))) break;
                  c = c.parentElement;
                }
                if (!c || c.hasAttribute("data-jobbot-rg")) return;
                const optTexts = rs.map(r =>
                  (r.labels && r.labels[0]) ? r.labels[0].textContent.trim() : ""
                ).filter(Boolean);
                if (optTexts.length < 2) return;
                const optset = new Set(optTexts);
                let q = "";
                const legend = c.querySelector("legend");
                if (legend) q = legend.innerText.trim();
                if (!q) {
                  const lines = (c.innerText || "").split("\n").map(s => s.trim())
                    .filter(s => s && !optset.has(s));
                  q = lines.length ? lines[0] : "";
                }
                c.setAttribute("data-jobbot-rg", String(idx));
                groups.push({
                  kind: "radio_group",
                  selector: "[data-jobbot-rg='" + idx + "']",
                  label: q.slice(0, 160),
                  options: optTexts,
                });
                idx++;
              });
              return groups;
            }""")
        except Exception as e:
            log.warning("llm_fill_radio_group_scrape_failed", error=str(e)[:100])
            return []

    def _ask_claude(
        self,
        fields: list[dict[str, Any]],
        job: JobPosting,
        profile: Profile,
        docs: GeneratedDocs,
        *,
        second_pass: bool = False,
    ) -> list[dict[str, Any]] | None:
        """Send fields + profile + job to Claude, get back a JSON list of
        `{selector, value, kind}` entries. Returns None on a Claude
        error or invalid JSON, callers treat that as 'fill nothing'."""
        try:
            from anthropic import Anthropic
        except ImportError:
            log.error("llm_fill_anthropic_not_installed")
            return None

        client = Anthropic(api_key=self._api_key)
        prompt = self._build_prompt(
            fields, job, profile, docs, second_pass=second_pass,
        )
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                temperature=0,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            log.error("llm_fill_claude_failed", error=str(e))
            return None

        # Claude is asked to return ONLY a JSON object. Be defensive in case
        # it wraps in markdown fences anyway.
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("llm_fill_claude_bad_json", error=str(e), text=text[:200])
            return None
        return parsed.get("fills", []) if isinstance(parsed, dict) else None

    def _build_prompt(
        self,
        fields: list[dict[str, Any]],
        job: JobPosting,
        profile: Profile,
        docs: GeneratedDocs,
        *,
        second_pass: bool,
    ) -> str:
        p = profile.personal
        prefs = profile.preferences
        loc = p.get("location", {}) or {}
        salary_anchor_eur = int(prefs.get("application_salary_eur_year") or 125_000)
        pass_note = (
            "SECOND PASS: only file inputs that the first pass revealed. "
            "Map each file input to one of the file paths provided."
            if second_pass else
            "FIRST PASS: every non-file field. Skip file inputs in this pass."
        )
        return f"""# Task

{pass_note}

You are mapping a job-application form to the candidate's profile data.
Return a JSON object with a `fills` array. Each element maps ONE form
field to a value the runner will write into it.

# Form fields (scraped from page)

```json
{json.dumps(fields, indent=2)}
```

# Candidate profile

- Full name: {p.get('full_name')}
- First name: {p.get('full_name', '').split()[0] if p.get('full_name') else ''}
- Last name:  {p.get('full_name', '').split()[-1] if p.get('full_name') else ''}
- Email: {p.get('email')}
- Phone: {p.get('phone')}
- City: {loc.get('city')}
- Country: {loc.get('country')}
- LinkedIn: {(p.get('links') or {{}}).get('linkedin')}
- GitHub:   {(p.get('links') or {{}}).get('github')}
- Website:  {(p.get('links') or {{}}).get('website')}
- Salary expectation (EUR/year): {salary_anchor_eur}
- Visa / authorization: EU citizen, German national, no sponsorship required
- Earliest start / availability: ASAP, immediately, ab sofort (always the
  earliest option, do not enter a multi-week notice)

# Job context

- Title:   {job.title}
- Company: {job.company}
- URL:     {job.apply_url}

# Available files on disk (use these EXACT paths for file inputs)

- CV PDF: {docs.cv_pdf}
- Cover letter PDF: {docs.cover_letter_pdf}
- Combined application package PDF: {(docs.output_dir or '') + '/application_package.pdf'}

# Mapping rules

1. Build a CSS selector for each field that uniquely identifies it.
   Preferred order: `[name='<name>']` > `[id='<id>']` > `[placeholder='<placeholder>']`.
   Use the ATTRIBUTE form `[id='...']`, NOT `#id`, because ATS ids often
   contain ':' or '.' which break a `#id` selector. For a file input that
   is the only CV upload on the page, `input[type=file]` is also fine.
2. For text/email/tel/textarea inputs: set `kind` to `"text"` and `value` to
   the string to fill.
3. For SELECT inputs: set `kind` to `"select_option"` and `value` to the
   option's `value` attribute (NOT its visible text). Pick the option
   that best matches the candidate. For gender selects use `"diverse"`
   or equivalent if available, else leave the field unmapped.
4. For file inputs: set `kind` to `"file"` and `value` to the absolute
   path of cv.pdf or cover_letter.pdf depending on what the doc-type
   label / select implies. ONLY map a file input whose `accept` attribute
   includes pdf (or is empty/unset). NEVER upload a PDF to an input that
   only accepts images (accept contains png/jpg/jpeg), that is an avatar/
   photo field, leave it unmapped.
5. For CHECKBOX inputs (type=checkbox): if it is a required consent /
   privacy / GDPR / "I agree" / data-processing checkbox, set `kind` to
   `"checkbox"` and `value` to `"true"` so the submit button enables.
   Leave optional marketing opt-ins unmapped.
6. AVAILABILITY / earliest start date / notice period: always answer with
   the EARLIEST possible, "ASAP" (or "Sofort" / "Ab sofort" in German,
   "immediately"). Do NOT enter a multi-week notice period.
7. SKIP a field by NOT including it in `fills` if you cannot confidently
   map it. NEVER fabricate values (do not invent a street address, a
   birthday, a postal code, or a phone number the profile doesn't have).
8. Detect form language from labels/placeholders. If German, write German
   values for free-text fields. Salary stays numeric.
9. NEVER write em-dashes in any text value. Use commas, periods, or
   hyphens. This is a hard rule, the user has been bitten by it before.
10. Salary fields: write the EUR anchor as plain integer (e.g. "125000"),
    no currency symbol, no thousands separator, unless the placeholder
    explicitly hints at a different format.
11. BUTTON-GROUP questions (a field with `kind` already set to
    `"button_group"`): single-choice questions rendered as a row of
    buttons (e.g. a Yes/No work-authorization question). To answer one,
    return an entry with `kind` = `"button_click"`, `selector` = the
    group's EXACT `selector` value from the field list, and `value` = the
    EXACT text of the option button to click (one of the listed `options`).
    Skip the group if you cannot answer it confidently.
12. WORK AUTHORIZATION / right-to-work questions: the candidate is a German
    citizen, authorized to work anywhere in the EU/EEA with no sponsorship.
    - "Authorized to work in <Germany / an EU or EEA country>?" -> Yes.
    - "Do you require visa sponsorship for <Germany / the EU>?" -> No.
    - For NON-EU countries (US, UK, Switzerland, Canada, ...), the candidate
      is NOT currently authorized and WOULD need sponsorship: answer
      truthfully ("No" to authorized, "Yes" to requires-sponsorship).
    - Infer the country from the question text, else the job location /
      company. If still unclear, skip the question.
13. RADIO-GROUP questions (a field with `kind` already set to
    `"radio_group"`): single-choice questions rendered as native radios.
    To answer one, return an entry with `kind` = `"radio_select"`,
    `selector` = the group's EXACT `selector` value, and `value` = the
    EXACT text of the option to select (one of the listed `options`). The
    work-authorization rules in (12) apply to radio groups too.
14. VOLUNTARY EEO / demographic questions (gender, race/ethnicity, veteran
    status, disability, "self-identification"): choose a decline option if
    one exists ("I don't wish to answer", "Decline to self-identify",
    "Prefer not to say"). If no decline option is offered, SKIP the group.
    Never guess a demographic value.

# Output format

Return ONLY valid JSON. No markdown fences, no commentary. Schema:

{{
  "fills": [
    {{"selector": "#first_name", "value": "Philipp", "kind": "text"}},
    {{"selector": "[name='gender']", "value": "diverse", "kind": "select_option"}},
    {{"selector": "#consent", "value": "true", "kind": "checkbox"}},
    {{"selector": "[data-jobbot-bg='0']", "value": "Yes", "kind": "button_click"}},
    {{"selector": "[data-jobbot-rg='1']", "value": "No", "kind": "radio_select"}}
  ],
  "language_detected": "de"
}}
"""

    def _apply_mapping(
        self, page: "Page", fills: list[dict[str, Any]],
    ) -> None:
        """Walk the LLM mapping and apply each entry. Per-field failures
        are logged but do not abort the whole pass; partial fills are
        better than zero fills for the human reviewer."""
        for entry in fills:
            sel = entry.get("selector")
            val = entry.get("value")
            kind = entry.get("kind")
            if not sel or val is None or not kind:
                continue
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                if kind == "text":
                    loc.fill(str(val), timeout=5_000)
                elif kind == "select_option":
                    loc.select_option(value=str(val), timeout=5_000)
                elif kind == "file":
                    loc.set_input_files(str(val), timeout=5_000)
                elif kind == "checkbox":
                    # Tick consent/privacy boxes so submit enables.
                    want = str(val).lower() in ("true", "1", "yes", "on")
                    if want and not loc.is_checked():
                        loc.check(timeout=5_000)
                    elif not want and loc.is_checked():
                        loc.uncheck(timeout=5_000)
                elif kind == "button_click":
                    # Single-choice button group: `sel` scopes to the group
                    # container, `val` is the exact option-button text. Click
                    # the matching button within the group.
                    loc.get_by_role(
                        "button", name=str(val), exact=True
                    ).first.click(timeout=5_000)
                elif kind == "radio_select":
                    # Single-choice radio group: `sel` scopes to the group
                    # container, `val` is the exact option label. Check the
                    # matching radio within the group.
                    loc.get_by_label(
                        str(val), exact=True
                    ).first.check(timeout=5_000)
                else:
                    log.warning("llm_fill_unknown_kind", kind=kind)
            except Exception as e:
                log.warning(
                    "llm_fill_field_failed",
                    selector=sel, kind=kind, error=str(e)[:100],
                )


_SYSTEM_PROMPT = """You are a form-mapping engine. You convert form-field
scrapes into precise field-to-value mappings for a Playwright runner.

Strict rules:
- Output ONLY valid JSON, no commentary, no markdown fences.
- Use the candidate's actual profile data; never fabricate values.
- Never use em-dashes (U+2014); use commas, periods, or hyphens instead.
- Skip fields you cannot map confidently. Partial mappings are correct.
- For SELECT inputs, return the option's `value` attribute, not its
  visible text.
"""
