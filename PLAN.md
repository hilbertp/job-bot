# Job-Bot — Plan & Architecture

Automated pipeline that (1) scrapes job postings from a configured list of boards, (2) scores them against your profile, (3) uses Claude to tailor a CV and write a cover letter for matches, and (4) emails you the results — successes and failures — from your Gmail account. Runs locally on macOS via `launchd`.

---

## 1. Goals & non-goals

**Goals (v1)**
- Pull fresh postings from: LinkedIn, Indeed, StepStone, Xing, weworkremotely, freelancermap.de, freelance.de.
- Maintain a deduped queue of jobs you have not seen yet.
- Score each job against your profile; only generate documents for matches above a threshold.
- Generate a tailored CV and cover letter as Markdown + HTML per match.
- **Auto-apply on web forms** for matched jobs that have an external application URL — fill standard fields from `profile.yaml`, attach the generated CV+CL, handle multi-step flows.
- **OTP retrieval** — when an application form requires an email verification code, poll your inbox over IMAP and inject the code automatically.
- **Captcha solving** — delegate reCAPTCHA v2/v3, hCaptcha, and image captchas to a third-party solver (2Captcha or CapSolver) via API key.
- Email you a daily digest with successes (with attached/inlined docs, the job link, and apply status), a queue of jobs needing manual review, and a failure summary.
- All credentials in `.env`, never in code.
- **Default to dry-run mode**: every application is prepared and screenshotted but only submitted when `auto_submit: true` is set per source — prevents accidental spam during development.

**Non-goals (v1)**
- LinkedIn Easy Apply auto-submission (against ToS — too risky; v1 only assists, doesn't submit on LinkedIn).
- DOCX / PDF output (can be added later via Pandoc).
- A web UI — CLI + cron only.
- Multi-user; this is a single-tenant tool for you.

**Important caveats on auto-apply**
- Auto-submitting applications can violate site ToS (LinkedIn explicitly forbids it). The auto-applier is opt-in per source and ships disabled by default.
- Some employers reject obviously-templated applications; auto-apply is best for pre-screening high-volume boards (Indeed, StepStone), not relationship-driven roles.
- Captcha solver services are paid and not free of legal grey areas — included as a deliberate, configurable component, not on by default.

---

## 2. High-level architecture

```
                    ┌───────────────────────────┐
                    │   profile.yaml + base_cv  │
                    └─────────────┬─────────────┘
                                  │
 ┌──────────────┐    ┌────────────▼───────────┐    ┌────────────────┐
 │  Scrapers    │───▶│   Pipeline orchestrator │───▶│  State (SQLite)│
 │  (6 sources) │    │   - dedup               │    │  seen jobs +   │
 └──────────────┘    │   - score               │    │  apps + runs   │
                     │   - generate docs       │    └────────────────┘
                     │   - auto-apply (opt-in) │
                     │   - notify              │
                     └────────────┬────────────┘
                                  │
   ┌──────────────────────────────┼──────────────────────────────────┐
   ▼              ▼               ▼               ▼                  ▼
┌────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Claude  │ │Output files│ │  Auto-apply  │ │ OTP fetcher  │ │ Captcha API  │
│(LLM)   │ │ md + html  │ │ (Playwright) │ │   (IMAP)     │ │(2Captcha etc)│
└────────┘ └────────────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                                 └────────────────┴────────────────┘
                                                  │
                                          ┌───────▼────────┐
                                          │  Gmail SMTP    │
                                          │ (digest email) │
                                          └────────────────┘
```

Run cadence: a single `python -m jobbot run` invocation does one full cycle. `launchd` triggers it on a schedule (e.g. every 4 h between 08:00–20:00).

---

## 3. Components

### 3.1 Profile loader (`src/jobbot/profile/`)
- Reads `data/profile.yaml` (skills, experience summary, languages, locations, salary expectations, must-haves, deal-breakers).
- Reads `data/base_cv.md` — your canonical CV in Markdown (you provide).
- Exposes a typed `Profile` object to the rest of the pipeline.

### 3.2 Scrapers (`src/jobbot/scrapers/`)
Each scraper implements:
```python
class BaseScraper(Protocol):
    source: str            # "linkedin", "indeed", ...
    def fetch(self, query: SearchQuery) -> list[JobPosting]: ...
```
A `JobPosting` is a small dataclass: `id`, `source`, `title`, `company`, `location`, `url`, `posted_at`, `description`, `raw` (full text for the LLM), `tags` (remote / contract / etc.).

**Per-source approach (see §6 for details)**
| Source | Approach | Anti-bot risk |
|---|---|---|
| LinkedIn | Public Jobs guest endpoint (HTML) — fragile; long-term: official Jobs API | High |
| Indeed | RSS feeds where available + HTML fallback via Playwright | Medium |
| StepStone | Public listing pages with Playwright | Medium |
| Xing | Public jobs.xing.com search pages | Medium |
| weworkremotely | RSS feeds (officially supported) | Low |
| freelancermap.de | RSS feeds (officially supported) | Low |
| freelance.de | HTML scrape with `requests` + `bs4` | Low–Medium |

The pipeline treats each scraper as fallible and isolated — one source dying never fails the whole run.

### 3.3 Match scorer (`src/jobbot/scoring.py`)
Two-stage to keep LLM cost down:
1. **Cheap heuristic**: keyword overlap between profile must-haves/skills and the job description; hard filters for deal-breakers (e.g. on-site only when you want remote, wrong language, wrong seniority).
2. **LLM scoring (Claude Haiku)**: for jobs that pass the heuristic, ask the model for a 0–100 fit score with a one-line reason. Only jobs above the configured threshold (default 70) trigger document generation.

### 3.4 Generator (`src/jobbot/generators/`)
- `cv_tailor.py` — sends `base_cv.md` + job description + profile to Claude (Sonnet) with a prompt that re-orders/rewords bullets to match the role, never invents experience.
- `cover_letter.py` — generates a fresh cover letter in Markdown.
- Both write `output/<date>/<source>__<slug>/cv.md`, `cv.html`, `cover_letter.md`, `cover_letter.html`. HTML is a single self-contained file with embedded CSS for nice rendering and easy printing.

### 3.5 State store (`src/jobbot/state/`)
SQLite at `data/jobbot.db` with two tables:
- `seen_jobs(id, source, url, first_seen_at, score, generated, generated_at)` — the dedup index.
- `runs(id, started_at, finished_at, n_fetched, n_new, n_generated, n_errors, summary_json)`.

### 3.6 Notifier (`src/jobbot/notify/email.py`)
- Gmail SMTP (`smtp.gmail.com:587`, STARTTLS) using your address + a Google **App Password**.
- Two email types: **success digest** (one per run if there are any matches) listing each match with company, title, link, score, reason, and the cover letter inlined as HTML; **failure alert** (only if the run had errors) listing sources that failed and any generation exceptions.

### 3.7 Auto-applier (`src/jobbot/applier/`)
Playwright-driven webform agent. For each matched job whose source has `auto_submit: true`:
1. Navigate to the apply URL.
2. Detect the form type with a small library of **adapters**: `greenhouse.py`, `lever.py`, `workday.py`, `smartrecruiters.py`, `personio.py`, `generic.py` (heuristic fallback). ATSes share form structure, so a per-ATS adapter covers many employers.
3. Fill standard fields from `profile.yaml`: name, email, phone, location, LinkedIn URL, work auth, salary expectation, notice period, etc.
4. Upload the generated `cv.pdf` (we render Markdown→PDF on the fly with WeasyPrint just for the upload — no PDF in the long-term doc store) and `cover_letter.pdf`.
5. Answer free-text screener questions by sending them to Claude with the profile + job description as context. Confidence < 0.8 → mark for manual review, don't submit.
6. If a captcha appears → call `captcha_solver.solve(...)`. If a verification email arrives → call `otp_fetcher.wait_for_code(...)`.
7. **Dry-run by default**: take a full-page screenshot of the filled-in form, save to `output/<date>/<job>/apply_preview.png`, exit *without* clicking submit. When `auto_submit: true` and `confirm_each: false`, click submit and screenshot the confirmation page.
8. Record outcome in `applications` table: `submitted`, `dry_run`, `needs_review`, `failed_captcha`, `failed_otp`, `failed_form`.

### 3.8 OTP fetcher (`src/jobbot/otp/imap.py`)
- Connects over IMAP TLS to your Gmail (uses the same app password as SMTP, with IMAP enabled).
- `wait_for_code(sender_domain: str, timeout_s: int = 120) -> str | None`:
  - Polls every 5s up to the timeout.
  - Filters by sender domain (e.g. only look at mail from `noreply@workday.com` if applying via Workday).
  - Extracts a 4–8 digit code with regex (`\b\d{4,8}\b`) from the most recent matching unread message.
  - Marks the message as read so it isn't re-used.
- SMS-based OTP is **not** supported in v1 — would need a Twilio number; documented as a future option.

### 3.9 Captcha solver (`src/jobbot/captcha/`)
- Pluggable interface so we can swap providers:
  ```python
  class CaptchaSolver(Protocol):
      def solve_recaptcha_v2(self, site_key: str, url: str) -> str: ...
      def solve_recaptcha_v3(self, site_key: str, url: str, action: str) -> str: ...
      def solve_hcaptcha(self, site_key: str, url: str) -> str: ...
      def solve_image(self, png_bytes: bytes) -> str: ...
  ```
- Default implementation: **2Captcha** (`solvers/twocaptcha.py`) — reasonable price (~$2.99 / 1000 reCAPTCHAs), simple HTTP API. CapSolver adapter as alternative.
- Solver returns a token; the auto-applier injects it into the page (`g-recaptcha-response` textarea) and proceeds.
- If solver returns no token within the timeout (default 90s), the application is moved to `needs_review`.

### 3.10 Pipeline orchestrator (`src/jobbot/pipeline.py`)
The single entrypoint glue — wraps each step in try/except so partial failures still produce a useful email.

---

## 4. Data flow per run

1. Load profile + search queries from config.
2. For each scraper, fetch postings with timeout + retries → collect into one list, tag errors.
3. Filter against `seen_jobs`; insert new ones with `score=NULL`.
4. Heuristic prefilter → drop deal-breakers.
5. LLM score remaining → store score on row.
6. For jobs with `score >= threshold`: generate CV + cover letter, mark `generated=1`.
7. Build digest email; send via Gmail SMTP.
8. Write run summary into `runs` table.

---

## 5. Tech stack & dependencies

- **Python 3.11+** with a venv.
- `httpx` — HTTP client (sync; async optional later).
- `beautifulsoup4`, `selectolax` — HTML parsing.
- `feedparser` — RSS.
- `playwright` — headless browser fallback (LinkedIn, StepStone, Xing).
- `anthropic` — Claude SDK.
- `pydantic` — typed config + data models.
- `pyyaml` — profile/config files.
- `jinja2` — HTML rendering for the digest email and CV/CL templates.
- `tenacity` — retries with backoff.
- `python-dotenv` — load `.env`.
- `rich` / `structlog` — logging.
- `pytest`, `responses`/`respx` — tests.

No DOCX/PDF deps in v1 (output is Markdown + HTML).

---

## 6. Per-source notes

**LinkedIn.** No free official scraping API. The `linkedin.com/jobs/search` guest endpoint returns paginated HTML cards and works without login but may rate-limit your IP and break without notice. Plan: start there with a polite request rate (≥ 2s between calls, randomized UA), keep the parser small and easy to fix. If it gets blocked, switch to the [official LinkedIn Jobs API](https://learn.microsoft.com/en-us/linkedin/talent/job-postings) (requires partnership) or a paid relay (Proxycurl etc.) — out of scope for v1.

**Indeed.** Some country sites still expose RSS at `/rss?q=...&l=...`; check per-region. If RSS is gone for your queries, use Playwright on the search page; Indeed aggressively blocks plain `requests`.

**StepStone & Xing.** DACH-focused; both render server-side enough to scrape. Use Playwright for JS-heavy sections; throttle hard.

**weworkremotely.** Has clean per-category RSS (`/categories/remote-programming-jobs.rss` etc.). Easiest source — start here for end-to-end testing.

**freelancermap.de.** Offers RSS for searches: `/job_rss.php?...`. Reliable.

**freelance.de.** No public RSS. Plain HTML scrape is fine; respect robots.txt and add a delay.

**General etiquette**
- Identify with a real User-Agent string + your contact email.
- Cache aggressively (SQLite); never refetch the same posting.
- Random jitter between calls; cap concurrency at 1 per source.
- If a source 4xx/5xx’s repeatedly, back off for the rest of the run and report it in the failure email.

---

## 7. LLM prompting design

- **Match scoring** — Haiku, structured JSON output: `{score: int, reason: str}`. Cheap, fast.
- **CV tailoring** — Sonnet. System prompt enforces: never fabricate, only re-rank/rephrase existing bullets, keep section structure, output Markdown only. Job description + profile summary + `base_cv.md` go in the user message.
- **Cover letter** — Sonnet. System prompt sets tone (professional but warm, concise — max 250 words), forbids generic filler, requires a hook tied to the company.

All prompts live in `prompts/*.md` so you can iterate without editing code.

---

## 8. Configuration

- `.env` — API keys, SMTP creds (`ANTHROPIC_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFY_TO`).
- `data/config.yaml` — search queries per source, score threshold, cadence, output directory.
- `data/profile.yaml` — your structured profile.
- `data/base_cv.md` — canonical CV (you provide).

---

## 9. Scheduling on macOS

Two scheduled jobs, both managed via `launchd` LaunchAgents (preferred over cron because they survive reboots and play nicely with sleep):

| Job | Schedule | What it does |
|---|---|---|
| `com.philipp.jobbot.scrape` | Every 4 h, 08:00–20:00 | Run scrapers + score + generate docs. Writes new matches to the queue. |
| `com.philipp.jobbot.digest` | Daily, 08:30 | Send the daily digest email listing all suitable postings from the last 24 h, with links and per-job apply status. |
| `com.philipp.jobbot.apply` | Daily, 09:00 *(optional, off by default)* | Run the auto-applier over yesterday's queue for sources where `auto_submit: true`. |

A plain `cron` line is also supported for users who prefer it; the README ships both.

The daily digest is the user-facing artifact: one email per day, in your inbox, with everything it found and what it did. Scraper runs throughout the day silently fill the queue; the digest summarizes them.

---

## 10. Failure modes & mitigations

| Failure | Handling |
|---|---|
| One scraper crashes | Caught per-source; logged; included in failure email. Other sources continue. |
| LLM call fails | `tenacity` retry (3x, exp backoff); on final failure mark job `generated=0` and continue. |
| Gmail SMTP rejects | Log + write failure to disk; next run will retry (state in SQLite is intact). |
| Captcha / IP block | Source disabled for the rest of the run; failure email surfaces it. |
| Output disk full | Pre-flight check at run start; fail fast with email. |

---

## 11. Cost estimate

Assuming ~30 new postings/day across all sources, ~10 pass the heuristic, ~5 score above threshold:
- 30 × Haiku score (~500 in / 50 out tokens) ≈ $0.01/day.
- 5 × Sonnet CV+CL (~3k in / 1k out tokens each, twice) ≈ $0.15/day.
- ≈ **$5/month** in Claude API costs at this volume. Gmail SMTP is free.

---

## 12. Milestones

1. **M1 — Scaffold** (this session): folders, deps, stubs, README, plan ✅
2. **M2 — One source end-to-end**: weworkremotely RSS → SQLite → Haiku score → Sonnet generate → Gmail digest. Validates the whole chain.
3. **M3 — Add reliable sources**: freelancermap, Indeed RSS, freelance.de.
4. **M4 — Playwright sources**: StepStone, Xing.
5. **M5 — LinkedIn**: most fragile, last.
6. **M6 — Polish**: launchd plist, prompt tuning on real outputs, cost dashboard, failure-email design pass.

---

## 13. Workflow visualization

Each job posting moves through a fixed lifecycle, tracked in the `seen_jobs` and `applications` SQLite tables. The CLI command `jobbot status` prints a snapshot of how many jobs are in each stage, and the daily digest email embeds the same view as a small HTML graphic. See the rendered diagram alongside this plan.

States: **Scraped → Scored → Docs Generated → In Application → Submitted (Success) | Needs Review | Failed**.

A job can also exit early as **Filtered** (didn't pass heuristic) or **Below Threshold** (LLM score too low) — these go straight to a terminal state without consuming generation budget.

## 14. Open questions to revisit after M2

- Threshold tuning: is 70 the right cutoff?
- Should the cover letter pull more from the company website (extra HTTP fetch + summary)?
- Add a "snooze company" list to skip employers you've already applied to or rejected?
- Extend to PDF/DOCX if a portal demands it.
