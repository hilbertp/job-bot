"""Copy generated application documents into the user's Downloads folder.

Each generated job gets one folder named <company>__<title>__<id-suffix>;
a folder that already exists is treated as exported and skipped, so daily
runs only add the newly generated packages.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import structlog

from ..config import REPO_ROOT, Config
from .site import DOC_FILENAMES, resolve_output_dir

log = structlog.get_logger()

DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads" / "jobbot"


def _slug(s: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip()).strip("-").lower()
    return s[:max_len] or "unknown"


def downloads_root(config: Config) -> Path:
    configured = (config.publish.downloads_dir or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_DOWNLOADS_DIR


def export_documents(
    conn: sqlite3.Connection,
    config: Config,
    *,
    repo_root: Path = REPO_ROOT,
) -> list[Path]:
    """Export every generated package that is not in Downloads yet.

    Returns the list of newly created per-job folders.
    """
    root = downloads_root(config)
    rows = conn.execute(
        "SELECT id, company, title, output_dir FROM seen_jobs"
        " WHERE output_dir IS NOT NULL"
    ).fetchall()

    created: list[Path] = []
    for row in rows:
        out_dir = resolve_output_dir(row["output_dir"], repo_root)
        if out_dir is None:
            continue
        files = [name for name in DOC_FILENAMES if (out_dir / name).is_file()]
        if not files:
            continue
        target = root / f"{_slug(row['company'])}__{_slug(row['title'])}__{row['id'][-8:]}"
        if target.exists():
            continue  # already exported on a previous run
        target.mkdir(parents=True)
        for name in files:
            shutil.copyfile(out_dir / name, target / name)
        created.append(target)

    if created:
        log.info("downloads_exported", n=len(created), root=str(root))
    return created
