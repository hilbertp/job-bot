"""SQLite-backed state: dedup index for jobs + run history + applications."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import time
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
    confirmation_url    TEXT,
    received_at         TEXT,
    last_response_at    TEXT,
    response_type       TEXT,
    response_subject    TEXT,
    response_snippet    TEXT,
    proof_level         INTEGER NOT NULL DEFAULT 0,
    proof_evidence      TEXT,
    last_checked_at     TEXT
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

CREATE TABLE IF NOT EXISTS run_stage_progress (
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    stage         TEXT NOT NULL,
    total         INTEGER DEFAULT 0,
    started       INTEGER DEFAULT 0,
    completed     INTEGER DEFAULT 0,
    failed        INTEGER DEFAULT 0,
    skipped       INTEGER DEFAULT 0,
    current_index INTEGER DEFAULT 0,
    current_item_id TEXT,
    current_label TEXT,
    metadata_json TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (run_id, stage)
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                      INTEGER REFERENCES runs(id),
    phase                       TEXT NOT NULL,
    job_id                      TEXT,
    model                       TEXT NOT NULL,
    input_tokens                INTEGER DEFAULT 0,
    output_tokens               INTEGER DEFAULT 0,
    cache_creation_input_tokens INTEGER DEFAULT 0,
    cache_read_input_tokens     INTEGER DEFAULT 0,
    cost_usd                    REAL DEFAULT 0,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_stage_progress_run ON run_stage_progress(run_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_run ON llm_usage(run_id);

CREATE TABLE IF NOT EXISTS run_control (
    run_id          INTEGER PRIMARY KEY REFERENCES runs(id),
    requested_state TEXT NOT NULL DEFAULT 'running',
    reason          TEXT,
    updated_at      TEXT NOT NULL
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

APPLICATIONS_ADD_COLUMNS: list[tuple[str, str]] = [
    ("received_at", "TEXT"),
    ("last_response_at", "TEXT"),
    ("response_type", "TEXT"),
    ("response_subject", "TEXT"),
    ("response_snippet", "TEXT"),
    ("proof_level", "INTEGER NOT NULL DEFAULT 0"),
    ("proof_evidence", "TEXT"),
    ("last_checked_at", "TEXT"),
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


def _ensure_applications_columns(conn: sqlite3.Connection) -> None:
    """Additive migration for application outcome/proof-ladder columns."""
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(applications)")
    }
    for name, typ in APPLICATIONS_ADD_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {typ}")


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
        _ensure_applications_columns(conn)
        yield conn
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def upsert_new(conn: sqlite3.Connection, jobs: list[JobPosting]) -> list[JobPosting]:
    """Insert jobs we have not seen before. Returns the subset that was new.

    Newly scraped rows start with `score = NULL` per PRD §7.5 FR-SCO-01..05:
    a numeric score only exists after the LLM scorer runs with all three
    preconditions satisfied. Persisting a 0 placeholder would mix unscored
    rows into the "filtered / failed at score=0" bucket and lie to anyone
    reading the column directly.
    """
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
                None,
                None,
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
    proof_level = 1 if result.submitted else 0
    proof_evidence = []
    if result.submitted:
        proof_evidence.append({
            "level": proof_level,
            "source": "application",
            "confirmation_url": result.confirmation_url,
            "submitted": True,
            "at": _now(),
        })
    conn.execute(
        "INSERT OR REPLACE INTO applications(job_id, attempted_at, status, submitted, dry_run, "
        "needs_review_reason, error, screenshot_path, confirmation_url, proof_level, "
        "proof_evidence, last_checked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            job_id, _now(), result.status.value,
            int(result.submitted), int(result.dry_run),
            result.needs_review_reason, result.error,
            result.screenshot_path, result.confirmation_url,
            proof_level, json.dumps(proof_evidence), _now(),
        ),
    )


def jobs_with_submitted_application(conn: sqlite3.Connection) -> set[str]:
    """Return the set of job_ids that already have a real submitted
    application on file — bot OR manual mark. The pipeline must consult
    this set BEFORE every auto-apply attempt to avoid double-sending.

    Counts only rows with `submitted = 1`. Dry-run rows (submitted = 0,
    dry_run = 1) deliberately do NOT count — those are queued previews,
    not confirmed sends."""
    rows = conn.execute(
        "SELECT DISTINCT job_id FROM applications WHERE submitted = 1"
    ).fetchall()
    return {r["job_id"] for r in rows}


def mark_application_manually(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    note: str | None = None,
    channel: str = "manual",
) -> None:
    """Record that the operator applied to this job OUTSIDE the bot.

    Writes an `applications` row with submitted=1 + proof_level=1 + a
    proof_evidence entry tagged source="manual", and flips the seen_jobs
    status to APPLY_SUBMITTED. After this call the pipeline's apply step
    will skip the job on every future run (the same guard that protects
    against re-sending a bot-submitted application).

    Idempotent: re-running on the same job_id replaces the row but keeps
    the "manual" provenance tag. Note text, when set, is preserved in
    needs_review_reason so the dashboard / digest can surface it.
    """
    from .models import JobStatus

    evidence = [{
        "level": 1,
        "source": channel,
        "submitted": True,
        "note": note,
        "at": _now(),
    }]
    conn.execute(
        "INSERT OR REPLACE INTO applications(job_id, attempted_at, status, submitted, "
        "dry_run, needs_review_reason, error, screenshot_path, confirmation_url, "
        "proof_level, proof_evidence, last_checked_at) "
        "VALUES (?, ?, ?, 1, 0, ?, NULL, NULL, NULL, 1, ?, ?)",
        (
            job_id, _now(), JobStatus.APPLY_SUBMITTED.value,
            note, json.dumps(evidence), _now(),
        ),
    )
    conn.execute(
        "UPDATE seen_jobs SET status = ? WHERE id = ?",
        (JobStatus.APPLY_SUBMITTED.value, job_id),
    )


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO runs(started_at) VALUES (?)", (_now(),))
    run_id = cur.lastrowid  # type: ignore[assignment]
    conn.execute(
        "INSERT OR REPLACE INTO run_control(run_id, requested_state, reason, updated_at) "
        "VALUES (?, 'running', NULL, ?)",
        (run_id, _now()),
    )
    return run_id  # type: ignore[return-value]


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
    request_run_control(conn, run_id, "finished", reason="run completed")


def request_run_control(
    conn: sqlite3.Connection,
    run_id: int,
    requested_state: str,
    *,
    reason: str | None = None,
) -> None:
    if requested_state not in {"running", "paused", "stop_requested", "stopped", "finished"}:
        raise ValueError(f"unsupported run control state: {requested_state}")
    conn.execute(
        "INSERT OR REPLACE INTO run_control(run_id, requested_state, reason, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (run_id, requested_state, reason, _now()),
    )


def run_control_state(conn: sqlite3.Connection, run_id: int) -> dict[str, str | None]:
    row = conn.execute(
        "SELECT requested_state, reason, updated_at FROM run_control WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if not row:
        return {"requested_state": "running", "reason": None, "updated_at": None}
    return {
        "requested_state": row["requested_state"],
        "reason": row["reason"],
        "updated_at": row["updated_at"],
    }


def wait_while_paused(conn: sqlite3.Connection, run_id: int) -> bool:
    """Return False if the run should stop, True when execution may continue."""
    while True:
        state = run_control_state(conn, run_id)["requested_state"]
        if state in {"stop_requested", "stopped"}:
            return False
        if state != "paused":
            return True
        time.sleep(1)


def mark_run_stopped(conn: sqlite3.Connection, run_id: int, *, reason: str) -> None:
    row = conn.execute(
        "SELECT started_at, finished_at FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row and row["finished_at"] is None:
        summary = {
            "stopped": True,
            "stop_reason": reason,
        }
        conn.execute(
            "UPDATE runs SET finished_at = ?, n_errors = n_errors + 1, summary_json = ? "
            "WHERE id = ? AND finished_at IS NULL",
            (_now(), json.dumps(summary), run_id),
        )
    request_run_control(conn, run_id, "stopped", reason=reason)


def update_run_stage_progress(
    conn: sqlite3.Connection,
    run_id: int,
    stage: str,
    *,
    total: int | None = None,
    started: int | None = None,
    completed: int | None = None,
    failed: int | None = None,
    skipped: int | None = None,
    current_index: int | None = None,
    current_item_id: str | None = None,
    current_label: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Upsert live progress for one run stage.

    The dashboard reads this while the pipeline is running, so each write is
    deliberately small and autocommitted.
    """
    row = conn.execute(
        "SELECT * FROM run_stage_progress WHERE run_id = ? AND stage = ?",
        (run_id, stage),
    ).fetchone()
    values = {
        "total": 0,
        "started": 0,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "current_index": 0,
        "current_item_id": None,
        "current_label": None,
        "metadata_json": "{}",
    }
    if row:
        values.update({key: row[key] for key in values.keys()})
    updates = {
        "total": total,
        "started": started,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "current_index": current_index,
        "current_item_id": current_item_id,
        "current_label": current_label,
        "metadata_json": json.dumps(metadata or {}) if metadata is not None else None,
    }
    for key, value in updates.items():
        if value is not None:
            values[key] = value
    conn.execute(
        """
        INSERT OR REPLACE INTO run_stage_progress(
            run_id, stage, total, started, completed, failed, skipped,
            current_index, current_item_id, current_label, metadata_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, stage,
            values["total"], values["started"], values["completed"],
            values["failed"], values["skipped"], values["current_index"],
            values["current_item_id"], values["current_label"],
            values["metadata_json"], _now(),
        ),
    )


def run_stage_progress(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT stage, total, started, completed, failed, skipped, current_index,
               current_item_id, current_label, metadata_json, updated_at
        FROM run_stage_progress
        WHERE run_id = ?
        ORDER BY CASE stage
            WHEN 'scrape' THEN 1
            WHEN 'enrichment' THEN 2
            WHEN 'scoring' THEN 3
            WHEN 'generation' THEN 4
            WHEN 'tailored_rescore' THEN 5
            WHEN 'apply' THEN 6
            ELSE 99
        END, stage
        """,
        (run_id,),
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        out.append({
            "stage": row["stage"],
            "total": int(row["total"] or 0),
            "started": int(row["started"] or 0),
            "completed": int(row["completed"] or 0),
            "failed": int(row["failed"] or 0),
            "skipped": int(row["skipped"] or 0),
            "current_index": int(row["current_index"] or 0),
            "current_item_id": row["current_item_id"],
            "current_label": row["current_label"],
            "metadata": metadata if isinstance(metadata, dict) else {},
            "updated_at": row["updated_at"],
        })
    return out


_MODEL_PRICES_USD_PER_MTOK = {
    # Anthropic public Sonnet 4-family pricing: $3/M input, $15/M output.
    "sonnet-4": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "haiku-4.5": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10},
}


def estimate_llm_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    model_l = (model or "").lower()
    if "haiku" in model_l and "4" in model_l:
        prices = _MODEL_PRICES_USD_PER_MTOK["haiku-4.5"]
    else:
        prices = _MODEL_PRICES_USD_PER_MTOK["sonnet-4"]
    cost = (
        input_tokens * prices["input"]
        + output_tokens * prices["output"]
        + cache_creation_input_tokens * prices["cache_write"]
        + cache_read_input_tokens * prices["cache_read"]
    ) / 1_000_000
    return round(cost, 6)


def record_llm_usage(
    conn: sqlite3.Connection,
    *,
    run_id: int | None,
    phase: str,
    job_id: str | None,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> None:
    cost_usd = estimate_llm_cost_usd(
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
    )
    conn.execute(
        """
        INSERT INTO llm_usage(
            run_id, phase, job_id, model, input_tokens, output_tokens,
            cache_creation_input_tokens, cache_read_input_tokens, cost_usd, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, phase, job_id, model, input_tokens, output_tokens,
            cache_creation_input_tokens, cache_read_input_tokens, cost_usd, _now(),
        ),
    )


def llm_usage_summary(conn: sqlite3.Connection, run_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT phase, model, COUNT(*) AS calls,
               SUM(input_tokens) AS input_tokens,
               SUM(output_tokens) AS output_tokens,
               SUM(cache_creation_input_tokens) AS cache_creation_input_tokens,
               SUM(cache_read_input_tokens) AS cache_read_input_tokens,
               SUM(cost_usd) AS cost_usd
        FROM llm_usage
        WHERE run_id = ?
        GROUP BY phase, model
        ORDER BY phase, model
        """,
        (run_id,),
    ).fetchall()
    phases: list[dict] = []
    totals = {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cost_usd": 0.0,
    }
    for row in rows:
        item = {
            "phase": row["phase"],
            "model": row["model"],
            "calls": int(row["calls"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "cache_creation_input_tokens": int(row["cache_creation_input_tokens"] or 0),
            "cache_read_input_tokens": int(row["cache_read_input_tokens"] or 0),
            "cost_usd": float(row["cost_usd"] or 0),
        }
        phases.append(item)
        for key in totals:
            totals[key] += item[key]
    totals["cost_usd"] = round(float(totals["cost_usd"]), 6)
    return {"totals": totals, "phases": phases}


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


def scrub_stale_scores(conn: sqlite3.Connection) -> int:
    """PRD §7.5 FR-SCO-01..05: enforce the invariant that a numeric `score`
    cannot coexist with a violated precondition.

    A row was historically allowed to be scored when its raw_json carried a
    long listing-card snippet, even if the detail body was never fetched.
    Under the post-fix gate, those rows are mis-scored. This helper nulls
    their score columns, clears `scored_at`, and downgrades `status` to
    `cannot_score:no_body` so the next `jobbot enrich --backfill` plus
    `jobbot rescore --base` cycle can recover them honestly.

    Returns the number of rows scrubbed. Idempotent.
    """
    cannot_score = JobStatus.CANNOT_SCORE_NO_BODY.value
    scored = JobStatus.SCORED.value
    below = JobStatus.BELOW_THRESHOLD.value
    cur = conn.execute(
        "UPDATE seen_jobs "
        "SET score = NULL, "
        "    score_breakdown_json = NULL, "
        "    scored_at = NULL, "
        "    score_reason = CASE "
        "        WHEN status IN (?, ?) "
        "        THEN 'cannot_score:no_body (scrubbed: missed precondition)' "
        "        ELSE NULL END, "
        "    status = CASE WHEN status IN (?, ?) THEN ? ELSE status END "
        "WHERE score IS NOT NULL "
        "  AND (description_scraped IS NULL "
        "       OR description_scraped = 0 "
        "       OR description_word_count IS NULL "
        "       OR description_word_count < ?)",
        (scored, below, scored, below, cannot_score, 100),
    )
    return cur.rowcount


def jobs_needing_base_rescore(
    conn: sqlite3.Connection, limit: int,
) -> list[JobPosting]:
    """Rows that pass the preconditions but never received a base score —
    typically because they pre-date the scorer's enrichment gate, or
    `scrub_stale_scores` just nulled a previously-bogus score.

    Returns hydrated JobPosting objects with `description` swapped in from
    `description_full` so the prompt sees the real body, not the listing
    snippet. Ordered most-recent-first so backfill prioritises fresh
    postings the user might still want to apply to.
    """
    # Includes legacy primary/base-CV status names so old rows still flow
    # through the rescore once the corpus profile has been fixed.
    rows = conn.execute(
        "SELECT raw_json, description_full FROM seen_jobs "
        "WHERE raw_json IS NOT NULL "
        "  AND description_scraped = 1 "
        "  AND description_word_count >= 100 "
        "  AND score IS NULL "
        "  AND status IN (?, ?, ?, ?) "
        "ORDER BY first_seen_at DESC "
        "LIMIT ?",
        (
            JobStatus.SCRAPED.value,
            JobStatus.CANNOT_SCORE_NO_BODY.value,
            JobStatus.CANNOT_SCORE_NO_PRIMARY_CV.value,
            JobStatus.CANNOT_SCORE_NO_BASE_CV.value,
            limit,
        ),
    ).fetchall()
    out: list[JobPosting] = []
    for row in rows:
        try:
            job = JobPosting.model_validate_json(row["raw_json"])
        except Exception:
            continue
        if row["description_full"]:
            job = job.model_copy(update={"description": row["description_full"]})
        out.append(job)
    return out


def force_clear_base_scores(conn: sqlite3.Connection) -> tuple[int, int]:
    """Null base-score columns for every row that currently carries a score,
    in preparation for a full `rescore --base --force` pass.

    Two buckets:
      - SCORED / BELOW_THRESHOLD rows are downgraded to SCRAPED so the
        existing rescore queue picks them up.
      - Later-stage rows (GENERATED, APPLY_*, EMPLOYER_*, REJECTED,
        INTERVIEW_INVITED) keep their status — we don't want to undo
        downstream pipeline progress just to refresh a score. Their score
        gets re-set in place by the force rescore loop.

    Returns (early_cleared, late_cleared) row counts. Idempotent.
    """
    scored = JobStatus.SCORED.value
    below = JobStatus.BELOW_THRESHOLD.value
    scraped = JobStatus.SCRAPED.value
    # First: downgrade SCORED/BELOW_THRESHOLD to SCRAPED and null score cols.
    early = conn.execute(
        "UPDATE seen_jobs SET "
        "  score = NULL, "
        "  score_breakdown_json = NULL, "
        "  scored_at = NULL, "
        "  score_reason = 'cleared for base CV rescore', "
        "  status = ? "
        "WHERE score IS NOT NULL AND status IN (?, ?)",
        (scraped, scored, below),
    ).rowcount
    # Second: null score cols for late-stage rows but keep their status.
    late = conn.execute(
        "UPDATE seen_jobs SET "
        "  score = NULL, "
        "  score_breakdown_json = NULL, "
        "  scored_at = NULL, "
        "  score_reason = 'cleared for base CV rescore' "
        "WHERE score IS NOT NULL",
        (),
    ).rowcount
    return early, late


def jobs_needing_base_rescore_force(
    conn: sqlite3.Connection, limit: int,
) -> list[tuple[JobPosting, str]]:
    """Force-mode counterpart to `jobs_needing_base_rescore`. Returns every
    row passing the preconditions (real body, scraped, >=100 words) with a
    NULL base score, regardless of status — except FILTERED, which the
    heuristic rejected for non-CV reasons and should never reach the LLM.

    Returns (job, current_status) tuples so the caller can decide whether
    to update status or just refresh the score column for late-stage rows.
    """
    rows = conn.execute(
        "SELECT raw_json, description_full, status FROM seen_jobs "
        "WHERE raw_json IS NOT NULL "
        "  AND description_scraped = 1 "
        "  AND description_word_count >= 100 "
        "  AND score IS NULL "
        "  AND status != ? "
        "ORDER BY first_seen_at DESC "
        "LIMIT ?",
        (JobStatus.FILTERED.value, limit),
    ).fetchall()
    out: list[tuple[JobPosting, str]] = []
    for row in rows:
        try:
            job = JobPosting.model_validate_json(row["raw_json"])
        except Exception:
            continue
        if row["description_full"]:
            job = job.model_copy(update={"description": row["description_full"]})
        out.append((job, row["status"]))
    return out


def update_base_score_only(
    conn: sqlite3.Connection, job_id: str, score: int | None, reason: str,
) -> None:
    """Refresh the base score (score + score_reason + scored_at) without
    touching `status`. Used by the force-rescore loop so a row already in
    a late-stage status (GENERATED, APPLY_*) doesn't get knocked back to
    SCORED/BELOW_THRESHOLD. `score=None` records a cannot_score reason on
    a late-stage row without demoting its status."""
    scored_at = _now() if score is not None else None
    conn.execute(
        "UPDATE seen_jobs SET score = ?, score_reason = ?, scored_at = ? "
        "WHERE id = ?",
        (score, reason, scored_at, job_id),
    )


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
