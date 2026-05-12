"""Generate data/reports/score_downgrades_review.md — one section per row
whose Sonnet-4.6 score is lower than its previous (pre-Sonnet) score.

The user fills in the "Your comment:" block per row, then runs
`scripts/rescore_from_feedback.py` to re-score those rows with the
comment injected into the prompt.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "jobbot.db"
OUT_PATH = REPO_ROOT / "data" / "reports" / "score_downgrades_review.md"

HEADER = """\
# Score downgrade review — Sonnet 4.6 + primary CV

For each posting below, the **new** Sonnet-4.6 score is lower than the
**old** score from the previous run. If you want the model to reconsider,
write your feedback in the `### Your comment:` block — anything from a
correction ("I'm willing to relocate to Freiburg") to extra context
("I led a 3-year Finanzbuchhaltung integration that isn't on my CV").
Empty comments are skipped.

When done, run:

```
.venv/bin/python scripts/rescore_from_feedback.py
```

The script parses this file, calls Sonnet 4.6 with your comment injected
into the prompt, and updates the score in seen_jobs. The pre-feedback
score is preserved in the `score_snapshot_post_sonnet46` table.

---
"""

SECTION_TEMPLATE = """\
## {id}

**{company}** — *{title}*
**Old score:** {old}  →  **New score:** {new}  (delta {delta:+d})
**Source:** {source}  ·  **URL:** {url}

**New score reason:**
> {reason}

### Your comment:
<!-- Leave empty to skip this row. -->


---
"""


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT j.id, j.source, j.company, j.title, j.url,
               s.score_old, j.score AS score_new, j.score_reason
        FROM seen_jobs j
        JOIN score_snapshot_pre_sonnet46 s ON s.id = j.id
        WHERE j.score IS NOT NULL AND j.score < s.score_old
        ORDER BY (j.score - s.score_old) ASC, j.score ASC
        """
    ).fetchall()

    parts: list[str] = [HEADER]
    for r in rows:
        parts.append(SECTION_TEMPLATE.format(
            id=r["id"],
            source=r["source"] or "—",
            company=r["company"] or "(unknown company)",
            title=r["title"] or "(no title)",
            url=r["url"] or "—",
            old=r["score_old"],
            new=r["score_new"],
            delta=r["score_new"] - r["score_old"],
            reason=(r["score_reason"] or "").replace("\n", " ").strip() or "(no reason recorded)",
        ))

    OUT_PATH.write_text("".join(parts))
    print(f"wrote {len(rows)} sections to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
