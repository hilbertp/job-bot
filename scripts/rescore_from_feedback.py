"""Parse data/reports/score_downgrades_review.md and re-score each row
that has a non-empty `### Your comment:` block. The user's comment is
injected into the scoring prompt via llm_score(..., user_feedback=...).

Outputs:
  - DB: seen_jobs.score / score_reason updated in place (scored_at refreshed)
  - CSV log: data/reports/score_after_feedback.csv (one row per re-scored posting)

Run after editing the review markdown:

    .venv/bin/python scripts/rescore_from_feedback.py

Pre-feedback Sonnet scores remain in score_snapshot_post_sonnet46.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from jobbot.config import load_secrets  # noqa: E402
from jobbot.models import JobPosting  # noqa: E402
from jobbot.profile import load_profile  # noqa: E402
from jobbot.scoring import CannotScore, llm_score  # noqa: E402
from jobbot.state import connect, update_base_score_only  # noqa: E402

REVIEW_MD = REPO_ROOT / "data" / "reports" / "score_downgrades_review.md"
OUT_CSV = REPO_ROOT / "data" / "reports" / "score_after_feedback.csv"

_ID_RE = re.compile(r"^##\s+([A-Za-z0-9_\-]+)\s*$", re.MULTILINE)


def parse_review(md_text: str) -> list[tuple[str, str]]:
    """Return [(id, comment), ...] for sections with a non-empty user
    comment block. Sections without prose under `### Your comment:`
    (only the HTML placeholder comment or whitespace) are skipped."""
    # Split on the `\n---\n` horizontal rule between sections.
    chunks = re.split(r"\n---+\n", md_text)
    out: list[tuple[str, str]] = []
    for chunk in chunks:
        m = _ID_RE.search(chunk)
        if not m:
            continue
        row_id = m.group(1).strip()
        # Pull everything after the first occurrence of `### Your comment:`.
        marker = "### Your comment:"
        idx = chunk.find(marker)
        if idx < 0:
            continue
        body = chunk[idx + len(marker):]
        # Strip HTML comment placeholders and whitespace.
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        body = body.strip()
        if not body:
            continue
        out.append((row_id, body))
    return out


def load_job(conn: sqlite3.Connection, job_id: str) -> JobPosting | None:
    row = conn.execute(
        "SELECT raw_json, description_full FROM seen_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    if not row or not row["raw_json"]:
        return None
    try:
        job = JobPosting.model_validate_json(row["raw_json"])
    except Exception:
        return None
    if row["description_full"]:
        job = job.model_copy(update={"description": row["description_full"]})
    return job


def main() -> int:
    if not REVIEW_MD.exists():
        print(f"missing review file: {REVIEW_MD}", file=sys.stderr)
        print("run scripts/gen_downgrades_review.py first.", file=sys.stderr)
        return 1

    entries = parse_review(REVIEW_MD.read_text())
    if not entries:
        print("no non-empty user comments in the review file — nothing to do.")
        return 0

    secrets = load_secrets()
    profile = load_profile()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows_log: list[dict[str, object]] = []

    with connect() as conn:
        for job_id, comment in entries:
            row = conn.execute(
                "SELECT score AS score_pre, score_reason AS reason_pre, "
                "       company, title "
                "FROM seen_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                print(f"skip {job_id}: not in DB")
                continue
            job = load_job(conn, job_id)
            if not job:
                print(f"skip {job_id}: cannot load JobPosting (no raw_json/description)")
                continue
            try:
                result = llm_score(
                    job, profile, secrets,
                    description_scraped=True,
                    user_feedback=comment,
                )
            except CannotScore as e:
                print(f"skip {job_id}: cannot_score: {e.reason}")
                continue
            except Exception as e:
                print(f"skip {job_id}: scorer error: {e}")
                continue

            update_base_score_only(conn, job_id, result.score, result.reason)
            print(
                f"{job_id}  {row['score_pre']} -> {result.score}  "
                f"({row['company'] or '?'} — {(row['title'] or '?')[:50]})"
            )
            rows_log.append({
                "id": job_id,
                "company": row["company"],
                "title": row["title"],
                "score_pre_feedback": row["score_pre"],
                "score_post_feedback": result.score,
                "delta": result.score - (row["score_pre"] or 0),
                "user_comment": comment,
                "reason_pre_feedback": row["reason_pre"],
                "reason_post_feedback": result.reason,
            })

    if rows_log:
        with OUT_CSV.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_log[0].keys()))
            writer.writeheader()
            writer.writerows(rows_log)
        print(f"\nwrote {len(rows_log)} row(s) to {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
