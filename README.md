# job-bot

Personal automated job-search pipeline. Scrapes 7 boards, scores each posting against your profile with Claude, generates a tailored CV + cover letter for matches, optionally auto-applies on web forms (with OTP retrieval and captcha solving), and emails you a daily digest.

Runs locally on macOS via `launchd`. See [PLAN.md](./PLAN.md) for the full architecture.

## Status: scaffold only

This repo is a stub. Modules, interfaces, and the daily flow are wired end-to-end but most scrapers and adapters need real selectors filled in. Validate one source at a time (start with `weworkremotely` — official RSS, no anti-bot to fight).

## Setup (one-time)

```bash
# 1. Python venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium      # for Playwright-based scrapers / auto-apply

# 2. Secrets
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, etc.

# 3. Profile + base CV
cp data/profile.example.yaml data/profile.yaml
cp data/base_cv.example.md   data/base_cv.md
cp data/config.example.yaml  data/config.yaml
# Edit all three with your real data.

# 4. Smoke test
pytest -q
jobbot sources                   # should list all 7 scrapers
jobbot status                    # should show empty pipeline
```

### Gmail App Password

The Gmail account needs an **App Password** (the regular password won't work with 2FA on):
1. Go to https://myaccount.google.com/apppasswords
2. Create one named "jobbot"
3. Paste it into `.env` as `GMAIL_APP_PASSWORD` (spaces are stripped automatically)
4. Make sure IMAP is enabled in Gmail settings → Forwarding and POP/IMAP

## Daily use

```bash
jobbot run        # full pipeline pass: scrape → score → generate → (apply) → digest email
jobbot digest     # send a digest of the last 24 h (use this if a scrape ran but no email went out)
jobbot status     # current pipeline counts per stage
```

## Scheduling (launchd)

Two LaunchAgents ship in `scheduling/`. Replace `REPO_PATH` with the absolute path to this checkout, then install:

```bash
# Replace placeholders
REPO=$(pwd)
mkdir -p logs
sed "s|REPO_PATH|$REPO|g" scheduling/com.philipp.jobbot.scrape.plist  > ~/Library/LaunchAgents/com.philipp.jobbot.scrape.plist
sed "s|REPO_PATH|$REPO|g" scheduling/com.philipp.jobbot.digest.plist  > ~/Library/LaunchAgents/com.philipp.jobbot.digest.plist

# Load
launchctl load ~/Library/LaunchAgents/com.philipp.jobbot.scrape.plist
launchctl load ~/Library/LaunchAgents/com.philipp.jobbot.digest.plist

# Verify
launchctl list | grep jobbot
```

The scrape job runs every 4 h between 08:00–20:00. The digest job runs daily at 08:30 — that's the email you'll actually look at. Logs go to `logs/scrape.{out,err}.log` and `logs/digest.{out,err}.log`.

To remove: `launchctl unload ~/Library/LaunchAgents/com.philipp.jobbot.*.plist`.

## Auto-apply (off by default)

Per-source flag in `data/config.yaml`:

```yaml
sources:
  indeed:
    auto_submit: true       # opt in only after you've watched a few dry-runs
```

Even with `auto_submit: true`, the global `apply.dry_run: true` in config.yaml prevents real submissions — the runner fills the form, screenshots it, and exits without clicking submit. Set both to enable real submissions, ideally with `apply.confirm_each: true` for a while.

**LinkedIn auto-submit is forbidden by their ToS — leave it off.**

For captcha solving, set `CAPTCHA_API_KEY` in `.env` (default provider: 2Captcha). Without a key, applications that hit a captcha are marked `needs_review` instead of failing.

## Project layout

```
job-bot/
├── PLAN.md                          # full architecture / decisions / risks
├── README.md                        # this file
├── pyproject.toml
├── .env.example
├── data/
│   ├── config.example.yaml          # search queries, thresholds, per-source flags
│   ├── profile.example.yaml         # your structured profile (skills, prefs, screener defaults)
│   └── base_cv.example.md           # your canonical CV in Markdown
├── prompts/
│   ├── match_score.md               # Haiku scoring prompt
│   ├── cv_tailor.md                 # Sonnet CV tailoring
│   ├── cover_letter.md              # Sonnet cover letter
│   └── screener.md                  # answer one application screener question
├── scheduling/
│   ├── com.philipp.jobbot.scrape.plist
│   └── com.philipp.jobbot.digest.plist
├── src/jobbot/
│   ├── __init__.py
│   ├── __main__.py                  # `python -m jobbot`
│   ├── cli.py                       # argparse entrypoints
│   ├── config.py                    # .env + data/config.yaml loaders
│   ├── models.py                    # pydantic data models
│   ├── pipeline.py                  # orchestrator: scrape → score → generate → apply → notify
│   ├── profile.py                   # profile + base_cv loaders
│   ├── scoring.py                   # heuristic + Haiku scorer
│   ├── state.py                     # SQLite schema + helpers
│   ├── scrapers/
│   │   ├── base.py                  # BaseScraper protocol
│   │   ├── registry.py              # name → instance
│   │   ├── weworkremotely.py        # ✅ implemented (RSS)
│   │   ├── freelancermap.py         # ✅ implemented (RSS)
│   │   ├── freelance_de.py          # 🟡 stub (HTML — verify selectors)
│   │   ├── indeed.py                # 🟡 RSS path implemented; Playwright fallback TODO
│   │   ├── stepstone.py             # ⛔ stub (Playwright — M4)
│   │   ├── xing.py                  # ⛔ stub (Playwright — M4)
│   │   └── linkedin.py              # ⛔ stub (M5; consider session-cookie approach)
│   ├── generators/
│   │   └── pipeline.py              # CV + cover letter via Claude → md + html
│   ├── applier/
│   │   ├── runner.py                # Playwright apply flow
│   │   ├── base.py                  # FormAdapter protocol
│   │   └── adapters/
│   │       ├── greenhouse.py
│   │       ├── lever.py
│   │       ├── workday.py
│   │       └── generic.py           # heuristic fallback (dry-run only)
│   ├── otp/imap.py                  # poll Gmail for verification codes
│   ├── captcha/
│   │   ├── base.py                  # CaptchaSolver protocol + NullSolver
│   │   └── twocaptcha.py            # 2Captcha implementation
│   └── notify/
│       ├── email.py                 # Gmail SMTP
│       └── templates/
│           ├── digest.html.j2
│           └── failure.html.j2
└── tests/
    └── test_smoke.py                # imports + heuristic + state schema
```

## Workflow lifecycle

Each scraped job moves through this state machine (`status` column in `seen_jobs`):

```
scraped → filtered                 (heuristic deal-breaker)
        → below_threshold          (LLM score < 70)
        → generated                (CV + CL written)
            → apply_queued
                → apply_submitted  (success)
                → apply_needs_review
                → apply_failed     (captcha/OTP/form error)
```

`jobbot status` prints the count in each stage.

## Roadmap

| Milestone | Scope |
|---|---|
| **M1** ✅ | Scaffold (this commit). |
| **M2** | End-to-end on weworkremotely: real run sends one digest. |
| **M3** | freelancermap + freelance.de + Indeed RSS reliable. |
| **M4** | StepStone + Xing via Playwright. |
| **M5** | LinkedIn (session-cookie approach, behavioral throttling). |
| **M6** | Auto-apply for Greenhouse/Lever forms validated on real postings; captcha + OTP loop tested. |

## Notes & risks

- **Scraping ToS.** All seven sites' ToS prohibit automated access in some form. This is a personal-use tool; volume is low; risk is on you. LinkedIn is the most aggressive about restrictions — keep its rate low.
- **Auto-apply.** Recruiters can usually tell when an application is templated. This pipeline is best for high-volume pre-screening on aggregator boards (Indeed, StepStone), not for relationship-driven roles.
- **LLM cost.** ~€5/month at moderate volume. The `max_jobs_per_run` cap is your safety belt.
- **Captcha solver.** Paid third-party service; legal grey area in some jurisdictions. Disabled unless you set an API key.
