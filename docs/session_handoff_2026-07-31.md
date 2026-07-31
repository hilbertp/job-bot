# Session handoff, 2026-07-31

Written for someone picking this up cold. Two tracks ran in parallel this
session: **job-application work** (documents, scoring decisions) and
**pipeline engineering** (why the runs were broken and what was changed).
The engineering track is the one with unmerged code.

---

## 1. Where the code is

**Branch `fix-market-age-gate-and-enrich-fallback`, four commits, not pushed,
no PR yet.**

```
93533ea docs(applications): canonical positioning, EWERK package, run knowledge
e932459 fix(dashboard): make the header answer questions the user actually has
3206890 fix(pipeline): stop runs burning their whole budget on a self-refilling backlog
54bf1dd fix(render): full-bleed paper background in generated PDFs
```

**Important: this code is already running in production.** `.venv-1` is an
editable install pointing at `src/`, and the launchd agents run from the
working tree. Run 298 (2026-07-31 19:42 UTC) executed with all of it. So the
PR is bookkeeping, not activation. Do not assume `main` reflects what the
machine is doing.

`data/config.yaml` is **gitignored**. Local values that differ from the
committed defaults:

| key | local | default in `config.py` |
|---|---|---|
| `max_market_age_days` | 3 | 3 |
| `publish.max_age_days` | 7 | 45 |
| `score_concurrency` | (unset, uses default) | 4 |
| `score_failure_breaker` | (unset, uses default) | 5 |

---

## 2. What was actually wrong with the runs

The user's question was "why would scoring fail at all, we control that
ourselves". He was right: nothing about scoring itself failed. Four
environmental causes, each proven from the data:

1. **Self-refilling backlog.** A failed scoring call resets the row to
   `SCRAPED`; the next run picks it up and fails again. Rows with no
   `posted_at` (14% of the corpus) were immortal because the recency gate
   only looked at `posted_at`. Run 297 spent **199 scoring calls on 13 new
   postings**; 186 were retries.
2. **Laptop sleep.** Run 296 ran 72 minutes and produced **zero** successful
   LLM calls. `pmset -g log` shows `Clamshell Sleep` seven minutes after it
   started, continuously through the whole window.
3. **Overlapping runs.** Runs 292 and 293 started 114 seconds apart. Five
   launchd invocations (`scrape` at 08/12/16/20, `daily` at 15) plus the
   dashboard's "Run now" button, with no mutual exclusion beyond the SQLite
   writer lock. Two stale processes were also found alive, one for **38
   hours**, and were terminated with the user's approval.
4. **CLI mid-upgrade.** Runs 287/288 failed 200x each with
   `FileNotFoundError`; the `claude` symlink was recreated that evening at
   19:17.

### What changed

- `too_old_for_market()` in `scoring.py`, falling back to `first_seen_at`,
  applied **before enrichment** so a stale row costs neither an HTTP detail
  fetch nor an LLM call. The old hardcoded `RECENT_POSTING_DAYS = 7` became
  `config.max_market_age_days`, default 3.
- Circuit breaker: stop the scoring stage after N consecutive identical
  failures, leave the rest `SCRAPED`.
- `_single_run_lock()`: an `flock` around `run_once`; a second run returns
  immediately.
- `jobs_needing_enrichment()` now also retries `cannot_score:no_body` rows
  (previously only `description_scraped IS NULL`, so one 429 stranded a row
  forever).
- Scoring LLM calls go through a `ThreadPoolExecutor`; **all DB writes stay
  on the main thread**. Free gates are re-evaluated in the loop on purpose:
  they are regex work, and duplicating them was safer than restructuring the
  persistence code.
- Housekeeping probes `digest.generate_docs_above_score` instead of
  `score_threshold`, which is 0 here and made it HEAD-probe ~929 rows a run.
- Run summaries persist deduplicated error **messages**; only the exception
  type survived before, which is why "LlmError x177" was undiagnosable.

### Measured result

| | run 297 (before) | run 298 (after) |
|---|---|---|
| total | 33m 43s | **5m 46s** |
| scoring calls | 199 | **18** |
| scoring failures | 1 | **0** |
| scoring stage | 23m 18s | 29s |

`scraped` went 1005 → ~0 (retired at the age gate, zero LLM cost);
`cannot_score:no_body` 393 → 210 (183 recovered by the retry fix).

---

## 3. Dashboard changes

The stat bar led with `len(jobs)`, which is `publish.max_jobs` once the
corpus outgrows it: it read "300 matches" every day. It now reads
**new today | of those 80+ | packages waiting to be sent | rows shown**,
with the unsent count taken over the whole corpus so a narrower table window
cannot hide a to-do.

Live-run panel: moved above the stat bar with an accent border; stage counts
carry their unit (`29/29 searches across 14 job boards`, not a bare 29/29
that reads as a percentage or as 29 sites); pending stages say what they are
waiting for.

Also fixed a real counting bug: `completed` included filtered and
cannot-score rows while `skipped`/`failed` counted the same rows again, so
the panel rendered **86/63**.

---

## 4. Open items

**Engineering**

- Push the branch, open the PR, merge. `WORKFLOW.md` is mandatory policy here:
  no direct commits on `main`, integration via GitHub PR.
- **37 of 100 detail fetches fail.** Largely expired listings: StepStone
  returns HTTP 410, LinkedIn redirects to `?trk=expired_jd_redirect`.
  Detecting those and marking `listing_expired` immediately would stop them
  being retried every run. This is the next real win.
- `caffeinate` is **not** in `com.philipp.jobbot.scrape.plist`. It only
  prevents idle sleep, never clamshell sleep. The user was told
  `sudo pmset -c disablesleep 1` is his call; it is persistent until set
  back to 0.
- `scored_at` has not been written since 2026-07-28 although rows are being
  scored. The user explicitly deprioritised this.
- The launchd agents use `.venv-1`; testing in this session used `.venv`.
  Worth aligning.

**Tests**

`25 failed, 423 passed` is the **pre-existing baseline**, verified twice by
stashing the changes. All 25 are stale dashboard-template assertions. One
genuine regression was introduced and fixed during the session (the literal
`'waiting'` assertion in `test_publish_site.py`), and it was flagged to the
user before the test was touched, per his standing rule.

Beware: the suite is **order-dependent**. A polluted run reported 44
failures; a clean run of the same code reported 26. Always compare full-suite
runs against a freshly stashed baseline, never against a remembered number.

**Applications**

- **EWERK Group, Product Owner (Stuttgart, hybrid)**: submitted. Base 85 /
  tailored 93.
- **BG prevent via ISO Recruiting**: submitted. Base 82 / tailored 96.
  Headhunter intel: they replaced two people in a row on this mandate over
  the arrogance of the Ober- and Chefärzte, so temperament is the real
  selection criterion. Do not re-quote above the 80 EUR/h already offered.
- **Scalable Capital, PM AI Platform**: base 90 / tailored 96, the strongest
  permanent fit in months, **abandoned at the portal's degree-certificate
  upload**. He owns no certificate. Second confirmation at this employer; do
  not build for them again.
- **Agility PR Solutions**: base 87 / tailored 93, package built, **not
  sent**. Comp is 90-120k CAD, roughly 57-76k EUR, far under his floor.
- **SoftProject**: fit 88, deliberately **not built**: 70-77k EUR band plus
  a Zeugnis requirement.

---

## 5. Landmines

- `data/applications/PROFILE.md` holds the canonical positioning. Read it
  before writing any document. Two rules cost real rework this session:
  never write a "I have not worked with X" disclaimer without checking the
  station stack lines first (Django was falsely disclaimed), and never frame
  him as a hands-on developer (he is a technical PM with an AI-first
  approach; naming a stack he owned is right, claiming he writes in it is
  not).
- No em-dashes in any generated artefact. No `lovable.*` URLs anywhere. The
  contact address is `hilbert@true-north.berlin`, never projuncta.
- Anthropic API credits are depleted; the LLM backend is `claude_cli` against
  the Max plan. Rendering documents outside the pipeline needs the stub-
  `anthropic`-module recipe (see `data/applications/APPLICATIONS.md`).
- The scoring prompt contains only the CV, the compiled profile, the hard
  preferences, the job body and its metadata. **No history, no previous
  scores, no other postings.** The size of the corpus does not affect prompt
  cost; it affected housekeeping HEAD probes, which is now bounded.
