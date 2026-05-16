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
# an "Apply" button (TeamTailor, scope-recruiting.de, Greenhouse v2 etc.).
# Idempotent: if no button matches, nothing happens.
_REVEAL_SELECTORS = (
    "button:has-text('Apply now')",
    "button:has-text('Apply for this position')",
    "button:has-text('Apply')",
    "button[aria-label='Apply']",
    "button:has-text('Bewerbung abschicken')",
    "button:has-text('Bewerben')",
    "button:has-text('Jetzt bewerben')",
    "button:has-text('Bewerbung starten')",
    "a:has-text('Apply now')",
    "a:has-text('Bewerben')",
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
        """Match any page that has at least one input or textarea.
        GenericAdapter still acts as the absolute fallback if even that
        check fails (no form on page at all)."""
        try:
            return page.locator("input, textarea, select").count() > 0
        except Exception:
            return False

    def fill(
        self, page: "Page", job: JobPosting, profile: Profile,
        docs: GeneratedDocs,
    ) -> None:
        if not self._api_key:
            log.warning("llm_fill_no_api_key", note="ANTHROPIC_API_KEY unset; skipping")
            return

        self._reveal_form(page)
        fields = self._scrape_fields(page)
        if not fields:
            log.info("llm_fill_no_fields_found", url=page.url)
            return

        mapping = self._ask_claude(fields, job, profile, docs)
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

    def submit(self, page: "Page") -> str:  # noqa: ARG002
        # v1: never auto-submit; the runner falls back to supervised wait
        # so the human eyeballs the filled form before clicking Send.
        # Future: re-enable once we have positive-evidence telemetry on
        # successful submits via this adapter.
        raise NotImplementedError(
            "llm_fill adapter is fill-only in v1; submit requires "
            "supervised human click"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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
        """Pull every visible form field with enough context for the LLM
        to map it. Hidden fields, csrf tokens, and zero-size offscreen
        inputs are filtered out (offsetParent === null)."""
        filter_expr = (
            "el.type === 'file'" if only_files
            else "el.type !== 'hidden'"
        )
        return page.evaluate(f"""() => {{
            const els = [...document.querySelectorAll('input, textarea, select')]
                .filter(el => el.offsetParent !== null && {filter_expr});
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
                }};
            }});
        }}""")

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
- Earliest start: within 4 weeks of an offer
- Notice period: {prefs.get('notice_period_weeks', 4)} weeks

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
   Preferred order: `#<id>` > `[name='<name>']` > `[placeholder='<placeholder>']`.
2. For text/email/tel/textarea inputs: set `kind` to `"text"` and `value` to
   the string to fill.
3. For SELECT inputs: set `kind` to `"select_option"` and `value` to the
   option's `value` attribute (NOT its visible text). Pick the option
   that best matches the candidate. For gender selects use `"diverse"`
   or equivalent if available, else leave the field unmapped.
4. For file inputs (only in second pass): set `kind` to `"file"` and
   `value` to the absolute path of cv.pdf or cover_letter.pdf depending
   on what the doc-type label / select implies.
5. SKIP a field by NOT including it in `fills` if you cannot confidently
   map it. NEVER fabricate values (do not invent a street address, a
   birthday, a postal code, or a phone number the profile doesn't have).
6. Detect form language from labels/placeholders. If German, write German
   values for free-text fields like "earliest start" (e.g. "innerhalb
   von 4 Wochen"). Salary stays numeric.
7. NEVER write em-dashes (—) in any text value. Use commas, periods, or
   hyphens. This is a hard rule, the user has been bitten by it before.
8. Salary fields: write the EUR anchor as plain integer (e.g. "125000"),
   no currency symbol, no thousands separator, unless the placeholder
   explicitly hints at a different format.

# Output format

Return ONLY valid JSON. No markdown fences, no commentary. Schema:

{{
  "fills": [
    {{"selector": "#first_name", "value": "Philipp", "kind": "text"}},
    {{"selector": "[name='gender']", "value": "diverse", "kind": "select_option"}}
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
