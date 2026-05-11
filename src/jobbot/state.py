"""SQLite-backed state: dedup index for jobs + run history + applications."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import REPO_ROOT
from .models import JobPosting, JobStatus

DB_PATH = REPO_ROOT / "data" / "jobbot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT,
    company       TEXT,
    first_seen_at TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'scraped',
    score         INTEGER,
    score_reason  TEXT,
    description_full TEXT,
    description_scraped INTEGER,
    description_word_count INTEGER,
    seniority     TEXT,
    salary_text   TEXT,
    apply_email   TEXT,
    score_breakdown_json TEXT,
    enriched_at   TEXT,
    scored_at     TEXT,
    output_dir    TEXT,
    raw_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen_status ON seen_jobs(status);
CREATE INDEX IF NOT EXISTS idx_seen_seen   ON seen_jobs(first_seen_at);

CREATE TABLE IF NOT EXISTS applications (
    job_id              TEXT PRIMARY KEY REFERENCES seen_jobs(id),
    attempted_at        TEXT NOT NULL,
    status              TEXT NOT NULL,
    submitted           INTEGER NOT NULL DEFAULT 0,
    dry_run             INTEGER NOT NULL DEFAULT 1,
    needs_review_reason TEXT,
    error               TEXT,
    screenshot_path     TEXT,
    confirmation_url    TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    n_fetched    INTEGER DEFAULT 0,
    n_new        INTEGER DEFAULT 0,
    n_generated  INTEGER DEFAULT 0,
    n_applied    INTEGER DEFAULT 0,
    n_errors     INTEGER DEFAULT 0,
    summary_json TEXT
);
"""

SEEN_JOBS_ADD_COLUMNS: list[tuple[str, str]] = [
    ("description_full", "TEXT"),
    ("description_scraped", "INTEGER"),
    ("description_word_count", "INTEGER"),
    ("seniority", "TEXT"),
    ("salary_text", "TEXT"),
    ("apply_email", "TEXT"),
    ("score_breakdown_json", "TEXT"),
    ("enriched_at", "TEXT"),
    ("scored_at", "TEXT"),
    # Stage-3 rescore: the same scorer run AFTER tailored CV + CL are
    # produced, so the dashboard can show "did tailoring lift the fit?"
    ("score_tailored", "INTEGER"),
    ("score_tailored_reason", "TEXT"),
    ("score_tailored_breakdown_json", "TEXT"),
    ("scored_tailored_at", "TEXT"),
]


def _ensure_seen_jobs_columns(conn: sqlite3.Connection) -> None:
    """PRD §7.2 FR-PER-01: additive, idempotent migration for enrichment columns."""
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(seen_jobs)")
    }
    for name, typ in SEEN_JOBS_ADD_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE seen_jobs ADD COLUMN {name} {typ}")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class LockStatus:
    locked: bool
    detail: str
    holders: list[dict[str, str]]


def _lock_holders(p: Path) -> list[dict[str, str]]:
    """Best-effort: shell out to lsof to identify processes holding the DB."""
    if not shutil.which("lsof"):
        return []
    try:
        out = subprocess.run(
            ["lsof", "-F", "pcn", str(p)],
            capture_output=True, text=True, timeout=2.0,
        ).stdout
    except Exception:
        return []
    holders: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in out.splitlines():
        tag, val = line[:1], line[1:]
        if tag == "p":
            if cur:
                holders.append(cur)
            cur = {"pid": val}
        elif tag == "c":
            cur["command"] = val
    if cur:
        holders.append(cur)
    return holders


def db_lock_status(db_path: Path | None = None) -> LockStatus:
    """Quickly determine whether the DB is currently held in a writer lock.

    Strategy: open a fresh connection with a 100ms busy_timeout and try
    `BEGIN IMMEDIATE`. SQLite returns an OperationalError ("database is
    locked"/"busy") iff another connection currently holds the writer lock.
    Rolls back immediately on success so we never block anyone else.
    """
    p = db_path or DB_PATH
    if not p.exists():
        return LockStatus(locked=False, detail="db file does not exist yet", holders=[])
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(p, timeout=0.2, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 100")
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ROLLBACK")
            return LockStatus(locked=False, detail="writer lock available", holders=_lock_holders(p))
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "lock" in msg or "busy" in msg:
                return LockStatus(locked=True, detail=str(e), holders=_lock_holders(p))
            raise
    except sqlite3.OperationalError as e:
        return LockStatus(locked=True, detail=str(e), holders=_lock_holders(p))
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    p = db_path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    
    # Clean up stale journal files
    journal_path = p.with_suffix('.db-journal')
    if journal_path.exists():
        try:
            journal_path.unlink()
        except Exception:
            pass
    
    # Connect with timeout and retry-friendly settings.
    # isolation_level=None puts sqlite3 in autocommit mode: each statement
    # commits immediately, so the writer lock is held for milliseconds at a
    # time instead of for the full pipeline run. This lets the dashboard and
    # ad-hoc tools write while a `jobbot run` is in progress.
    conn = sqlite3.connect(p, timeout=30.0, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    
    try:
        # Enable WAL mode for better concurrent access
        # WAL allows reads while writes are in progress
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")  # Faster but still safe
        conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout for locks
        
        conn.executescript(SCHEMA)
        _ensure_seen_jobs_columns(conn)
        yield conn
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def upsert_new(conn: sqlite3.Connection, jobs: list[JobPosting]) -> list[JobPosting]:
    """Insert jobs we have not seen before. Returns the subset that was new."""
    new_jobs: list[JobPosting] = []
    for j in jobs:
        cur = conn.execute(
            "INSERT OR IGNORE INTO seen_jobs(id, source, url, title, company, first_seen_at, status, score, score_reason, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                j.id,
                j.source,
                str(j.url),
                j.title,
                j.company,
                _now(),
                JobStatus.SCRAPED.value,
                0,
                "awaiting scoring",
                json.dumps(j.model_dump(mode="json")),
            ),
        )
        if cur.rowcount:
            new_jobs.append(j)
    return new_jobs


def update_status(conn: sqlite3.Connection, job_id: str, status: JobStatus,
                  score: int | None = None, reason: str | None = None,
                  output_dir: str | None = None) -> None:
    sets = ["status = ?"]
    args: list = [status.value]
    if score is not None:
        sets.append("score = ?")
        args.append(score)
    if reason is not None:
        sets.append("score_reason = ?")
        args.append(reason)
    if output_dir is not None:
        sets.append("output_dir = ?")
        args.append(output_dir)
    args.append(job_id)
    conn.execute(f"UPDATE seen_jobs SET {', '.join(sets)} WHERE id = ?", args)


def update_enrichment(
    conn: sqlite3.Connection,
    job_id: str,
    description_full: str,
    description_scraped: bool,
    description_word_count: int,
    seniority: str | None,
    salary_text: str | None,
    apply_email: str | None,
) -> None:
    """Persist enrichment fields for a posting and keep raw_json description in sync."""
    row = conn.execute("SELECT raw_json FROM seen_jobs WHERE id = ?", (job_id,)).fetchone()
    raw_json = row["raw_json"] if row else "{}"
    try:
        payload = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict):
        payload["description"] = description_full or payload.get("description", "")

    conn.execute(
        "UPDATE seen_jobs SET description_full = ?, description_scraped = ?, "
        "description_word_count = ?, seniority = ?, salary_text = ?, apply_email = ?, "
        "enriched_at = ?, raw_json = ? WHERE id = ?",
        (
            description_full,
            int(description_scraped),
            description_word_count,
            seniority,
            salary_text,
            apply_email,
            _now(),
            json.dumps(payload),
            job_id,
        ),
    )


def update_score_tailored(
    conn: sqlite3.Connection,
    job_id: str,
    score: int,
    reason: str,
    breakdown: dict | None = None,
) -> None:
    """Persist the Stage-3 rescore (tailored CV + CL substituted into the
    scoring prompt). Leaves the original `score` column untouched so the
    dashboard can render a true before/after pair."""
    conn.execute(
        "UPDATE seen_jobs SET score_tailored = ?, score_tailored_reason = ?, "
        "score_tailored_breakdown_json = ?, scored_tailored_at = ? WHERE id = ?",
        (
            score,
            reason,
            json.dumps(breakdown) if breakdown else None,
            _now(),
            job_id,
        ),
    )


def record_application(conn: sqlite3.Connection, job_id: str, result) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO applications(job_id, attempted_at, status, submitted, dry_run, "
        "needs_review_reason, error, screenshot_path, confirmation_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            job_id, _now(), result.status.value,
            int(result.submitted), int(result.dry_run),
            result.needs_review_reason, result.error,
            result.screenshot_path, result.confirmation_url,
        ),
    )


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO runs(started_at) VALUES (?)", (_now(),))
    return cur.lastrowid  # type: ignore[return-value]


def finish_run(conn: sqlite3.Connection, run_id: int, **counts) -> None:
    conn.execute(
        "UPDATE runs SET finished_at = ?, n_fetched = ?, n_new = ?, n_generated = ?, "
        "n_applied = ?, n_errors = ?, summary_json = ? WHERE id = ?",
        (
            _now(),
            counts.get("n_fetched", 0),
            counts.get("n_new", 0),
            counts.get("n_generated", 0),
            counts.get("n_applied", 0),
            counts.get("n_errors", 0),
            json.dumps(counts.get("summary", {})),
            run_id,
        ),
    )


def jobs_needing_enrichment(conn: sqlite3.Connection) -> list[JobPosting]:
    """Re-hydrate JobPosting objects for rows where description_scraped IS NULL.

    These are postings scraped before the enrichment phase was wired into the
    pipeline; without this they would never get a body fetch on subsequent runs
    because dedup excludes them from `all_new`.
    """
    rows = conn.execute(
        "SELECT raw_json FROM seen_jobs WHERE description_scraped IS NULL "
        "AND raw_json IS NOT NULL"
    ).fetchall()
    out: list[JobPosting] = []
    for row in rows:
        try:
            out.append(JobPosting.model_validate_json(row["raw_json"]))
        except Exception:
            continue
    return out


def jobs_needing_backfill(conn: sqlite3.Connection, min_words: int, limit: int) -> list[JobPosting]:
    """Rows whose body is missing or shorter than `min_words` — sorted oldest
    first so backfill steadily drains the long tail of pre-enrichment rows
    without thrashing the most recent ones. The CLI caps `limit` per
    invocation to keep the work bounded.
    """
    rows = conn.execute(
        "SELECT raw_json FROM seen_jobs "
        "WHERE raw_json IS NOT NULL "
        "  AND (description_scraped IS NULL "
        "       OR description_word_count IS NULL "
        "       OR description_word_count < ?) "
        "ORDER BY first_seen_at ASC "
        "LIMIT ?",
        (min_words, limit),
    ).fetchall()
    out: list[JobPosting] = []
    for row in rows:
        try:
            out.append(JobPosting.model_validate_json(row["raw_json"]))
        except Exception:
            continue
    return out


def jobs_needing_tailored_rescore(
    conn: sqlite3.Connection, limit: int = 100,
) -> list[tuple[JobPosting, str]]:
    """Rows that already went through Stage 3 generation but never got their
    Stage 3 rescore. Returns (job, output_dir) tuples so the caller can read
    the tailored CV + cover letter from disk and pass them to
    `llm_score_tailored`. The job's `description` is filled from
    `description_full` (the post-enrichment body) rather than the original
    scrape snippet, since the rescore prompt needs the full body.

    Ordered oldest-generated first so repeated backfill calls drain the
    queue deterministically.
    """
    rows = conn.execute(
        "SELECT raw_json, description_full, output_dir FROM seen_jobs "
        "WHERE status = 'generated' "
        "  AND score_tailored IS NULL "
        "  AND output_dir IS NOT NULL "
        "  AND raw_json IS NOT NULL "
        "ORDER BY first_seen_at ASC "
        "LIMIT ?",
        (limit,),
    ).fetchall()
    out: list[tuple[JobPosting, str]] = []
    for row in rows:
        try:
            job = JobPosting.model_validate_json(row["raw_json"])
        except Exception:
            continue
        if row["description_full"]:
            job = job.model_copy(update={"description": row["description_full"]})
        out.append((job, row["output_dir"]))
    return out


_APPLY_CHANNEL_ATS = {
    "greenhouse.io":      "Greenhouse",
    "lever.co":           "Lever",
    "myworkdayjobs.com":  "Workday",
    "smartrecruiters.com": "SmartRecruiters",
    "personio":           "Personio",
}


def apply_channel(
    row: sqlite3.Row | None = None,
    *,
    apply_email: str | None = None,
    apply_url: str | None = None,
) -> str:
    """Derive the application channel for a posting per PRD §7.7 FR-APP-01.

    Returns one of: 'email', 'form', 'external', 'manual'.

    - email:    `apply_email` is present.
    - form:     `apply_url` matches a known ATS (greenhouse / lever /
                workday / smartrecruiters / personio).
    - external: `apply_url` is present but isn't a known ATS.
    - manual:   neither email nor URL — needs human handling.

    Accepts a sqlite3.Row (or any mapping with 'apply_email'/'apply_url'
    keys) OR kwargs. The row form is convenient for digest/dashboard
    builders that iterate seen_jobs; the kwargs form is convenient inside
    the pipeline where the JobPosting and the enrichment columns aren't
    always in the same object.
    """
    if row is not None:
        try:
            apply_email = row["apply_email"]
        except (KeyError, IndexError):
            pass
        try:
            apply_url = row["apply_url"]
        except (KeyError, IndexError):
            pass
    if apply_email and str(apply_email).strip():
        return "email"
    if apply_url and str(apply_url).strip():
        url_lower = str(apply_url).lower()
        for needle in _APPLY_CHANNEL_ATS:
            if needle in url_lower:
                return "form"
        return "external"
    return "manual"


def apply_channel_ats_name(apply_url: str | None) -> str | None:
    """If apply_url points at a known ATS, return its human name
    ('Greenhouse', 'Lever', 'Workday', 'SmartRecruiters', 'Personio').
    Returns None for non-ATS URLs or empty input.
    """
    if not apply_url:
        return None
    url_lower = str(apply_url).lower()
    for needle, name in _APPLY_CHANNEL_ATS.items():
        if needle in url_lower:
            return name
    return None


def jobs_by_status(conn: sqlite3.Connection, status: JobStatus, since: datetime | None = None) -> list[sqlite3.Row]:
    if since:
        return list(conn.execute(
            "SELECT * FROM seen_jobs WHERE status = ? AND first_seen_at >= ? ORDER BY first_seen_at DESC",
            (status.value, since.isoformat()),
        ))
    return list(conn.execute(
        "SELECT * FROM seen_jobs WHERE status = ? ORDER BY first_seen_at DESC",
        (status.value,),
    ))
