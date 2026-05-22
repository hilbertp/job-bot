"""One-shot apply-batch: run apply_to_job against every 'generated' row
that has a direct ATS/employer apply URL and hasn't already been submitted.

Usage:
    uv run python scripts/apply_batch.py [--limit N]

The config.apply.dry_run setting is respected (currently true = screenshot
only, no real submission). auto_submit per-source is BYPASSED here; this
script exists precisely to apply to the backlog of already-generated rows
that the pipeline's scoring loop never re-visits.

Results are recorded in the applications table and the seen_jobs status
is updated the same way the pipeline does it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --- repo path setup -------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from jobbot.cli import load_config, load_secrets
from jobbot.applier.runner import apply_to_job
from jobbot.generators.pipeline import load_existing_docs
from jobbot.models import JobPosting, JobStatus
from jobbot.profile import load_profile
from jobbot.state import connect, jobs_with_submitted_application, record_application, update_status

import structlog
log = structlog.get_logger()

import re as _re

# URLs that are job-listing aggregators or generic careers homepages;
# no specific application form exists at these addresses.
SKIP_URL_PATTERNS = [
    "de.linkedin.com/jobs/view/",
    "www.stepstone.de/stellenangebote",
    "www.freelancermap.de/projekt",
    "dailyremote.com/remote-job",  # dailyremote paywall landing
]

# Ashby org-level pages have no UUID — just https://jobs.ashbyhq.com/<org>
# A job-specific URL always has a 36-char UUID after the org slug.
_ASHBY_ORG_ONLY = _re.compile(
    r"^https?://jobs\.ashbyhq\.com/[^/]+/?$"
)

# Generic career-listing pages ending in bare /jobs (or /jobs?...) with no
# job-id following — these are index pages, not specific application forms.
# Also handles locale-prefixed variants like /en/jobs, /de/jobs, /en-US/jobs,
# /en_US/jobs (Siemens Energy style).
_GENERIC_JOBS_PAGE = _re.compile(
    r"^https?://[^/]+(/[a-z]{2}([_-][A-Za-z]{2,4})?)?/jobs/?(\?.*)?$"
)


def is_skippable(apply_url: str | None) -> bool:
    if not apply_url:
        return True
    if any(p in apply_url for p in SKIP_URL_PATTERNS):
        return True
    if _ASHBY_ORG_ONLY.match(apply_url):
        return True
    if _GENERIC_JOBS_PAGE.match(apply_url):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply to all generated jobs")
    ap.add_argument("--limit", type=int, default=50, help="Max jobs to attempt")
    args = ap.parse_args()

    config = load_config()
    secrets = load_secrets()
    profile = load_profile()

    with connect() as conn:
        already_applied = jobs_with_submitted_application(conn)

        rows = conn.execute(
            """
            SELECT id, source, title, company, score, raw_json, output_dir
            FROM   seen_jobs
            WHERE  status = 'generated'
            ORDER  BY score DESC
            """
        ).fetchall()

    print(f"Found {len(rows)} generated jobs. dry_run={config.apply.dry_run}")
    print()

    attempted = skipped_url = skipped_applied = skipped_no_docs = 0
    results: list[dict] = []

    for row in rows[: args.limit]:
        raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
        apply_url = raw.get("apply_url") or ""

        label = f"[{row['score']}] {row['company']} - {row['title']}"

        if row["id"] in already_applied:
            print(f"  SKIP (already applied) {label}")
            skipped_applied += 1
            continue

        if is_skippable(apply_url):
            print(f"  SKIP (paywalled/generic URL) {label}")
            print(f"       {apply_url}")
            skipped_url += 1
            continue

        docs = load_existing_docs(row["output_dir"])
        if docs is None:
            print(f"  SKIP (no docs on disk) {label}")
            skipped_no_docs += 1
            continue

        try:
            job = JobPosting.model_validate_json(row["raw_json"])
        except Exception as e:
            print(f"  ERROR parse {label}: {e}")
            continue

        print(f"  APPLY {label}")
        print(f"        {apply_url}")

        try:
            res = apply_to_job(job, profile, docs, secrets, config)
        except Exception as e:
            print(f"    -> EXCEPTION: {e}")
            results.append({"id": row["id"], "status": "exception", "error": str(e)})
            continue

        with connect() as conn:
            record_application(conn, job.id, res)
            update_status(conn, job.id, res.status)

        tag = (
            "SUBMITTED" if res.submitted
            else "DRY-RUN" if res.dry_run
            else f"NEEDS-REVIEW ({res.needs_review_reason})" if res.status == JobStatus.APPLY_NEEDS_REVIEW
            else f"FAILED ({res.error})"
        )
        print(f"    -> {tag}"
              + (f"  screenshot: {res.screenshot_path}" if res.screenshot_path else ""))
        results.append({
            "id": row["id"], "company": row["company"], "title": row["title"],
            "apply_url": apply_url, "status": tag,
            "screenshot": res.screenshot_path,
        })
        attempted += 1

    print()
    print(f"Done. attempted={attempted}, skipped_url={skipped_url}, "
          f"skipped_applied={skipped_applied}, skipped_no_docs={skipped_no_docs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
