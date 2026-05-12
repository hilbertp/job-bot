#!/usr/bin/env bash
# job-bot one-shot installer.
#
# Safe to re-run: every step is a no-op when the target is already in place.
# Halts on the FIRST unrecoverable error and tells you what to fix.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Python version
# ---------------------------------------------------------------------------
bold "1. Checking Python"
PYTHON_BIN="${PYTHON:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN=python3.11
  else
    die "Need Python 3.11 or 3.12. Install:
       macOS:  brew install python@3.12
       Linux:  sudo apt install python3.12 python3.12-venv"
  fi
fi
PY_VERSION="$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
ok "Found $PYTHON_BIN (Python $PY_VERSION)"

# ---------------------------------------------------------------------------
# 2. Virtualenv
# ---------------------------------------------------------------------------
bold "2. Creating virtualenv (.venv)"
if [ -d .venv ]; then
  ok ".venv already exists"
else
  $PYTHON_BIN -m venv .venv
  ok "Created .venv with $PYTHON_BIN"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
ok "Activated .venv (you'll need 'source .venv/bin/activate' in new shells)"

# ---------------------------------------------------------------------------
# 3. Python deps
# ---------------------------------------------------------------------------
bold "3. Installing Python packages"
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"
ok "Installed jobbot + dev dependencies"

# ---------------------------------------------------------------------------
# 4. Playwright Chromium
# ---------------------------------------------------------------------------
bold "4. Installing Playwright Chromium (~150 MB, one-time)"
if [ -d "$HOME/Library/Caches/ms-playwright" ] || [ -d "$HOME/.cache/ms-playwright" ]; then
  ok "Playwright browsers already cached"
else
  playwright install chromium >/dev/null 2>&1 || warn "playwright install hit an issue — run it manually with 'playwright install chromium'"
  ok "Chromium installed"
fi

# ---------------------------------------------------------------------------
# 5. Personal data files (copy templates if missing)
# ---------------------------------------------------------------------------
bold "5. Personal data files (gitignored)"
for pair in \
    ".env.example:.env" \
    "data/profile.example.yaml:data/profile.yaml" \
    "data/base_cv.example.md:data/base_cv.md" \
    "data/config.example.yaml:data/config.yaml"; do
  template="${pair%:*}"
  target="${pair#*:}"
  if [ -f "$target" ]; then
    ok "$target already exists — kept yours"
  elif [ -f "$template" ]; then
    cp "$template" "$target"
    ok "Created $target from $template (EDIT THIS)"
  else
    warn "$template missing — skipping $target"
  fi
done

# ---------------------------------------------------------------------------
# 6. Sanity smoke
# ---------------------------------------------------------------------------
bold "6. Smoke test"
if jobbot sources >/dev/null 2>&1; then
  ok "jobbot CLI installed ($(jobbot sources | wc -l | tr -d ' ') sources registered)"
else
  die "jobbot CLI not on PATH — try 'source .venv/bin/activate' and re-run"
fi

# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------
cat <<'EOF'

────────────────────────────────────────────────────────────────────────
Setup complete. Three things still need YOUR input before first run:

  1. Edit .env — paste your ANTHROPIC_API_KEY and GMAIL_APP_PASSWORD
     - Get the Anthropic key: https://console.anthropic.com/settings/keys
     - Generate Gmail app password: https://myaccount.google.com/apppasswords

  2. Edit data/profile.yaml — name, email, salary range, deal-breakers

  3. Edit data/base_cv.md — your CV in Markdown (1-3 pages)

Then:
     pytest -q -m "not live"     # confirm tests pass
     jobbot run                  # first end-to-end run
     jobbot dashboard            # http://localhost:5001

Stuck? See README.md → Troubleshooting.
────────────────────────────────────────────────────────────────────────
EOF
