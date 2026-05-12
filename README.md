# job-bot

A personal automated job-search pipeline. It scrapes 10+ job boards, scores each posting against your CV with Claude, generates a tailored **application package** (opus-style PDF with cover letter + CV) for the strong matches, and optionally sends it from your own SMTP mailbox. A local dashboard at `http://localhost:5001` lets you triage everything in your browser.

Built for one person to run on their own laptop. **Nothing leaves your machine** except the Anthropic API call, the Gmail digest, and (when you flip the safety switch) the outbound application emails.

The shipped configuration searches for Product Owner / Product Manager roles on German boards. **You can retarget it for any profession** — cook, copywriter, data engineer, paramedic — by editing the queries, profile, and a handful of role-specific spots in the prompts. See [Adapting to your profession](#adapting-to-your-profession) below.

```text
scrape → enrich (full body) → heuristic filter → LLM score
                                                    ↓
                                         tailored CV + cover letter
                                                    ↓
                                         tailored rescore
                                                    ↓
                          digest email + dashboard + (optional) auto-apply
```

---

## What you'll need before starting

| Thing | Why | How to get it |
| --- | --- | --- |
| **macOS or Linux** | The launchd schedule assumes macOS; everything else works on Linux too | — |
| **Python 3.11 or 3.12** | The codebase | macOS: `brew install python@3.12` · Linux: `sudo apt install python3.12 python3.12-venv` |
| **Anthropic API key** | Scoring + tailoring use Claude Sonnet | Sign up at <https://console.anthropic.com>, create a key under Settings → Keys. Expect ~€5–€20/month at moderate volume. |
| **Gmail address + App Password** | Sends the daily digest to yourself (NOT for outbound applications) | Enable 2FA on your Gmail account, then generate an App Password at <https://myaccount.google.com/apppasswords> |
| **(Optional) Business SMTP mailbox** | Sends outbound applications from a professional address (e.g. IONOS, Fastmail, Zoho) | Any provider works. You'll paste host / port / user / password into `.env`. Until you do, applications stay in dry-run mode and just write `.eml` files to disk. |
| **(Optional) WeasyPrint native libs** | Renders the application-package PDF | macOS: `brew install weasyprint` · Linux: see <https://doc.courtbouillon.org/weasyprint/stable/first_steps.html> |

You do **not** need a CAPTCHA solver, an IMAP server, or anything else to get started — those become relevant only if you turn on auto-apply with web forms or inbox-scanning later.

---

## Quick start (10 minutes)

```bash
git clone <your fork URL> job-bot
cd job-bot
./scripts/setup.sh                # creates .venv, installs deps, Playwright Chromium
source .venv/bin/activate
jobbot init                       # interactive wizard — asks who you are, what jobs, what salary
```

`jobbot init` walks you through a focused Q&A — name, email, target role(s) in YOUR words ("Sous Chef", "Senior Data Engineer", "Paramedic"), salary range, deal-breaker industries, language profile — and writes four config files:

| File (gitignored) | What it holds |
| --- | --- |
| `.env` | API keys + SMTP placeholders |
| `data/profile.yaml` | Your structured profile + preferences |
| `data/config.yaml` | Per-portal search queries seeded from your target roles |
| `data/base_cv.md` | A stub CV you replace with your own content |

The wizard is non-destructive — if any of those files already exists, it asks before overwriting.

Two manual edits remain before the first run:

1. **`.env`**: paste your real `ANTHROPIC_API_KEY` (starts with `sk-ant-`, get it at <https://console.anthropic.com/settings/keys>) and your Gmail App Password (`GMAIL_APP_PASSWORD`, generate at <https://myaccount.google.com/apppasswords>).
2. **`data/base_cv.md`**: replace the stub content with your real CV. Plain Markdown, 1–3 pages.

Then:

```bash
pytest -q -m "not live"     # confirm tests pass
jobbot run                  # first end-to-end pass — scrape, score, generate
jobbot dashboard            # http://localhost:5001
```

Your first `jobbot run` typically takes 5–15 minutes (scraping 10+ boards + scoring ~50 jobs with Sonnet). At the end you'll get an email summary in your Gmail inbox, plus a dashboard you can open.

> **Prefer to edit by hand?** `setup.sh` already copied the `.example.*` templates over for you — skip `jobbot init` and edit `.env`, `data/profile.yaml`, `data/config.yaml`, `data/base_cv.md` directly.

---

## What "success" looks like on the first run

When the first run is healthy:

- ✅ `jobbot status` shows hundreds of rows in `scraped` and a few in `scored` / `generated`.
- ✅ The dashboard's **Stage 1: Hits per Portal** has 4+ portals reporting positive counts.
- ✅ The dashboard's **Stage 2: PO/PM Shortlist** table is sorted by score, descending, with the top jobs visible.
- ✅ Your Gmail inbox has a digest email titled like `jobbot digest · 2026-05-12 · 47 new postings`.
- ✅ For any score ≥ 70 you can open `output/<date>/<job-folder>/application_package.pdf` and see an editorial CV + cover letter formatted like a real application.

If any of those don't happen, jump to [Troubleshooting](#troubleshooting).

---

## Personalising your install

### `.env` — API keys + SMTP

Open `.env` (created by `setup.sh`) and paste your secrets:

| Variable | Required? | Where to get it |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | **yes** | <https://console.anthropic.com/settings/keys> — starts with `sk-ant-` |
| `GMAIL_ADDRESS` | yes | The Gmail account that sends the digest to you |
| `GMAIL_APP_PASSWORD` | yes | <https://myaccount.google.com/apppasswords> — 16-char App Password, not your login password |
| `NOTIFY_TO` | yes | Where the digest gets sent (usually same as `GMAIL_ADDRESS`) |
| `TRUENORTH_SMTP_HOST/PORT/USER/PASS` | optional | Your business SMTP (e.g. `smtp.ionos.de` + port 587). Leave any blank and the apply channel stays in dry-run mode forever — safe default. |
| `IMAP_HOST/IMAP_PORT` | optional | For inbox-scan and OTP polling. Defaults to Gmail. |
| `CAPTCHA_API_KEY` | optional | Only if you turn on web-form auto-apply and hit CAPTCHAs. |

**Gmail tip:** your regular login won't work if 2FA is on. You need an App Password (16 characters, spaces are stripped automatically).

### `data/profile.yaml` — who you are

Edit the YAML to describe yourself. The fields that matter most:

- `personal.full_name`, `personal.email`, `personal.location` — appear in the application package contact line.
- `personal.links` — LinkedIn, GitHub, website, optional YouTube. **These appear at the TOP and BOTTOM of every tailored CV** as a trust band.
- `preferences.remote`, `preferences.on_site_ok`, `preferences.willing_to_relocate`, `preferences.desired_salary_eur` — fed to the scorer as hard preferences.
- `deal_breakers.keywords` / `industries` / `on_site_only` — scoring will floor any posting that violates these.
- `must_have_skills`, `nice_to_have_skills` — used by the heuristic filter to drop obvious non-matches before LLM scoring.
- `user_facts` — free-text statements the LLM treats as authoritative even if absent from the CV (e.g. *"Logistik Vertiefung im Master-Studium an der TU Berlin"*). Great for surfacing latent domain expertise.

### `data/base_cv.md` — your CV

Plain Markdown, 1–3 pages. The LLM uses this as the source of truth when tailoring per job. Keep the structure: H1 with your name, contact line below, then sections like `## Bearing`, `## Experience`, `## Skills`, `## Languages`.

The contact line in the H1 block is copied verbatim into every tailored CV — make sure the email there matches `personal.email` in your profile (a regression test in `tests/test_return_address_guarantee.py` catches drift).

### (Optional) Corpus-based profile distillation

For richer scoring, drop your CV variants under `data/corpus/cvs/` and let Sonnet distill a compiled profile:

```bash
mkdir -p data/corpus/cvs
# Drop one or more PDF/Markdown CVs in there. Prefix the canonical one with PRIMARY_
# e.g. PRIMARY_Your_Name_CV.pdf
jobbot profile rebuild         # writes data/profile.compiled.yaml
```

The compiled profile is merged with `data/profile.yaml` at runtime, with the YAML's hand-curated fields always winning over LLM-generated ones.

### `data/config.yaml` — search queries

Ships with German Product Owner / Product Manager queries on Stepstone, Xing, WeWorkRemotely, LinkedIn, etc. For different roles or geographies, edit `sources.<portal>.queries` — each portal accepts `q:` strings, some accept `category:` or `keywords: [...]`.

The dashboard's "PO/PM" filter lives in [src/jobbot/templates/index.html](src/jobbot/templates/index.html) as a regex named `PO_PM_RE`. Replace it with your own role regex if you're searching for something else (see next section).

---

## Adapting to your profession

The defaults in this repo are tuned for a Product Manager / Product Owner search. **If you're a cook, a copywriter, a data engineer, a paramedic — any role** — you'll need to retarget a few files. None of these changes are scary, but they do build on each other, so do them in order.

### What you'll change for any non-PM profession

| File | What to change | Cook example |
| --- | --- | --- |
| `data/profile.yaml` | `target_roles`, `must_have_skills`, `nice_to_have_skills`, `deal_breakers` | `target_roles: ["Koch", "Chef de Partie", "Sous Chef", "Küchenchef"]`, must-haves like `["Gastronomie", "à la carte", "HACCP"]` |
| `data/base_cv.md` | Your CV. Replace the example content entirely. | Stations worked, cuisine focus, Ausbildung, languages |
| `data/config.yaml` | `sources.<portal>.queries` — the search terms each board uses | `queries: [{q: "Koch m/w/d"}, {q: "Chef de Partie"}, {q: "Küchenchef"}]` per portal |
| `prompts/match_score.md` | Remove the PM/PO calibration block | Delete the bullets under `Calibration guidance:` that mention "Product-management fit", "B2B SaaS", "OMS/WMS/e-commerce", "PM/PO". Replace with calibration relevant to your field — for a cook: "Kitchen-station fit primarily about cuisine type, brigade size, shift pattern, and service style (à la carte vs banquet vs system gastronomy)." |
| `prompts/application_package.md` | Rewrite the `§ AI-native stack` and `§ Technical environment` sections | A cook doesn't have an AI-native stack. Replace with `§ Stations & service style` (line cook / saucier / pâtissier / banquet experience) and `§ Cuisine focus` (regional / dietary / certifications) |
| `src/jobbot/templates/index.html` | The `PO_PM_RE` regex that filters Stage 2 of the dashboard | Replace with a regex of your role titles (e.g. `koch\|chef\|cuisinier` separated by escaped pipes), then rename the regex in the two places it's used |

### What you can leave alone

Most of the codebase is profession-agnostic. The scrapers, the SMTP channel, the trust-anchor links, the "already applied" guard, the scheduling, the dashboard structure — all of it works for any role. What's PM-flavoured is **only the content the LLM is asked to produce** (prompts) and **the dashboard's role filter** (regex).

### Cook walkthrough (10 minutes)

```bash
# 1. Edit search queries
$EDITOR data/config.yaml
# Change every `queries: [{q: "product manager"}, ...]` block to your role:
#   queries:
#     - q: "Koch m/w/d"
#     - q: "Chef de Partie"
#     - q: "Sous Chef Berlin"

# 2. Edit your profile
$EDITOR data/profile.yaml
# target_roles, must_have_skills, deal_breakers — speak in YOUR vocabulary,
# not in PM jargon. The LLM scorer reads these.

# 3. Replace the CV
$EDITOR data/base_cv.md
# Delete the PM example. Paste your own CV in Markdown.

# 4. Defang the scoring prompt
$EDITOR prompts/match_score.md
# Delete the "Calibration guidance:" block (the bullets about PM fit,
# B2B SaaS, etc). Replace with one or two short bullets about what makes
# a strong kitchen role for you.

# 5. Rewrite the bespoke application-package sections
$EDITOR prompts/application_package.md
# Find the `## AI-native stack` and `## Technical environment` headings.
# Either delete them outright, or rename + repurpose them to something
# meaningful for your field.

# 6. Update the dashboard role filter
$EDITOR src/jobbot/templates/index.html
# Search for PO_PM_RE — there are two references. Replace the regex
# with one that matches your role titles.

# 7. Smoke test
pytest -q -m "not live"      # should still pass — code didn't change
jobbot run                   # first run with the new config
jobbot dashboard             # confirm Stage 2 shows kitchen jobs, not PM jobs
```

### How to know you got it right

After your first `jobbot run` with the new config:

- ✅ Stage 1 (Hits per Portal) shows hits on the boards you queried (Stepstone and Xing tend to have lots of cooking jobs in Germany).
- ✅ Stage 2 (PO/PM Shortlist → now your-role Shortlist) shows jobs in your field, sorted by score.
- ✅ The top-scored row's `application_package.pdf` reads like a real application for *your* profession, not a PM cover letter awkwardly bolted onto a kitchen CV.

If Stage 2 is empty or the LLM cover letter starts talking about "product strategy" for a sous-chef role, go back to steps 4 and 5 — the prompts are the brain.

### Cost note for prompt-heavy edits

Each rescore against an edited prompt is one Sonnet call per posting (~€0.01–0.05). Use `jobbot rescore --base --force --limit 20` first to validate the new prompt feels right on 20 rows before letting it loose on hundreds.

---

## Daily use

```bash
jobbot run                              # full pipeline pass
jobbot status                           # current counts per stage
jobbot dashboard                        # open the UI at http://localhost:5001
jobbot digest                           # re-send the last-24h digest email
jobbot db-status                        # SQLite writer-lock state + holders

jobbot enrich --backfill --limit 100    # re-fetch detail pages for shallow rows
jobbot rescore --base --limit 50        # rescore rows that newly pass the precondition
jobbot rescore --base --force --limit 200   # nuke all base scores and re-evaluate (run after evaluator changes)
jobbot rescore --backfill --limit 50    # rescore generated rows against their tailored CV + CL

jobbot mark-applied <job_id> --note "Applied via LinkedIn UI"   # lock a job out of future auto-apply
jobbot scan-inbox                       # check inbox for replies / bounces / rejections / interviews

jobbot sources                          # list registered scrapers
```

`jobbot --help` shows the full menu.

### The dashboard at a glance

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Outcome Funnel — Total · Suitable · Tailored · Applied · Interview   │
├─────────────────────────────────────────────────────────────────────┤
│ ▾ Stage 1: Hits per Portal   (per-portal counts + description %)    │
│ ▾ Stage 2: PO/PM Shortlist   (sortable; defaults to score-desc)     │
│ ▾ Stage 3: Tailored Shortlist (score ≥ 70, with sort dropdown)      │
│ ▾ Stage 4: Application Outcomes (Received / Waiting / Rejected ...) │
│ ▾ Recent Runs                 (run-detail page is live-updating)     │
└─────────────────────────────────────────────────────────────────────┘
```

- **Stage 2** opens with the highest-scoring jobs at the top. Click any column header to re-sort.
- **Stage 3** has a sort dropdown (Best score / Base / Tailored / Tailoring delta Δ / Title / Company / Portal).
- **Run detail** auto-refreshes every 5 s while a run is in flight, and exposes pause / resume / stop controls.
- **Export JSON** dumps the full scored set to `~/Downloads/jobs_export_<ts>.json` (never into the repo).

---

## Auto-apply — the safety story

Sending applications on your behalf is irreversible. The pipeline has **three independent safety rails**:

1. **`apply.dry_run: true`** in `data/config.yaml` is the global kill switch. When true, every application is rendered to `output/<date>/<job>/application.eml` and **no SMTP call is made**. This is the shipped default.
2. **Missing SMTP creds forces dry-run.** If any of `TRUENORTH_SMTP_HOST/USER/PASS` is empty in `.env`, the email channel falls back to dry-run regardless of the config flag, and the dashboard shows `needs_review_reason = smtp_creds_missing`.
3. **`apply.per_run_limit: 5`** caps how many real applications a single run can send. Increase only after you trust the output.

**Plus** a fourth implicit rail: the **"already applied" guard.** Every run consults the `applications` table BEFORE attempting a send. Any job with `submitted = 1` (bot OR manual mark) is skipped. Use `jobbot mark-applied <job_id> --note "..."` to lock out jobs you applied to outside the bot.

### Going live

When you're ready to actually send:

1. Paste `TRUENORTH_SMTP_HOST/PORT/USER/PASS` into `.env` (use a business mailbox — never reuse `GMAIL_APP_PASSWORD`, the PRD treats Gmail as digest-only).
2. Run a `jobbot run` while `dry_run: true`. Open one of the `output/<date>/<job>/application.eml` files in Mail.app or Thunderbird — confirm subject, body, attached `application_package.pdf` all look correct.
3. Flip `apply.dry_run: false` in `data/config.yaml`.
4. Next `jobbot run` will send up to `per_run_limit` real applications. Every sent `.eml` is preserved on disk for audit.

LinkedIn Easy Apply is **forbidden by their ToS** and the codebase refuses to automate it — leave `linkedin.auto_submit: false`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `jobbot: command not found` after `setup.sh` | venv not activated in current shell | `source .venv/bin/activate` |
| `KeyError: 'ANTHROPIC_API_KEY'` on `jobbot run` | `.env` not edited | Open `.env`, paste your key starting with `sk-ant-` |
| `Gmail authentication failed` / `Application-specific password required` | Using your login password instead of an App Password | Generate one at <https://myaccount.google.com/apppasswords>, paste it into `GMAIL_APP_PASSWORD` |
| `cannot load library 'libgobject-2.0-0'` on PDF render | WeasyPrint native deps missing | macOS: `brew install weasyprint` · Linux: see [WeasyPrint install guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) — the pipeline still works without PDFs (HTML is always written) |
| `playwright._impl._errors.Error: Executable doesn't exist` | Chromium not installed | `playwright install chromium` |
| Stage 1 shows 0 hits for every portal | Network blocked / portal selectors broke | Run `jobbot run` and check `logs/run.out.log`; some portals (e.g. `remote.co`) are TLS-fingerprint-blocked and are intentionally off |
| `pytest` is suddenly slow + flaky | The live acceptance test is enabled by default | Use `pytest -q -m "not live"` to skip it during local iteration |
| Application emails not sending after flipping `dry_run: false` | One of `TRUENORTH_SMTP_*` is empty | The channel auto-falls-back to dry-run when creds are partial — check `.env` |
| Dashboard 404s | Wrong port / Flask not running | Make sure `jobbot dashboard` is running; URL is `http://localhost:5001` (HTTP not HTTPS) |
| `git status` shows `data/profile.yaml` modified | Personal data leaked into git tracking | Run `make check-secrets` — it fails if any gitignored pattern is tracked |
| `jobbot mark-applied <id>` says "no seen_jobs row found" | Wrong job_id | Query the DB: `sqlite3 data/jobbot.db "SELECT id, title FROM seen_jobs WHERE title LIKE '%hero%'"` |

If something else breaks: `logs/run.out.log` and `logs/run.err.log` carry structured JSON output you can pipe to `jq`.

---

## Scheduling (macOS launchd, optional)

Four LaunchAgents ship in [scheduling/](./scheduling/). Replace `REPO_PATH` with the absolute path to your checkout, then install:

```bash
REPO=$(pwd)
mkdir -p logs
for plist in scrape digest apply inbox; do
  sed "s|REPO_PATH|$REPO|g" "scheduling/com.philipp.jobbot.$plist.plist" \
    > ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist
  launchctl unload ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist 2>/dev/null
  launchctl load   ~/Library/LaunchAgents/com.philipp.jobbot.$plist.plist
done
launchctl list | grep jobbot
```

| Agent | When | Command |
| --- | --- | --- |
| `scrape` | 08:00 / 12:00 / 16:00 / 20:00 | `jobbot run` |
| `digest` | 08:30 daily | `jobbot digest` |
| `apply` | 09:00 daily | `jobbot apply` (batched send, respects `dry_run`) |
| `inbox` | 09:30 daily | `jobbot inbox-scan` (replies / bounces / interviews) |

To remove all: `launchctl unload ~/Library/LaunchAgents/com.philipp.jobbot.*.plist`.

> **Python path gotcha:** the plists must point at a real Python interpreter, not the macOS `/usr/bin/python3` shim (which silently fails under launchd). The setup script's `.venv/bin/python` is a stable choice.

---

## Secrets and personal data — what's gitignored and why

Everything you'd ever want to keep off GitHub:

| File / pattern | Why gitignored |
| --- | --- |
| `.env`, `.env.*` | API keys, SMTP password |
| `data/profile.yaml` / `data/profile.compiled.yaml` | Name, email, phone, salary range, deal-breakers |
| `data/base_cv.md` | Your CV |
| `data/general CV.pdf`, `data/general*.pdf` | PDF CV variants |
| `data/config.yaml` | Your search queries (reveals what jobs you want) |
| `data/corpus/` | Personal CV corpus + scraped portfolio |
| `data/jobbot.db*` | Local DB with scored postings |
| `output/`, `logs/`, `data/exports/`, `data/reports/` | Generated artifacts (CVs, cover letters, JSON dumps, debug renders) |

The `.example.*` siblings (`profile.example.yaml`, `base_cv.example.md`, `config.example.yaml`, `.env.example`) are templates — they're tracked, and `setup.sh` copies them to the gitignored real files.

Run `make check-secrets` (or `./scripts/check-secrets.sh`) anytime to verify nothing personal slipped into `git ls-files`. If a secret already leaked into history, scrub with [`git filter-repo`](https://github.com/newren/git-filter-repo) and **rotate the credential immediately** — history rewrites don't unleak data that already left your machine.

---

## Project layout

```text
job-bot/
├── README.md · PRD.md · PLAN.md · WORKFLOW.md · CLAUDE.md · MILESTONES.md
├── pyproject.toml                   # deps + jobbot CLI entry point
├── Makefile                         # make test / check-secrets / dashboard
├── .env.example                     # template for secrets
├── data/
│   ├── profile.example.yaml         # template — copy to data/profile.yaml
│   ├── base_cv.example.md           # template — copy to data/base_cv.md
│   ├── config.example.yaml          # template — copy to data/config.yaml
│   └── corpus/                      # personal CV corpus (gitignored)
├── prompts/
│   ├── application_package.md       # unified Sonnet prompt for the opus-style PDF
│   ├── match_score.md               # Sonnet scoring rubric
│   ├── cv_tailor.md / cover_letter.md  # legacy separate-doc prompts
│   └── screener.md                  # single-application screener
├── scheduling/                      # *.plist LaunchAgent templates
├── scripts/
│   ├── setup.sh                     # one-shot installer (you ran this already)
│   ├── check-secrets.sh             # fail if personal data is tracked
│   └── smoke_test_score_floor.py    # non-destructive scoring smoke test
├── src/jobbot/
│   ├── cli.py                       # `jobbot <cmd>` entrypoint
│   ├── pipeline.py                  # orchestrator
│   ├── scoring.py / models.py
│   ├── state.py                     # SQLite schema + helpers (incl. apply_channel)
│   ├── dashboard.py + dashboard/
│   ├── scrapers/ · enrichment/ · generators/ · applier/
│   ├── notify/ · otp/ · captcha/
│   └── outcomes/                    # inbox-scan + proof ladder
└── tests/                           # pytest suite (run with `pytest -q -m "not live"`)
```

---

## Workflow lifecycle

```text
scraped → filtered                 (heuristic deal-breaker)
        → below_threshold          (LLM score < generate_docs_above_score)
        → scored                   (CV + CL would be tailored but threshold not met)
        → generated                (application_package.pdf written; rescore applied)
            → apply_queued
                → apply_submitted  (sent — bot OR manual mark)
                → apply_needs_review
                → apply_failed     (SMTP / captcha / form error)
```

`jobbot status` prints counts per stage.

---

## Sources

| Portal | Implementation | State |
| --- | --- | --- |
| weworkremotely | RSS per category | ✅ |
| working_nomads | public JSON API | ✅ |
| nodesk | RSS + detail HTML | ✅ |
| dailyremote | JSON-LD on listing + per-job detail | ✅ |
| freelancermap | RSS | ✅ |
| stepstone | HTML + selectolax | ✅ |
| xing | Playwright | ✅ |
| linkedin | Playwright (read-only; never auto-apply per ToS) | ✅ |
| indeed | Playwright | 🟡 enabled per `data/config.yaml` |
| freelance_de | HTML | 🟡 disabled (robots.txt issue) |
| remote.co | n/a | ⛔ blocked by Cloudflare TLS fingerprinting |

`jobbot sources` prints the live registry.

---

## Workflow / branching

See [WORKFLOW.md](./WORKFLOW.md). Short version: never commit on `main`; every change starts from a fresh `main`, branches into `feat-/fix-/chore-/config-/docs-/refactor-…`, tests must be green before push, integration is via GitHub PR merge.

---

## Notes & risks

- **Scraping ToS.** Most boards prohibit automated access. Personal use, low volume; risk is on you. LinkedIn is the most aggressive — keep its rate low and never automate Easy Apply.
- **Auto-apply.** Recruiters can usually tell when an application is templated. This pipeline is best for high-volume pre-screening on aggregator boards, not for relationship-driven roles.
- **LLM cost.** ~€5–€20/month at moderate volume. Cap with `max_jobs_per_run` in `data/config.yaml`.
- **CAPTCHA solver.** Paid third-party; legal grey area in some jurisdictions. Disabled unless `CAPTCHA_API_KEY` is set.
- **PDF rendering.** WeasyPrint needs native libs (Pango, Cairo). Without them, HTML is still generated and the pipeline falls back gracefully — but the polished `application_package.pdf` won't render. Install via `brew install weasyprint` on macOS.
