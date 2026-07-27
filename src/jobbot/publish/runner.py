"""Orchestrate one publish pass: build site -> Downloads export -> git push."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import structlog

from ..config import REPO_ROOT, Config
from ..state import connect
from .downloads import export_documents
from .pages import DEFAULT_PAGES_DIR, clear_site_tree, commit_and_push, ensure_pages_repo
from .site import build_site

log = structlog.get_logger()

# Fallback build location when no pages repo is configured (gitignored).
LOCAL_SITE_DIR = REPO_ROOT / "site"


def publish_all(
    config: Config,
    *,
    push: bool = True,
    downloads: bool = True,
    db_path: Path | None = None,
    repo_root: Path = REPO_ROOT,
    now: datetime | None = None,
) -> dict:
    """Run one full publish pass. Returns a summary dict for the CLI."""
    now = now or datetime.now(timezone.utc)
    pub = config.publish
    summary: dict = {
        "site_dir": None, "n_jobs": 0, "n_docs": 0,
        "downloads_created": 0, "git_result": "skipped",
    }
    if not pub.enabled:
        summary["git_result"] = "disabled"
        return summary

    remote = (pub.pages_repo_url or "").strip()
    if remote:
        site_dir = (Path(pub.pages_repo_dir).expanduser()
                    if pub.pages_repo_dir.strip() else DEFAULT_PAGES_DIR)
        ensure_pages_repo(site_dir, remote, pub.pages_branch)
        clear_site_tree(site_dir)
    else:
        site_dir = LOCAL_SITE_DIR
    summary["site_dir"] = str(site_dir)

    with connect(db_path) as conn:
        report = build_site(conn, config, site_dir, repo_root=repo_root, now=now)
        summary["n_jobs"] = report.n_jobs
        summary["n_docs"] = report.n_docs_copied
        if downloads and pub.downloads_enabled:
            created = export_documents(conn, config, repo_root=repo_root)
            summary["downloads_created"] = len(created)

    if remote:
        summary["git_result"] = commit_and_push(
            site_dir, pub.pages_branch, push=push,
            message=f"site: daily publish {now.date().isoformat()}",
        )
    log.info("publish_done", **summary)
    return summary
