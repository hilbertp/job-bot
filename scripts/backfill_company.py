"""One-shot backfill for existing rows whose company stayed at the
listing-page placeholder ("Unknown", "(see posting)", etc.) because the
old enrichment runner discarded the real name returned by fetch_detail.

After PR #N fixed `update_enrichment` to persist the company, this script
walks every still-placeholder row, re-runs the scraper's fetch_detail,
and updates the company column in place. Read-only for everything else
(description, score, status — all left alone).

Idempotent: re-running is safe. Rows whose company is now real are
skipped on the next pass.

Usage:
    python scripts/backfill_company.py            # dry run, prints what would change
    python scripts/backfill_company.py --write    # actually update the DB
    python scripts/backfill_company.py --write --source dailyremote   # one source only
"""
from __future__ import annotations

import argparse
import json
import sys

from jobbot.models import JobPosting
from jobbot.scrapers import REGISTRY
from jobbot.state import _is_real_company_name, connect


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true",
                   help="actually update seen_jobs.company (default: dry run)")
    p.add_argument("--source", default=None,
                   help="only re-fetch this source (e.g. dailyremote)")
    p.add_argument("--limit", type=int, default=None,
                   help="cap total rows processed")
    args = p.parse_args()

    with connect() as conn:
        sql = """
            SELECT id, source, raw_json
            FROM seen_jobs
            WHERE company IS NULL OR company = ''
               OR LOWER(TRIM(company)) IN (
                   'unknown', '(see posting)', '[unlock with premium]',
                   'anonymous', 'auftraggeber', 'projektanbieter',
                   'freelancermap (auftraggeber anonym)'
               )
        """
        params: list = []
        if args.source:
            sql += " AND source = ?"
            params.append(args.source)
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = conn.execute(sql, params).fetchall()

    print(f"found {len(rows)} rows with placeholder company"
          f"{f' (source={args.source})' if args.source else ''}")
    if not rows:
        return 0

    updated = 0
    skipped = 0
    failed = 0

    for row in rows:
        source = row["source"]
        scraper = REGISTRY.get(source)
        if scraper is None or not hasattr(scraper, "fetch_detail"):
            skipped += 1
            continue
        try:
            payload = json.loads(row["raw_json"] or "{}")
            payload.setdefault("description", "")
            job = JobPosting(**payload)
        except Exception as e:
            print(f"  [{row['id'][:14]}] raw_json parse failed: {e}")
            failed += 1
            continue

        try:
            enriched = scraper.fetch_detail(job)
        except Exception as e:
            print(f"  [{row['id'][:14]}] fetch_detail crashed: {e}")
            failed += 1
            continue

        if enriched is None:
            skipped += 1
            continue
        new_company = (enriched.company or "").strip()
        if not _is_real_company_name(new_company):
            skipped += 1
            continue

        action = "UPDATE" if args.write else "would update"
        print(f"  [{row['id'][:14]}] {source:>12s}  {action}: company → {new_company!r}")
        if args.write:
            with connect() as conn:
                conn.execute(
                    "UPDATE seen_jobs SET company = ? WHERE id = ?",
                    (new_company, row["id"]),
                )
        updated += 1

    mode = "applied" if args.write else "dry-run only"
    print(f"\nsummary ({mode}): {updated} updated, {skipped} skipped, "
          f"{failed} failed (of {len(rows)} candidate rows)")
    if not args.write and updated:
        print("re-run with --write to actually apply these changes.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
