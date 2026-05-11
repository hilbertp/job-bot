#!/usr/bin/env bash
# Fail if anything that should be gitignored is currently tracked.
# Run via: ./scripts/check-secrets.sh  (or wire to pre-push hook).
set -euo pipefail

# Patterns that must never appear in `git ls-files`.
# These mirror the "Secrets / personal data" block in .gitignore.
BAD_PATTERNS=(
    '^\.env$'
    '^\.env\.'
    '^data/profile\.yaml$'
    '^data/profile\.compiled\.yaml$'
    '^data/base_cv\.md$'
    '^data/config\.yaml$'
    '^data/general .*\.pdf$'
    '^data/corpus/cvs/'
    '^data/corpus/website/'
    '^data/jobbot\.db'
)

tracked=$(git ls-files)
# Whitelist: things that look like they match a bad pattern but are intentionally
# tracked (templates, dir-keep markers).
WHITELIST_RE='(^\.env\.example$|/\.gitkeep$|^data/corpus/README\.md$)'

violations=()
for pat in "${BAD_PATTERNS[@]}"; do
    matches=$(printf "%s\n" "$tracked" | grep -E "$pat" | grep -vE "$WHITELIST_RE" || true)
    if [ -n "$matches" ]; then
        while IFS= read -r line; do
            violations+=("$line")
        done <<< "$matches"
    fi
done

if [ ${#violations[@]} -ne 0 ]; then
    echo "FAIL: personal data tracked by git — should be in .gitignore." >&2
    printf '  %s\n' "${violations[@]}" >&2
    echo "" >&2
    echo "Run 'git rm --cached <file>' to stop tracking without deleting from disk," >&2
    echo "then commit. Rotate any exposed credentials." >&2
    exit 1
fi

echo "OK: no personal data tracked."
