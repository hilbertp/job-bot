# Build Milestones — file-level punch list

Reads alongside [PRD.md](./PRD.md). Each milestone maps PRD requirements to concrete files and acceptance tests. Implement them in order; run `pytest -q` after each before starting the next.

The scaffold is roughly 60% done. This document tells the implementer (Copilot or human) which 40% is missing and exactly where to put it.

---

## Status legend
- ✅ done in scaffold
- 🟡 partial / needs upgrade
- ⛔ stub only — body is `NotImplementedError`
- ⬜ not yet created

---

## Milestone 1 — Profile distillation + corpus + DB enrichment columns

**PRD sections:** §7.4, §7.2 FR-PER-01

| File | Status | What's needed |
|---|---|---|
| `src/jobbot/profile_distiller/corpus_loader.py` | ⛔ | implement `load_corpus()` — PDF/DOCX/MD readers, PRIMARY_ enforcement |
| `src/jobbot/profile_distiller/distiller.py` | ⛔ | implement `rebuild_compiled_profile()` — Sonnet call, write yaml |
| `src/jobbot/profile_distiller/website_fetcher.py` | ⛔ | implement `fetch_website()` — crawl truenorth, write md files |
| `src/jobbot/profile.py` | 🟡 | extend to also load `data/profile.compiled.yaml` and merge with `profile.yaml` |
| `src/jobbot/state.py` | 🟡 | ALTER TABLE seen_jobs: add `description_full TEXT`, `description_scraped INT`, `description_word_count INT`, `seniority TEXT`, `salary_text TEXT`, `apply_email TEXT`, `score_breakdown_json TEXT`, `enriched_at TEXT`, `scored_at TEXT`. Migration must be idempotent. |
| `src/jobbot/cli.py` | 🟡 | add subcommands: `profile rebuild`, `profile fetch-website` |
| `data/corpus/cvs/PRIMARY_*.pdf` | ⬜ | user drops their Opus CV here (manual step) |

**Acceptance:** `jobbot profile rebuild` produces a non-empty `data/profile.compiled.yaml` with all schema fields populated. `pytest -q` passes. Re-running with the same corpus produces a byte-identical file (modulo `compiled_at`).

---

## Milestone 2 — Enrichment step in the pipeline

**PRD sections:** §7.3

| File | Status | What's needed |
|---|---|---|
| `src/jobbot/enrichment/runner.py` | ⛔ | implement `enrich_new_postings()` — call each scraper's fetch_detail, persist columns |
| `src/jobbot/enrichment/email_extractor.py` | ⛔ | implement `extract_apply_email()` — regex + preference filter |
| `src/jobbot/scrapers/stepstone.py` | ⛔ | implement `fetch_detail()` |
| `src/jobbot/scrapers/xing.py` | ⛔ | implement `fetch_detail()` |
| `src/jobbot/scrapers/weworkremotely.py` | ⛔ | implement `fetch_detail()` |
| `src/jobbot/scrapers/freelancermap.py` | ⛔ | implement `fetch_detail()` |
| `src/jobbot/scrapers/freelance_de.py` | ⛔ | implement `fetch_detail()` |
| `src/jobbot/scrapers/linkedin.py` | ✅ | already implemented |
| `src/jobbot/pipeline.py` | 🟡 | insert enrichment phase between scrape and score; load body from DB into JobPosting before scoring |

**Acceptance:** after one full `jobbot run`, ≥80% of new LinkedIn / WWR / Stepstone postings have `description_scraped = TRUE` and `description_word_count > 200` in SQLite.

- `jobbot enrich --backfill` (CLI + `enrichment/backfill.py`): drains the pre-enrichment NULL-body tail without locking transient failures into `cannot_score:no_body`; supports `--dry-run`, `--source <name>`, and 1-req/s/source pacing. freelance_de rows are terminal-marked `cannot_score:source_unsupported`.

---

## Milestone 3 — Six-axis scoring + digest layout

**PRD sections:** §7.5, §7.9

| File | Status | What's needed |
|---|---|---|
| `prompts/match_score.md` | 🟡 | extend breakdown to six axes (role / domain / seniority / working_mode / language / compensation), add language_fit and compensation_fit rules |
| `src/jobbot/scoring.py` | 🟡 | parse the new breakdown, persist `score_breakdown_json`, average with `compensation_fit` skipped if not assessable |
| `src/jobbot/notify/templates/digest.html.j2` | 🟡 | render funnel snapshot at top, per-source health table, per-application proof-level rows, all-postings table sorted by score with faded no-body rows |
| `src/jobbot/pipeline.py` | 🟡 | feed the compiled profile to the scorer instead of just `profile.yaml` |

**Acceptance:** one real `jobbot run` produces a digest containing the funnel snapshot, every scored posting with axis breakdown, and applications-so-far with proof levels.

---

## Milestone 4 — Apply: email channel + 09:00 batched cron + cap

**PRD sections:** §7.7

| File | Status | What's needed |
|---|---|---|
| `src/jobbot/applier/email_channel.py` | ⛔ | implement `send_email_application()` — SMTP from truenorth, attach PDFs |
| `src/jobbot/applier/runner.py` | 🟡 | route by channel (`apply_email` set → email_channel; else form_adapter) |
| `src/jobbot/cli.py` | 🟡 | add `jobbot apply` subcommand — drains queue up to 8/day cap |
| `src/jobbot/config.py` | 🟡 | add `truenorth_smtp_host/port/user/pass`, `truenorth_imap_host/port` to Secrets |
| `.env.example` | 🟡 | document the new TRUENORTH_* env vars |
| `scheduling/com.philipp.jobbot.apply.plist` | ✅ | already created (REPO_PATH placeholder) |
| `src/jobbot/applier/adapters/greenhouse.py` | 🟡 | enable PDF upload paths (already wired, verify) |
| `src/jobbot/applier/adapters/lever.py` | 🟡 | same |

**Acceptance:** at least one real application sent successfully via email channel and one via Greenhouse form. Both appear in `applications` table at proof_level = 1. LinkedIn-discovered jobs route through the company's own channel, never Easy Apply.

---

## Milestone 5 — Outcome tracking + proof ladder

**PRD sections:** §7.8

| File | Status | What's needed |
|---|---|---|
| `src/jobbot/outcomes/proof_ladder.py` | ⛔ | implement `advance_proof_level()` and `verify_yourself_hint()` |
| `src/jobbot/outcomes/inbox_scanner.py` | ⛔ | implement `scan_inbox()` — IMAP walk, bounce / reply / interview / rejection detection |
| `src/jobbot/outcomes/classifier.py` | ⛔ | implement `classify_message()` — regex prefilter + Haiku fallback |
| `src/jobbot/state.py` | 🟡 | extend `applications` schema: `proof_level INT`, `proof_evidence TEXT (JSON)`, `last_checked_at TEXT`. Add `companies(domain TEXT PK, snooze_until TEXT)` table. |
| `src/jobbot/cli.py` | 🟡 | add `jobbot inbox-scan` subcommand |
| `scheduling/com.philipp.jobbot.inbox.plist` | ✅ | already created (REPO_PATH placeholder) |
| `src/jobbot/scoring.py` | 🟡 | check snooze table at heuristic stage; skip if company snoozed |

**Acceptance:** sent application reaches L2 within 24h of acceptance; replies advance to L3 within one daily inbox-scan cycle; rejection at L5 inserts a row in `companies` with snooze_until = now+6mo.

---

## Milestone 6 — Local dashboard + polish

**PRD sections:** §7.10, §11

| File | Status | What's needed |
|---|---|---|
| `src/jobbot/dashboard/server.py` | ⛔ | implement `run()` — FastAPI/Flask routes per `__init__.py` docstring |
| `pyproject.toml` | 🟡 | add `fastapi` (or `flask`), `uvicorn`, `pypdf`, `python-docx`, `markdownify` to dependencies |
| `README.md` | 🟡 | replace setup section with link to PRD + MILESTONES |
| `tests/` | 🟡 | add unit tests per milestone (corpus_loader, email_extractor, proof_ladder, classifier are easy wins) |

**Acceptance:** `jobbot dashboard` starts on localhost:5001, all routes render. `pytest -q` passes with ≥ 60% coverage on the new modules.

---

## Working agreement for Copilot

1. Implement one milestone at a time, top to bottom. Don't skip ahead.
2. After each milestone, run `pytest -q`. Do not start the next one until tests pass.
3. Before any destructive DB migration (DROP, ALTER COLUMN with data loss), stop and ask. Additive ALTER TABLE ADD COLUMN is fine.
4. Do not touch files marked ✅ unless the PRD requires it (Milestone 6 polish only).
5. Every new function gets a docstring referencing the PRD section it implements.
6. Secrets (`TRUENORTH_SMTP_PASS`, etc.) are requested in-flight from the user when first needed — never assume defaults.

---

## Cross-reference

- PRD: [PRD.md](./PRD.md) — single source of truth for behavior.
- Original architecture sketch: [PLAN.md](./PLAN.md) — historical, superseded by PRD where they conflict.
- Repo overview: [README.md](./README.md) — install + run.
