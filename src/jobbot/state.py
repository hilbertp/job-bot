"""SQLite-backed state: dedup index for jobs + run history + applications."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
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
    
    # Connect with timeout and retry-friendly settings
    conn = sqlite3.connect(p, timeout=30.0, check_same_thread=False)
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
