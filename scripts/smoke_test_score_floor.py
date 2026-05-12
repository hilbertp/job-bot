"""Non-destructive score-floor smoke test.

Picks a small mix of borderline (70-84) and mid-range (60-69) rows from
seen_jobs, re-scores each against the current prompt + profile, and prints
OLD vs NEW side by side. Does NOT write back to the DB.

Use this to validate prompt changes (e.g. score-floor calibration, new
user_facts wiring) before doing a real `jobbot rescore --base --force`.
"""
from __future__ import annotations

import json

from jobbot.config import load_secrets
from jobbot.models import JobPosting
from jobbot.profile import load_profile
from jobbot.scoring import CannotScore, llm_score
from jobbot.state import connect


def _row_to_posting(row) -> JobPosting:
    raw = json.loads(row["raw_json"])
    raw["description"] = row["description_full"] or raw.get("description") or ""
    return JobPosting(**raw)


def main() -> int:
    profile = load_profile()
    secrets = load_secrets()

    with connect() as conn:
        borderline = conn.execute(
            """
            SELECT id, score, score_reason, title, company, raw_json, description_full
            FROM seen_jobs
            WHERE score BETWEEN 70 AND 84
              AND description_scraped = 1
              AND description_word_count >= 100
              AND raw_json IS NOT NULL
            ORDER BY first_seen_at DESC
            LIMIT 3
            """
        ).fetchall()
        midrange = conn.execute(
            """
            SELECT id, score, score_reason, title, company, raw_json, description_full
            FROM seen_jobs
            WHERE score BETWEEN 60 AND 69
              AND description_scraped = 1
              AND description_word_count >= 100
              AND raw_json IS NOT NULL
            ORDER BY first_seen_at DESC
            LIMIT 2
            """
        ).fetchall()
        sample = list(borderline) + list(midrange)

    print(f"sampling {len(sample)} rows: "
          f"{len(borderline)} borderline (70-84) + {len(midrange)} mid (60-69)")
    print(f"user_facts in profile: {profile.user_facts}")
    print()

    deltas: list[int] = []
    for row in sample:
        old = int(row["score"])
        job = _row_to_posting(row)
        try:
            result = llm_score(job, profile, secrets, description_scraped=True)
        except CannotScore as e:
            print(f"[SKIP] {job.id[:12]} {(job.title or '')[:50]}: {e}")
            continue
        new = int(result.score)
        delta = new - old
        deltas.append(delta)
        sign = "+" if delta >= 0 else ""
        title = (job.title or "")[:55]
        company = (job.company or "")[:22]
        print(f"  OLD={old:3d}  NEW={new:3d}  {sign}{delta:+3d}   "
              f"{title:55s} @ {company}")
        print(f"    OLD reason: {(row['score_reason'] or '')[:200]}")
        print(f"    NEW reason: {(result.reason or '')[:200]}")
        print()

    if deltas:
        avg = sum(deltas) / len(deltas)
        up = sum(1 for d in deltas if d > 0)
        down = sum(1 for d in deltas if d < 0)
        same = sum(1 for d in deltas if d == 0)
        print(f"summary: {len(deltas)} rescored | up={up} down={down} same={same} | avg delta={avg:+.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
