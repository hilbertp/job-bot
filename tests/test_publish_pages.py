"""Git publish step, exercised against a local bare repo (no network)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from jobbot.publish.pages import clear_site_tree, commit_and_push, ensure_pages_repo


def _bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)],
                   check=True, capture_output=True)
    return remote


def test_publish_to_empty_remote_then_no_change_then_update(tmp_path: Path):
    remote = _bare_remote(tmp_path)
    repo_dir = tmp_path / "pages"

    # First publish: clone of an empty remote falls back to init-a-branch.
    ensure_pages_repo(repo_dir, str(remote), "main")
    (repo_dir / "index.html").write_text("<h1>v1</h1>")
    assert commit_and_push(repo_dir, "main") == "pushed"

    # Same content again: nothing to commit.
    ensure_pages_repo(repo_dir, str(remote), "main")
    (repo_dir / "index.html").write_text("<h1>v1</h1>")
    assert commit_and_push(repo_dir, "main") == "no_changes"

    # Changed content publishes a second commit.
    ensure_pages_repo(repo_dir, str(remote), "main")
    clear_site_tree(repo_dir)
    (repo_dir / "index.html").write_text("<h1>v2</h1>")
    assert commit_and_push(repo_dir, "main") == "pushed"

    log = subprocess.run(
        ["git", "log", "--oneline", "main"], cwd=remote,
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert len(log) == 2


def test_clear_site_tree_preserves_git_and_cname(tmp_path: Path):
    remote = _bare_remote(tmp_path)
    repo_dir = tmp_path / "pages"
    ensure_pages_repo(repo_dir, str(remote), "main")
    (repo_dir / "CNAME").write_text("jobs.example.com")
    (repo_dir / "stale.html").write_text("x")
    (repo_dir / "docs").mkdir()
    (repo_dir / "docs" / "old.pdf").write_bytes(b"x")

    clear_site_tree(repo_dir)
    assert (repo_dir / ".git").is_dir()
    assert (repo_dir / "CNAME").exists()
    assert not (repo_dir / "stale.html").exists()
    assert not (repo_dir / "docs").exists()


def test_remote_url_change_reclones(tmp_path: Path):
    remote_a = tmp_path / "a.git"
    remote_b = tmp_path / "b.git"
    for r in (remote_a, remote_b):
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(r)],
                       check=True, capture_output=True)
    repo_dir = tmp_path / "pages"

    ensure_pages_repo(repo_dir, str(remote_a), "main")
    (repo_dir / "index.html").write_text("site A")
    commit_and_push(repo_dir, "main")

    # Pointing publish at a different remote must not push into remote A.
    ensure_pages_repo(repo_dir, str(remote_b), "main")
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_dir,
                            capture_output=True, text=True).stdout.strip()
    assert origin == str(remote_b)
    assert not (repo_dir / "index.html").exists()  # fresh clone of empty B


def test_gh_pages_branch_on_code_repo_is_orphan_site_only(tmp_path: Path):
    # A "code repo": main branch with source files already pushed.
    remote = _bare_remote(tmp_path)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--initial-branch=main", str(seed)],
                   check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed,
                   check=True, capture_output=True)
    (seed / "src").mkdir()
    (seed / "src" / "app.py").write_text("print('code')\n")
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-m", "code"], cwd=seed, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=seed,
                   check=True, capture_output=True)

    repo_dir = tmp_path / "pages"
    ensure_pages_repo(repo_dir, str(remote), "gh-pages")
    clear_site_tree(repo_dir)
    (repo_dir / "index.html").write_text("<h1>site</h1>")
    assert commit_and_push(repo_dir, "gh-pages") == "pushed"

    files = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "gh-pages"], cwd=remote,
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert files == ["index.html"]  # no code files on the site branch
    history = subprocess.run(
        ["git", "log", "--oneline", "gh-pages"], cwd=remote,
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert len(history) == 1  # orphan lineage, detached from code history


def test_no_push_commits_locally_only(tmp_path: Path):
    remote = _bare_remote(tmp_path)
    repo_dir = tmp_path / "pages"
    ensure_pages_repo(repo_dir, str(remote), "main")
    (repo_dir / "index.html").write_text("<h1>draft</h1>")
    assert commit_and_push(repo_dir, "main", push=False) == "committed"
    remote_heads = subprocess.run(
        ["git", "ls-remote", "--heads", str(remote)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert remote_heads == ""
