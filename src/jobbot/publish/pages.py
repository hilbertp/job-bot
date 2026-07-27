"""Commit + push the built site to the GitHub Pages repo.

The pages working copy is machine-owned, generated content: every publish
rebuilds the full tree, and the local copy is forced back onto the remote
branch before building so a manual edit on GitHub never causes a conflict.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import structlog

log = structlog.get_logger()

DEFAULT_PAGES_DIR = Path.home() / ".jobbot" / "pages-repo"

# Files at the repo root that a publish must never delete.
_PRESERVE = {".git", "CNAME"}


class PagesPublishError(RuntimeError):
    pass


def _git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args], cwd=repo_dir, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise PagesPublishError(
            f"git {' '.join(args)} failed in {repo_dir}: {proc.stderr.strip()}"
        )
    return proc


def ensure_pages_repo(repo_dir: Path, remote_url: str, branch: str) -> None:
    """Clone the pages repo (or sync an existing working copy to origin)."""
    if not (repo_dir / ".git").is_dir():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["git", "clone", "--branch", branch, remote_url, str(repo_dir)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            # Fresh/empty remote has no branch to clone; start one locally.
            proc2 = subprocess.run(
                ["git", "clone", remote_url, str(repo_dir)],
                capture_output=True, text=True,
            )
            if proc2.returncode != 0:
                raise PagesPublishError(
                    f"git clone {remote_url} failed: {proc.stderr.strip()} / "
                    f"{proc2.stderr.strip()}"
                )
            _git(repo_dir, "checkout", "-B", branch)
        return

    _git(repo_dir, "fetch", "origin")
    _git(repo_dir, "checkout", "-B", branch)
    # Generated content only: origin wins over any local drift.
    remote_branch = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{branch}"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if remote_branch.returncode == 0:
        _git(repo_dir, "reset", "--hard", f"origin/{branch}")


def clear_site_tree(repo_dir: Path) -> None:
    """Remove everything except .git/CNAME so deleted jobs disappear."""
    for entry in repo_dir.iterdir():
        if entry.name in _PRESERVE:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def commit_and_push(repo_dir: Path, branch: str, *, push: bool = True,
                    message: str | None = None) -> str:
    """Commit the current tree; push when there is something new.

    Returns "no_changes", "committed", or "pushed".
    """
    _git(repo_dir, "add", "-A")
    status = _git(repo_dir, "status", "--porcelain").stdout.strip()
    if not status:
        log.info("pages_publish_no_changes", dir=str(repo_dir))
        return "no_changes"
    _git(repo_dir, "-c", "user.name=jobbot", "-c", "user.email=jobbot@localhost",
         "commit", "-m", message or "site: automated daily publish")
    if not push:
        return "committed"
    _git(repo_dir, "push", "origin", branch)
    log.info("pages_published", dir=str(repo_dir), branch=branch)
    return "pushed"
