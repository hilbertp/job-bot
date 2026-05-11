# Test coverage gap analysis

Framed around the four user journeys the system actually supports
(per user, 2026-05-11). For each journey: what works today, what's
tested, what isn't. The "MISSING" rows are the work items.

Test suite as of the audit: `pytest -q` → 25 passed, 1 skipped, 2 xfailed.

---

## Journey 1 — "What happened to my last run?"

> How many were scraped, what are the stats, which portals are performing,
> how do I re-run?

### Works today

| Question | Where the answer lives |
|---|---|
| how many scraped | `runs.n_fetched` ([state.py:57-67](src/jobbot/state.py#L57-L67)) |
| stats of the run | `runs.summary_json` (stages, score_stats, blockers) |
| portal performance | `summary_json.per_source_fetched` + `per_source_new` |
| browse history | dashboard `/api/runs`, `/runs/<id>` ([dashboard.py](src/jobbot/dashboard.py)) |
| re-run | `jobbot run` from terminal |

### Covered by tests

- Nothing directly. `test_pipeline_enriches_new_jobs_before_scoring` calls
  `pipeline.run_once` end-to-end but with a fake scraper and fake LLM, and
  it asserts enrichment behavior — not run-summary persistence.

### MISSING

- E2E: `jobbot run` (or `pipeline.run_once`) produces a `runs` row with
  `n_fetched / n_new / n_generated / n_applied / n_errors` set, plus a
  `summary_json` containing `per_source_fetched` and `per_source_new`.
- API contract: `GET /api/runs` returns the last N runs with the expected
  field shape.
- Page render: `GET /runs/<id>` returns 200 and the template fills out
  for a real run row.
- No UI affordance to trigger a re-run from the dashboard — that's a
  product gap, not just a test gap.

---

## Journey 2 — "What are my match scores? What was filtered? Why? How's body coverage?"

### Works today

| Question | Where the answer lives |
|---|---|
| match scores | `seen_jobs.score`, `score_reason`, `score_breakdown_json` |
| what was filtered | `status = 'filtered'` rows + `score_reason` |
| why it was filtered | `score_reason` (e.g. `deal-breaker keyword: junior`) |
| cannot_score:* reasons | `status = 'cannot_score:no_body'` / `:no_primary_cv` |
| body coverage | `description_word_count >= 200` over total |
| pipeline funnel | dashboard `/api/pipeline-funnel` |
| stage-2 listing | dashboard `/api/positions`, Stage-2 table in [index.html](src/jobbot/templates/index.html) |
| digest separation | `cannot_score:*` rendered in its own section ([digest.html.j2](src/jobbot/notify/templates/digest.html.j2)) |

### Covered by tests

- Heuristic filter: 5 tests in [test_scoring_heuristic.py](tests/test_scoring_heuristic.py)
- LLM-scorer preconditions: `test_llm_score_refuses_short_body`,
  `test_llm_score_refuses_when_primary_cv_missing`
- User-message structure: `test_user_message_has_five_sections_in_order`
- DB columns exist: `test_state_enrichment_columns_exist` (description_full,
  description_word_count, etc.)

### MISSING

- E2E: a filtered job → `seen_jobs.status='filtered'` with the right
  `score_reason` persisted. We test the function `passes_heuristic`
  returns the right tuple, but not that `update_status` writes it.
- E2E: a `cannot_score` path → status persists, digest shows it under
  the right section. `send_digest` is monkeypatched in the only
  pipeline test, so the digest path is uncovered end-to-end.
- API contract: `GET /api/positions`, `GET /api/pipeline-funnel`,
  `GET /api/latest-run-portal-hits`.
- Body-coverage metric: no test that the dashboard or digest exposes
  the % of postings ≥ 200 words by source.

---

## Journey 3 — "Which listings got a custom CV+CL? Where are the files? Score before vs after?"

### Works today

| Question | Where the answer lives |
|---|---|
| which listings | `status='generated'` rows |
| posting URL | `seen_jobs.url` |
| posting description | `seen_jobs.description_full` |
| custom CV file | `output_dir/cv.md` + `cv.html` + `cv.pdf` |
| custom cover letter | `output_dir/cover_letter.md` + `.html` + `.pdf` |
| score BEFORE | `seen_jobs.score` (base CV → LLM) |
| score AFTER | `seen_jobs.score_tailored` (tailored CV+CL → LLM) |
| delta | computed in `/api/shortlist`, rendered in Stage-3 card |
| dashboard view | Stage-3 panel + `/shortlist/<job_id>/<filename>` doc serving |

### Covered by tests

- `llm_score_tailored` refuses empty inputs: `test_llm_score_tailored_refuses_empty_inputs`
- Tailored user-message structure: `test_user_message_tailored_variant_swaps_cv_and_injects_cover_letter`

### MISSING

- E2E: `generate_documents` produces every expected file
  (`cv.md`, `cv.html`, `cv.pdf`, `cover_letter.md`, `cover_letter.html`,
  `cover_letter.pdf`) under `output/<date>/<slug>/`. Today only the
  static-CV fallback path is implicitly exercised; the tailored PDF render
  via WeasyPrint is silently failing on this host (pango missing) and we'd
  never know from the test suite.
- E2E: after Stage-3 generation, the pipeline writes BOTH `score` and
  `score_tailored` for the same job row.
- API contract: `GET /api/shortlist` returns `score`, `score_tailored`,
  `tailored_reason`, `score_delta`, `cv_html_url`, `cover_letter_html_url`.
- File serving: `GET /shortlist/<job_id>/cv.html` returns 200 with content;
  path-traversal attempts are rejected.

---

## Journey 4 — "Sent / received / waiting / rejected / interview_invitation"

### Works today

| Question | Where the answer lives |
|---|---|
| sent | `status = 'apply_submitted'` |
| failed to submit | `status = 'apply_failed'` |
| needs human review | `status = 'apply_needs_review'` |
| application attempt log | `applications` table (one row per attempt) |

### NOT modeled — backend gap, not just a test gap

The system tracks **outbound** application state. It doesn't model anything
**inbound** from the employer:

| User's intent | Backend support |
|---|---|
| "received" (employer acknowledged) | ❌ no status, no column |
| "waiting" (no response after N days) | ❌ not derived anywhere |
| "rejected" (employer rejection email) | ❌ no status, no inbox poller for response emails |
| "interview_invitation" | ❌ no status, no inbox poller |

The closest existing infrastructure is the IMAP polling used for OTP
codes during apply ([`src/jobbot/otp/imap.py`](src/jobbot/otp/imap.py)).
Same Gmail account, same fetcher pattern — but the OTP path discards
non-OTP mail. A response classifier would reuse the connection, scan for
sender domain / subject patterns, and update the application row.

### MISSING

This whole journey is **product work**, not just test work. Sketch:

1. New `JobStatus` values: `EMPLOYER_RECEIVED`, `WAITING_RESPONSE`,
   `REJECTED`, `INTERVIEW_INVITED`.
2. New `applications` columns or a `responses` table: `received_at`,
   `last_response_at`, `response_type`, `response_subject`, `response_snippet`.
3. Background job (or new CLI subcommand `jobbot scan-inbox`) that polls
   the same Gmail mailbox and classifies replies.
4. Dashboard Stage-4 panel: pipeline column for each lifecycle state,
   ability to manually correct misclassified rows.
5. Tests at every layer: classifier rules, status transitions, panel render.

Once the backend exists, tests follow the same patterns as Journeys 1-3.

---

## Suggested order of work

The four journeys aren't equal. Recommended sequence:

1. **Backfill tests for Journey 1 and 2** — fast, the backend exists.
   Adds confidence to all subsequent work. ~5-8 tests.
2. **Backfill tests for Journey 3** — also fast. ~4-6 tests.
3. **Decide on Journey 4 backend** — schema + classifier first. Tests
   come with the implementation.

The current 25 tests cover correctness of the *logic units* (heuristic,
scoring preconditions, message structure, schema migration). They do
NOT cover *what the user actually sees and does*. That's the gap this
audit identifies.
