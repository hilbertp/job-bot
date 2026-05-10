# jobbot — Product Requirements Document

**Version:** 1.0 (v1 PRD, supersedes prior PLAN.md as the source of truth)
**Owner:** Philipp Hilbert
**Status:** Approved for build
**Last updated:** 2026-05-10

---

## 1. Summary

jobbot is a personal automation tool that finds product-role openings across the German job market, decides which ones are worth pursuing, prepares the application materials, sends them, and tracks the outcome with conservative, evidence-based reporting. It runs on the user's Mac and produces one short email each morning that the user reads in five minutes to decide what (if anything) needs human follow-up.

The principle behind every design decision: **maximum visibility, conservative action, full reversibility.** Show every posting and every score; only spend money and recruiter goodwill on high-confidence matches; never claim success without evidence; never destroy data.

---

## 2. Background and problem

A senior product-role search in Germany involves checking 5–7 job boards every day, reading dozens of postings, deciding which are worth applying to, tailoring a CV and writing a cover letter for each, sending the application through whatever channel the company uses, and remembering whether each one actually went through and got a response. The "find, read, decide, write, send, track" loop takes 10–15 hours a week and most of it is mechanical work that doesn't benefit from human judgment.

The user has already done this loop manually long enough to have a corpus of 5 distinct CVs and 4 cover letters across fintech / crypto / DeFi / security companies (N26, BCB, Suri Ventures, FeDi, 0G, Upwind). That corpus is the seed data the tool will distill to understand the user's capabilities and writing voice.

---

## 3. Goals and non-goals

### 3.1 Goals (v1)

1. **Discover** every product-owner and product-manager posting on LinkedIn, StepStone, Xing, weworkremotely, freelancermap.de, freelance.de, and (best-effort) Indeed within 4 hours of publication.
2. **Distill** a normalized capabilities profile from the user's existing CVs and cover letters; rebuild on demand.
3. **Score** each posting against the distilled profile on six axes with full transparency (per-axis breakdown, not a black-box number).
4. **Tailor** a CV (light edits, never invent) and write a fresh cover letter for every match scoring ≥70.
5. **Apply** automatically via the appropriate channel (employer's email, Greenhouse / Lever / Workday form), capped at 8 submissions per day.
6. **Track** the outcome with a 5-level proof ladder (SMTP accepted → no bounce → human reply → interview → rejection), defaulting to "fail" until evidence proves otherwise.
7. **Report** once per day via a digest email at 08:30, sorted by score, with per-stage funnel stats and per-application proof status.

### 3.2 Non-goals (v1, explicit)

- LinkedIn Easy Apply automation (ToS-forbidden; account-ban risk asymmetric to value).
- Indeed scraping if Cloudflare bypass is required (low-value source for senior product roles).
- Web UI for general use — CLI + email digest only. (A read-only local dashboard at `localhost:5001` exists for the user's own inspection.)
- Multi-user / multi-tenant.
- Sending money, executing trades, or any other irreversible financial action.
- Background nag notifications about retries / failed scrapers.

---

## 4. User persona

Single user: Philipp Hilbert. Senior product professional searching across Germany. Comfortable with CLI, shell, light Python. Has Anthropic API access. Has a personal Gmail and a professional `hilbert@truenorth.berlin` address (the latter used for all outbound applications).

---

## 5. Success metrics

These are read out of the SQLite store and surfaced in every digest. The user can compare them week over week.

| Metric | Definition | Target after 4 weeks |
|---|---|---|
| Source-level body-fetch rate | % of new postings per source where the detail body was successfully scraped | ≥ 80% per active source |
| Above-threshold rate | % of scored postings reaching score ≥ 70 | 15–35% (sanity range) |
| Application send rate | applications successfully delivered (proof L2+) / applications attempted | ≥ 85% |
| Reply rate | applications reaching proof L3 / applications at L2 | ≥ 15% (industry-typical for cold is 5–10%) |
| Interview rate | applications reaching proof L4 / applications at L2 | ≥ 5% |
| End-to-end conversion | proof L4 / total scrape hits | ≥ 1% |

If any number is materially off these targets after the second week of real operation, the user retunes weights, threshold, or the corpus.

---

## 6. Funnel and lifecycle

The tool implements a strict 9-stage funnel. Every posting moves through these stages and is persisted at each transition.

```
1. Scrape hit          — pulled by a source-specific scraper
2. New & unique        — passes dedup against the SQLite store
3. Body fetched        — detail page scraped, full description stored
4. Heuristic passed    — no deal-breaker keywords / industries
5. Match score ≥ 70    — LLM scored above the apply threshold
6. Application sent    — submitted via email or form
7. Delivered (L2)      — no bounce after 24h
8. Acknowledged (L3)   — human reply received
9. Interview (L4)      — interview invitation received
   (terminal: rejected (L5))
```

The visualization the user reviewed is the canonical reference for this funnel.

---

## 7. Functional requirements

### 7.1 Discovery (Scrape)

**FR-DIS-01.** Run a scrape every 4 hours between 08:00–20:00 local time via macOS `launchd` LaunchAgent. Catch up on missed runs (e.g. after sleep).

**FR-DIS-02.** Sources, with priority and method:
| Source | Priority | Method | Cookie required |
|---|---|---|---|
| LinkedIn | P0 | guest jobs API HTML | optional (`LINKEDIN_LI_AT`) |
| StepStone | P1 | httpx + selectolax | no |
| Xing | P1 | httpx + selectolax | no |
| weworkremotely | P1 | RSS | no |
| freelancermap.de | P2 | HTML scrape `/projektboerse.html` | no |
| freelance.de | P2 | HTML scrape `/projekte` | no |
| Indeed | P3 (best-effort) | RSS where alive | no |

**FR-DIS-03.** Each scraper exposes `fetch(query)` returning `JobPosting` objects (listing-card data only). Failure of one source does not stop the rest.

**FR-DIS-04.** Initial scrape window on first run = **last 7 days**. Subsequent runs only fetch new postings since the last run; older postings are dropped (dead weight).

**FR-DIS-05.** Per-source rate limiting: ≥ 3 seconds between paginated calls; stop on first 429 / 999 status and disable that source for the rest of the run.

**FR-DIS-06.** Configurable search queries per source in `data/config.yaml`. Default queries cover "product owner" and "product manager" in Germany; user can add narrower queries per role.

### 7.2 Persistence

**FR-PER-01.** Every posting is upserted into SQLite (`data/jobbot.db`) on first sight, with the columns:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | stable hash of source + canonical URL |
| `source` | TEXT | e.g. `linkedin` |
| `url` | TEXT | canonical URL with tracking params stripped |
| `title` | TEXT | from listing card |
| `company` | TEXT | from listing card |
| `location` | TEXT | from listing card or detail page |
| `first_seen_at` | TEXT (ISO ts) | append-only |
| `description_full` | TEXT NULL | from detail-page enrichment |
| `description_scraped` | INTEGER (bool) | NULL until enrichment runs, then 0/1 |
| `description_word_count` | INTEGER NULL | populated when scraped |
| `seniority` | TEXT NULL | extracted from body or criteria block |
| `salary_text` | TEXT NULL | raw extracted band ("€70-90k" etc.) |
| `apply_email` | TEXT NULL | extracted via regex from body |
| `apply_url` | TEXT NULL | from listing card or extracted |
| `score` | INTEGER NULL | 0-100 |
| `score_reason` | TEXT NULL | one-line explanation |
| `score_breakdown_json` | TEXT NULL | per-axis scores |
| `status` | TEXT | enum: scraped / enriched / scored / generated / applied / done |
| `enriched_at`, `scored_at`, `generated_at` | TEXT NULL | timestamps |
| `output_dir` | TEXT NULL | path to generated CV+CL |
| `raw_json` | TEXT | original scraped object |

**FR-PER-02.** Body snippet for the digest is derived at render time from `description_full[:300]` — not stored separately.

**FR-PER-03.** Database is the canonical record. Any posting can be re-scored or re-generated against an updated profile without re-scraping.

### 7.3 Enrichment

**FR-ENR-01.** Each scraper exposes a `fetch_detail(job)` method that returns the same `JobPosting` with `description_full` populated, plus any structured criteria (seniority, employment type, salary if visible).

**FR-ENR-02.** After the scrape phase, the pipeline calls `fetch_detail` on every new posting from the current run, in series, with per-source rate limits.

**FR-ENR-03.** Set `description_scraped = TRUE` only when body is non-empty and ≥ 100 words. Otherwise mark FALSE and keep the listing snippet only — these postings will not be scored.

**FR-ENR-04.** Extract `apply_email` from the body via regex (`[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`), prioritizing addresses with the local-part `careers`, `jobs`, `bewerbung`, `recruiting`, `talent`, or `hr`.

### 7.4 Profile distillation

**FR-PRO-01.** User maintains a corpus directory:
```
data/corpus/
├── cvs/
│   ├── PRIMARY_Philipp_Hilbert_opus_CV.pdf   — source of truth for facts (employers, dates, achievements)
│   └── *.{pdf,docx,md}                        — historical / role-specific variants (extra phrasings only)
├── cover_letters/
│   └── *.{pdf,docx,md}                        — used purely for voice extraction, never for facts
└── website/
    └── true-north.berlin/*.md                 — fetched snapshot of the user's master memo site
```

The PRIMARY-prefixed CV is treated as authoritative. Other CVs contribute *only* additional phrasings the user has previously approved; if a non-primary CV claims a title or date that contradicts the primary, the primary wins.

**FR-PRO-02.** The CLI command `jobbot profile rebuild` reads the entire corpus, calls Claude (Sonnet) once with all documents in a single prompt, and writes `data/profile.compiled.yaml` containing:
- `voice` — distilled tone descriptors and 5–10 sample phrases the user actually uses
- `capabilities` — normalized list (skill, years, source CV)
- `domains` — industries the user has worked in, with depth signal
- `achievements` — quantified outcomes verbatim from the corpus, deduped
- `seniority_signals` — title progression, team-size-managed, scope keywords
- `languages` — claimed in CVs

**FR-PRO-03.** `data/profile.yaml` (hand-edited) holds only hard preferences:
```yaml
preferences:
  remote: true / hybrid_ok / on_site_ok
  willing_to_relocate: bool
  desired_salary_eur: { min, max }
  notice_period_weeks: int
  work_authorization: str
  languages: [de_native, en_fluent]
deal_breakers:
  industries: [defense, gambling]
  keywords: [unpaid, commission only]
  on_site_only: bool
```

**FR-PRO-04.** Both files are loaded and merged at scoring + generation time. The compiled file is regenerated on demand only — never automatically — so the user can review what the distiller produced before it goes live.

**FR-PRO-05.** Website ingestion via separate command `jobbot profile fetch-website`:
- Crawls `https://true-north.berlin` (and same-domain links), converts each page to Markdown, writes to `data/corpus/website/`.
- Treated as a *static* corpus source — the user's website is finalized; the command is only invoked when the user explicitly chooses to refresh.
- After fetching, the user runs `jobbot profile rebuild` to fold the latest snapshot into `profile.compiled.yaml`.
- Website content is used by the cover-letter generator for voice + worldview signal, and by the scorer for richer domain context.

### 7.5 Scoring

**FR-SCO-01.** A two-stage matcher:
1. **Heuristic prefilter** — drops only on hard deal-breakers (deal-breaker keywords / industries / on-site-only-when-remote-required). Does NOT enforce skill-keyword presence.
2. **LLM scorer** (Claude Haiku) — runs on every posting that has a body and passes the heuristic.

**FR-SCO-02.** The LLM returns a JSON object:
```json
{
  "score": 0-100,
  "reason": "one-sentence explanation",
  "breakdown": {
    "role_match": 0-100,
    "domain_match": 0-100,
    "seniority_match": 0-100,
    "working_mode_match": 0-100,
    "language_fit": 0-100,
    "compensation_fit": 0-100
  }
}
```

**FR-SCO-03.** Combined `score` = equal-weight average of the six axes, rounded to integer. Weights are configurable in `config.yaml` (defaulted to equal in v1; user retunes after week 1 of real data).

**FR-SCO-04.** If `compensation_fit` cannot be assessed (salary not stated), it is excluded from the average, not zeroed.

**FR-SCO-05.** Single threshold: `apply_threshold: 70`. Postings ≥70 trigger CV+CL generation and an apply attempt. Postings below 70 are still shown in the digest, sorted by score.

### 7.6 Document generation

**FR-GEN-01.** For every posting reaching `score ≥ 70`, the generator (Claude Sonnet) produces:
- `cv.md`, `cv.html`, `cv.pdf` — lightly tailored from the corpus
- `cover_letter.md`, `cover_letter.html`, `cover_letter.pdf` — fully tailored

**FR-GEN-02.** The CV tailoring prompt enforces: never invent, never add bullets, only re-rank and re-word existing material. The cover letter prompt enforces the user's distilled voice.

**FR-GEN-03.** Output language follows posting language: English by default; German when the posting is in German (heuristic: `(m/w/d)` or `(w/m/d)` anywhere, or > 30% German stopwords).

**FR-GEN-04.** Filenames: `Hilbert_Philipp_CV.pdf`, `Hilbert_Philipp_Cover_Letter.pdf` (default; configurable).

**FR-GEN-05.** PDFs rendered via WeasyPrint. If WeasyPrint is unavailable, log a warning and skip the application step (no PDF = no upload).

### 7.7 Application submission

**FR-APP-01.** Channel selection per posting:
- `apply_email` present → channel = `email`
- else `apply_url` matches Greenhouse / Lever / Workday → channel = `form`
- else channel = `manual`, status = `cannot_apply`, surfaced for human

**FR-APP-02.** Email channel: SMTP from `hilbert@truenorth.berlin`. Subject template language-aware:
- DE: `Bewerbung als <Title>`
- EN: `Application: <Title> — Philipp Hilbert`

Body = the cover letter text (markdown rendered to plain text). PDFs attached.

**FR-APP-03.** Form channel: Playwright-driven, per-ATS adapter. CV + cover letter PDFs uploaded into the standard fields. Screener questions answered from `screener_defaults` in `profile.yaml`; LLM fallback for unrecognized questions, with confidence < 0.8 → mark `needs_review`, do not submit.

**FR-APP-04.** Daily submission cap: **8 applications per day** across all sources. Exceeded postings remain at `score≥70, generated, queued` until the next day.

**FR-APP-05.** Apply timing: queued through the day, submitted in a single 09:00 batch the next morning (right after the digest goes out). Avoids "9 applications in 2 minutes" anti-bot patterns.

**FR-APP-06.** Failure of one apply attempt does not retry. Status flips to `failed` with reason; surfaced in next digest.

**FR-APP-07.** LinkedIn Easy Apply is **never** automated, even if `auto_submit: true` is enabled for the source. LinkedIn-discovered postings are routed to email/form via the company's own channel only.

### 7.8 Outcome tracking (proof ladder)

**FR-OUT-01.** Every application is tracked with a `proof_level` integer 0–5 and a `proof_evidence_json` accumulator:

| Level | Evidence | Captured by | "Verify yourself" hint shown in digest |
|---|---|---|---|
| 0 | none | initial state | (failed before send) |
| 1 | SMTP 250 OK | email send call | "Check Sent folder in hilbert@truenorth.berlin for [subject]" |
| 2 | no bounce after 24h | daily IMAP scan | "If no `mailer-daemon` reply by tomorrow, the email was accepted by the recipient" |
| 3 | reply from `@<company-domain>` | daily IMAP scan + sender match | "Search inbox for replies from <domain>" |
| 4 | reply contains interview / Vorstellungsgespräch / calendar invite | LLM classifier on inbound mail | "Check inbox/calendar for the invitation" |
| 5 | reply contains rejection language | LLM classifier on inbound mail | "Check inbox for the message containing the role title" |

**FR-OUT-02.** `applications` table:
```
job_id            TEXT PK
attempted_at      TEXT
channel           TEXT (email | form | manual)
proof_level       INT  (0-5)
proof_evidence    TEXT (JSON, append-only)
status            TEXT (pending | submitted | acknowledged | interview | rejected | failed | cannot_apply)
needs_review      INT  (bool)
last_checked_at   TEXT
```

**FR-OUT-03.** A separate daily cron at 09:30 runs `jobbot inbox-scan`: connects to IMAP, walks unread messages from companies we've applied to in the last 90 days, advances proof levels accordingly.

**FR-OUT-04.** When a posting reaches L5 (rejected), the `companies` snooze table records the company with a `snooze_until` 6 months in the future. Future postings from that company are skipped at the heuristic stage.

### 7.9 Notification

**FR-NOT-01.** Daily digest at 08:30 from `hilbert@truenorth.berlin` to the same address.

**FR-NOT-02.** Digest content (in order):
1. **Funnel snapshot** — counts at each of the 9 stages from the previous 24 h.
2. **Per-source health** — count and body-fetch success rate per source.
3. **Applications outcome** — current proof level for every application sent in the last 14 days, with the verify-yourself hint.
4. **Today's matches** — every posting scored in the last 24h, sorted by score descending, in a single table; rows where `description_scraped = FALSE` are visually faded. Cap: 100 rows; truncated rows pushed to the local dashboard.
5. **Errors** — anything that broke during the run, summarized.

**FR-NOT-03.** No instant high-score alerts in v1. All notifications happen in the daily digest.

**FR-NOT-04.** If the daily digest itself fails to send (SMTP error), a fallback failure email goes out from a backup channel (Gmail, configured in `.env`).

### 7.10 Local dashboard

**FR-DSH-01.** `jobbot dashboard` starts an HTTP server on `localhost:5001` rendering the same data as the digest, but with all postings (not just top 100) and search/filter controls.

**FR-DSH-02.** Read-only. No state mutation from the UI in v1.

---

## 8. Non-functional requirements

**NFR-01. Hosting.** Runs on the user's Mac via launchd. No VPS, no cloud. If the Mac is asleep through a scheduled run, launchd catches up on wake.

**NFR-02. Cost.** Anthropic API spend ≤ €120/month at expected volume (~150 postings/day scored, ~30/day generated).

**NFR-03. Storage.** SQLite under `data/jobbot.db`. Expected growth ~3 MB/week including full bodies. No retention policy in v1.

**NFR-04. Secrets.** Every credential in `.env` (gitignored). Application code never logs secrets.

**NFR-05. Rate-limit safety.** All scrapers obey ≥ 3 s between paginated calls, jittered. First 429 / 999 disables the source for the rest of the run and surfaces in the digest.

**NFR-06. Failure isolation.** Any individual scraper, scorer call, generator call, or apply call can fail without aborting the rest of the run. Errors accumulate into the digest's error section.

**NFR-07. Reproducibility.** Re-running the same scrape against the same DB produces zero new rows (idempotent dedup). Re-scoring from a stored body uses the same prompt and stable model version.

**NFR-08. Languages.** All user-facing output (digest, cover letters, emails) is generated in the appropriate language: English by default, German when the posting language is German.

---

## 9. Architecture (one-screen overview)

```
                              ┌──────────────────────┐
                              │   data/corpus/       │
                              │   data/profile.yaml  │
                              └──────────┬───────────┘
                                         │ jobbot profile rebuild
                                         ▼
 ┌──────────────┐  scrape   ┌─────────────────────────┐  ┌──────────────────┐
 │  Scrapers    │──────────▶│   Pipeline orchestrator │─▶│ SQLite (canonical│
 │  7 sources   │◀──enrich──│   - dedup               │  │ store of all     │
 └──────────────┘           │   - score (Haiku)       │  │ postings)        │
                            │   - generate (Sonnet)   │  └──────────────────┘
                            │   - apply (email/form)  │
                            │   - inbox scan          │
                            └────────────┬────────────┘
                                         │
                ┌────────────────────────┼────────────────────────┐
                ▼                        ▼                        ▼
       ┌──────────────┐         ┌──────────────┐          ┌─────────────────┐
       │ output/      │         │ Email out    │          │ Daily digest    │
       │ cv+cl per job│         │(SMTP truenorth)         │ + dashboard view│
       └──────────────┘         └──────────────┘          └─────────────────┘
```

Three scheduled jobs, all via launchd:

| Job | Cadence | Purpose |
|---|---|---|
| `jobbot.scrape` | every 4h, 08–20 | scrape → enrich → score → generate → queue |
| `jobbot.apply` | daily 09:00 | submit yesterday's queue, capped at 8 |
| `jobbot.digest` | daily 08:30 | render & send the morning email |
| `jobbot.inbox` | daily 09:30 | advance proof levels via IMAP |

---

## 10. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn restricts the guest endpoint | Medium | Loss of P0 source | Cookie path already wired; fallback to manual review of LinkedIn URLs |
| Recruiters notice the same name across sources within minutes | High | Reputation hit | 8/day cap, batched 09:00 send, conservative cover-letter voice |
| WeasyPrint dependency breaks (libpango etc.) | Medium | No PDF, no upload | Detect at startup; degrade to no-attachment with warning in digest |
| LLM scorer drift / variance | Medium | Mediocre rankings | Equal weights v1, retune weekly with real signal; full breakdown stored for audit |
| `truenorth.berlin` SMTP misconfigured | Medium | All applications fail at L1 | Detected at first send; fallback failure email via Gmail |
| Anthropic API outage | Low | No new scoring/generation | Postings remain queued; backfill on next run |
| User's distilled profile has hallucinated capabilities | Medium | Cover letters claim things he can't do | `jobbot profile rebuild` shows diff; user reviews before activating |

---

## 11. Open questions / explicit defaults

These are decided for v1 and locked in. If real operation reveals a problem, they're tunable in config.

| ID | Question | v1 decision | When to revisit |
|---|---|---|---|
| OQ-1 | Digest layout for no-body rows | single faded table | if email > 100 lines feels overwhelming |
| OQ-2 | Instant high-score alerts | no, daily digest only | if a strong match shows up at 09:00 and the user wants it before next morning |
| OQ-3 | Daily application cap | 8/day | adjust based on observed reply rate |
| OQ-4 | Apply timing | 09:00 batched | if recruiters seem to notice batching |
| OQ-5 | Scoring axes | 6 (role/domain/seniority/mode/language/comp) | add `tech_stack_match` if relevant for engineering pivots |
| OQ-6 | Axis weights | equal | retune after week 1 from real data |
| OQ-7 | Auto-snooze on rejection | 6 months | shorten if good companies have many roles |
| OQ-8 | Apply retry policy | no retry | if observed failure rate is high and re-attempts succeed |

---

## 12. Out of scope (v1)

- LinkedIn Easy Apply automation (security/ToS, low ROI)
- Indeed scraping past basic RSS attempt
- Multi-user support
- Web UI for non-local consumers
- DOCX output
- Any irreversible financial or transactional action
- Automatic profile rebuild (always user-triggered)
- SMS-based OTP retrieval (only IMAP-delivered OTPs)

---

## 13. Roadmap and acceptance

### Milestone 0 — Foundations (already done in scaffold)
- Repo scaffold, models, SQLite schema, scraper interfaces, Gmail SMTP test, LinkedIn / Stepstone / Xing / WWR working scrapers.

### Milestone 1 — Profile + DB + Enrichment
- `jobbot profile rebuild` reads corpus, writes `profile.compiled.yaml`.
- `seen_jobs` schema extended with all enrichment columns.
- `fetch_detail` implemented for LinkedIn (done), StepStone, Xing, WWR.
- `jobbot run` enriches every new posting before scoring.
- **Acceptance:** for ≥ 80% of postings from each enabled source, `description_scraped = TRUE`; `description_word_count > 200`.

### Milestone 2 — Scoring + Digest
- Six-axis scorer wired to compiled profile.
- Digest template with funnel snapshot + per-source stats + scored table.
- Apply threshold = 70.
- **Acceptance:** one real run produces a digest containing all enriched postings sorted by score, with axis breakdown clickthrough.

### Milestone 3 — Generate + Apply
- CV + CL generated per ≥70 posting, output as md/html/pdf.
- Email channel implemented end-to-end via `hilbert@truenorth.berlin`.
- Greenhouse + Lever form adapters complete with PDF upload.
- 8/day cap and 09:00 batched send wired.
- **Acceptance:** at least one real application sent successfully via each channel; appears in digest at proof L1.

### Milestone 4 — Outcome tracking
- IMAP scanner, proof-ladder advancement, snooze table.
- **Acceptance:** sent applications reach L2 within 24h of acceptance; replies advance to L3 within 1 daily inbox-scan cycle.

### Milestone 5 — Polish
- Local dashboard.
- Weight retuning UX.
- README + runbook.

---

## 14. Credentials checklist (collected during build, not before)

| Credential | Required for | Provided by user when implementer asks |
|---|---|---|
| `ANTHROPIC_API_KEY` | scoring + generation | yes |
| `LINKEDIN_LI_AT` (optional) | richer LinkedIn results | optional |
| `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | digest email + fallback | already in .env |
| `TRUENORTH_SMTP_HOST`, `_PORT`, `_USER`, `_PASS` | outbound applications | provided in-flight |
| `TRUENORTH_IMAP_HOST`, `_PORT` | proof tracking (bounce + reply) | provided in-flight |
| `CAPTCHA_API_KEY` | only if a form throws CAPTCHA | optional |

---

## 15. Glossary

- **Posting / profile** — a single job opening, persisted as one row in `seen_jobs`.
- **Body / description** — the full job-description text from the detail page (not the listing-card snippet).
- **Compiled profile** — the LLM-distilled normalized capabilities document, written to `profile.compiled.yaml`.
- **Proof level** — integer 0–5 representing the strongest evidence we have that the application succeeded (L0 = no evidence, L4 = interview invitation, L5 = explicit rejection).
- **Snooze** — temporary skip of a company after a rejection, to avoid re-applying.
- **Primary CV** — the single CV file in the corpus marked `PRIMARY_*` (currently `Philipp_Hilbert_opus_CV.pdf`). The distiller treats it as the source of truth for facts; other CVs and cover letters contribute only voice and phrasing signal.
- **Master memo** — the user's personal website at true-north.berlin, treated as an elaborated narrative version of the primary CV. Static; refreshed only via explicit `jobbot profile fetch-website`.

---

*End of PRD.*
