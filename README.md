# job-bot

Personal automated job-search pipeline. Scrapes 10+ boards, scores each posting against your profile with Claude, generates a tailored CV + cover letter for matches, optionally auto-applies on web forms, and emails you a daily digest. Comes with a local dashboard at `http://localhost:5001`.

Runs locally on macOS via `launchd`. See [PLAN.md](./PLAN.md) for the full architecture and [PRD.md](./PRD.md) for the spec.

## At a glance

```
scrape → enrich (full body) → heuristic filter → LLM score → tailored CV + CL
                                                                ↓
                                                       tailored rescore
                                                                ↓
                                            digest email + dashboard + (optional) auto-apply
```

---

## ⚠️ Secrets and personal data — read this first

This repo is **opinionated about what should never be committed**:

| File / pattern | Why it's gitignored |
| --- | --- |
| `.env`, `.env.*` | API keys, SMTP password |
| `data/profile.yaml` | Your name, email, phone, salary range, deal-breakers |
| `data/profile.compiled.yaml` | Generated profile distilled from your CV corpus |
| `data/base_cv.md` | Your canonical CV in Markdown |
| `data/general CV.pdf`, `data/general*.pdf` | PDF CV variants |
| `data/config.yaml` | Your search queries (reveals what jobs you want) |
| `data/corpus/cvs/`, `data/corpus/website/` | Personal CV corpus + scraped portfolio |
| `data/jobbot.db` and `-*` companions | Local DB with scored postings |
| `output/`, `logs/`, `data/exports/` | Generated artifacts (CVs, cover letters, JSON dumps) |

If you're forking, **do not unstage these**. The `.example.*` siblings (`profile.example.yaml`, `base_cv.example.md`, `config.example.yaml`, `.env.example`) are your templates — copy them and edit the copies.

A `make check-secrets` target is included; CI / pre-push should fail if anything matching the patterns above appears in `git ls-files`.

If you suspect a secret has already been committed in history, use [`git filter-repo`](https://github.com/newren/git-filter-repo) or the [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) to scrub it — **and rotate the credential immediately**, because rewriting history doesn't unleak data that already left your machine.

---

## 1. Setup (one-time)

### 1a. Clone and install

```bash
git clone <your fork URL> job-bot
cd job-bot

# Python 3.12 venv. (3.11 works too; check pyproject.toml for the floor.)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Playwright Chromium for Indeed / LinkedIn / any auto-apply
playwright install chromium
```

### 1b. API keys → `.env`

Required:

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Where to get it | Required? |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com/settings/keys> — create a key, paste `sk-ant-…` | **yes** — scoring + tailoring won't run without it |
| `GMAIL_ADDRESS` | The Gmail account that sends the digest | yes |
| `GMAIL_APP_PASSWORD` | <https://myaccount.google.com/apppasswords> (16-char app password, not your login password) | yes |
| `IMAP_HOST`, `IMAP_PORT` | `imap.gmail.com` / `993` for Gmail (defaults) | only if you enable auto-apply with OTP polling |
| `CAPTCHA_API_KEY` | 2Captcha or similar — paid third-party | only if you enable auto-apply and listings hit captchas |

**Gmail-specific**: the regular account password won't work with 2FA on. Create an app password:
1. Visit https://myaccount.google.com/apppasswords
2. Make one named `jobbot`
3. Paste it into `.env` as `GMAIL_APP_PASSWORD` (spaces are stripped automatically)
4. Enable IMAP in Gmail → Forwarding and POP/IMAP → IMAP access: Enable

### 1c. Profile, CV, search config

```bash
cp data/profile.example.yaml data/profile.yaml
cp data/base_cv.example.md   data/base_cv.md
cp data/config.example.yaml  data/config.yaml
```

Then edit:

- **`data/profile.yaml`** — your structured profile. `personal` (name/email/phone), `preferences` (remote, on_site_ok, willing_to_relocate, desired_salary_eur), `deal_breakers` (keywords, industries, `on_site_only`), `must_have_skills`, `nice_to_have_skills`, `target_roles`, `screener_defaults` (canned answers used by the auto-applier).
- **`data/base_cv.md`** — your canonical CV in Markdown. This is what the LLM scorer reads against each posting; tailoring uses it as the source of truth too. Keep it 1–3 pages of plain Markdown. PDF is generated from this on demand (WeasyPrint).
- **`data/config.yaml`** — search queries per portal, score thresholds, digest behaviour, auto-apply flags.

For corpus-based profile distillation (richer scoring, optional):

```bash
mkdir -p data/corpus/cvs data/corpus/website
# Put 1+ PDF/Markdown CV variants under data/corpus/cvs/, prefix one with PRIMARY_
# (e.g. PRIMARY_Your_Name_CV.pdf — that one becomes the source-of-truth CV for scoring).
jobbot profile rebuild        # writes data/profile.compiled.yaml
```

### 1d. Verify

```bash
pytest -q                  # all green
jobbot sources             # lists 10 registered scrapers
jobbot status              # empty pipeline counts
```

If any of those fail, fix before continuing.

---

## 2. Daily use

```bash
jobbot run             # full pipeline pass — scrape, enrich, score, generate, optional apply, digest
jobbot digest          # re-send the digest of the last 24h (e.g. after a scrape with no auto-email)
jobbot status          # current pipeline counts per stage
jobbot db-status       # check SQLite writer lock + holders
jobbot dashboard       # local web dashboard at http://localhost:5001 (Ctrl-C to stop)
jobbot enrich --backfill --limit 100    # backfill bodies for rows with word_count < 200
jobbot rescore --backfill --limit 50    # rescore generated rows against their tailored CV + CL
```

### Dashboard

`jobbot dashboard` serves a read-only UI bound to `127.0.0.1:5001`:

- **Stage 1: Hits per Portal** — what each scraper produced in the latest run + a "Last run / Duration" badge in the header.
- **Stage 2: PO / PM Shortlist** — sortable table with score, title, portal, Apply via channel (📧 email / 🔗 ATS / 🌐 external / ✋ manual), description scraped (yes/no), expected salary, seniority.
- **Stage 3: Tailored Shortlist (score ≥ 70)** — high-fit jobs with their tailored CV + cover letter inlined. Each row shows base → tailored score with the delta.
- **Recent Runs** — link to the run-detail page, which goes live (auto-refresh every 5 s) while a run is in flight and shows a per-portal table + a "currently scraping/enriching/scoring/…" badge.
- **Export JSON** button — dumps the full scored set to `~/Downloads/jobs_export_<ts>.json` (not into the repo).

---

## 3. Scheduling (launchd)

Four LaunchAgents ship in [scheduling/](./scheduling/). Replace `REPO_PATH` with the absolute path to this checkout, then install:

```bash
REPO=$(pwd)
mkdir -p logs
for plist in scrape digest apply inbox; do
  sed "s|REPO_PATH|$REPO|g" "scheduling/com.philipp.jobbot.$plist.plist" \
    > ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist
  launchctl unload ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist 2>/dev/null
  launchctl load ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist
done

launchctl list | grep jobbot   # verify
```

Cadence (local time):

| Agent | When | Command |
| --- | --- | --- |
| `scrape` | 08:00 / 12:00 / 16:00 / 20:00 | `jobbot run` |
| `digest` | 08:30 daily | `jobbot digest` |
| `apply` | 09:00 daily (after digest) | `jobbot apply` (FR-APP-05 batch) |
| `inbox` | 09:30 daily | `jobbot inbox-scan` (OTP / confirmation polling) |

Logs go to `logs/{scrape,digest,apply,inbox}.{out,err}.log`.

To remove: `launchctl unload ~/Library/LaunchAgents/com.philipp.jobbot.*.plist`.

> **Note on Python path**: the plists must invoke a Python that resolves at runtime *without* `PATH`. Symlinks via `/usr/bin/python3` trigger macOS's xcode-select shim and silently fail under launchd. Point them at a direct interpreter (Homebrew's `.venv-1/bin/python` is one stable example).

---

## 4. Operating as a third party (you are not the original author)

If you fork this for your own job search:

1. **Read the secrets table above.** Don't accidentally commit your CV or `.env`.
2. **Run [scripts/setup.sh](./scripts/setup.sh)** if it exists, or follow §1 by hand.
3. **Adjust the search profile.** `data/config.yaml` ships with PO/PM queries on German boards (Stepstone, Xing, etc.). If you want different roles or geography:
   - Change `target_roles` in `profile.yaml`.
   - Edit per-source `queries` in `config.yaml`. Each portal accepts a `q:` string; some accept `category:` (WeWorkRemotely) or `keywords: [...]` (LinkedIn / freelance.de).
   - The PO/PM filter on the dashboard's Stage 2 lives in `src/jobbot/templates/index.html` as `PO_PM_RE` — replace with your own role regex if needed.
4. **Localise the prompts.** German job postings + German cover letters work today because `prompts/cover_letter.md` adapts to the posting's language. If you want a different default tone or language for the cover letter, edit `prompts/cover_letter.md` and `prompts/cv_tailor.md`.
5. **Sender identity.** `src/jobbot/notify/email.py` and `src/jobbot/applier/` reference `hilbert@truenorth.berlin` as the application sender. Replace with your address. The `pyproject.toml` and a few comments still carry the original author's email — search-and-replace if you care.
6. **Auto-apply is OPT-IN per source.** The `apply.dry_run: true` global in `config.yaml` prevents real submissions even when a source has `auto_submit: true`. Watch a few dry-runs (the runner screenshots filled forms) before flipping `dry_run: false`. LinkedIn auto-apply is **forbidden by their ToS** and the codebase refuses to automate it — leave it on `auto_submit: false`.
7. **Cost.** ~€5–€20/month at moderate volume (Sonnet + Haiku mix). `max_jobs_per_run` in `config.yaml` is the safety belt. The dashboard's "Total Jobs" stat is for sanity-checking what the scorer has seen.

---

## 5. Project layout

```
job-bot/
├── PRD.md, PLAN.md, WORKFLOW.md, CLAUDE.md, MILESTONES.md
├── README.md                        # this file
├── pyproject.toml                   # deps + scripts
├── .env.example                     # template for secrets
├── .gitignore                       # the secrets-and-personal-data list
├── data/
│   ├── profile.example.yaml         # template — copy to data/profile.yaml
│   ├── base_cv.example.md           # template — copy to data/base_cv.md
│   ├── config.example.yaml          # template — copy to data/config.yaml
│   └── corpus/                      # personal CV corpus (gitignored)
├── prompts/
│   ├── match_score.md               # Sonnet scoring rubric
│   ├── cv_tailor.md                 # CV tailoring
│   ├── cover_letter.md              # cover letter generator
│   └── screener.md                  # single application screener
├── scheduling/                      # *.plist LaunchAgent templates
├── src/jobbot/
│   ├── cli.py                       # `jobbot <cmd>` entrypoint
│   ├── config.py                    # .env + data/config.yaml loaders
│   ├── pipeline.py                  # orchestrator
│   ├── models.py                    # pydantic
│   ├── profile.py                   # profile + CV loaders
│   ├── scoring.py                   # base + tailored LLM scorer
│   ├── state.py                     # SQLite schema + helpers (incl. apply_channel)
│   ├── dashboard.py + dashboard/    # Flask dashboard
│   ├── templates/                   # Jinja templates for the dashboard
│   ├── scrapers/                    # one module per portal
│   ├── generators/                  # CV + cover letter via Claude
│   ├── applier/                     # Playwright apply flow + ATS adapters
│   ├── enrichment/                  # detail-page body fetch
│   ├── notify/                      # Gmail SMTP + digest template
│   ├── otp/                         # IMAP code retrieval
│   └── captcha/                     # 2Captcha solver
└── tests/                           # pytest suite
```

---

## 6. Workflow lifecycle (state machine)

```
scraped → filtered                 (heuristic deal-breaker)
        → below_threshold          (LLM score < generate_docs_above_score)
        → scored                   (CV + CL would be tailored but threshold not met)
        → generated                (CV + CL written; rescore applied)
            → apply_queued
                → apply_submitted  (success)
                → apply_needs_review
                → apply_failed     (captcha/OTP/form error)
```

`jobbot status` prints counts per stage. The dashboard's Stage 3 panel shows the latest scored rows including the tailored-rescore delta.

---

## 7. Sources

| Portal | Implementation | State |
| --- | --- | --- |
| weworkremotely | RSS per category | ✅ |
| working_nomads | public JSON API | ✅ |
| nodesk | RSS + detail HTML | ✅ |
| dailyremote | JSON-LD on listing + per-job detail | ✅ |
| freelancermap | RSS | ✅ |
| stepstone | HTML + selectolax | ✅ |
| xing | Playwright | ✅ |
| linkedin | Playwright (read-only; never auto-apply) | ✅ |
| indeed | Playwright | 🟡 enabled per `data/config.yaml` |
| freelance_de | HTML | 🟡 disabled (robots.txt issue) |
| remote.co | n/a | ⛔ blocked by Cloudflare TLS fingerprinting |

`jobbot sources` prints the live registry.

---

## 8. Workflow / branching

See [WORKFLOW.md](./WORKFLOW.md). Short version: never commit on `main`; every change starts with a fresh `main`, branches into `feat-/fix-/chore-/config-/docs-/refactor-…`, tests must be green before push, integration is via GitHub PR merge.

---

## 9. Notes & risks

- **Scraping ToS.** Most boards prohibit automated access in their terms. Personal use, low volume; risk is on you. LinkedIn is the most aggressive — keep its rate low and never automate Easy Apply.
- **Auto-apply.** Recruiters can usually tell when an application is templated. This pipeline is best for high-volume pre-screening on aggregator boards, not for relationship-driven roles.
- **LLM cost.** ~€5–€20/month at moderate volume. Cap with `max_jobs_per_run`.
- **Captcha solver.** Paid third-party; legal grey area in some jurisdictions. Disabled unless `CAPTCHA_API_KEY` is set.
- **Secret hygiene.** If you committed personal data to a fork's history before reading §0, treat the data as leaked and rotate any exposed keys. `git filter-repo` can scrub *future* clones; existing clones are forever.
