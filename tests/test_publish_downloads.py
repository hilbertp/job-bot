"""Downloads export: each generated package copied exactly once."""
from __future__ import annotations

from pathlib import Path

import pytest

from jobbot.config import Config
from jobbot.models import JobPosting, JobStatus
from jobbot.publish.downloads import export_documents
from jobbot.state import connect, update_status, upsert_new


@pytest.fixture()
def db(tmp_path: Path):
    with connect(tmp_path / "test.db") as conn:
        yield conn


def _seed_generated(conn, tmp_path: Path) -> JobPosting:
    job = JobPosting(
        id="remotive_0000000000000001", source="remotive",
        title="Senior Product Manager", company="Acme GmbH",
        url="https://example.com/jobs/1", description="word " * 150,
    )
    upsert_new(conn, [job])
    out_dir = tmp_path / "output" / "pkg1"
    out_dir.mkdir(parents=True)
    (out_dir / "cv.pdf").write_bytes(b"%PDF cv")
    (out_dir / "cover_letter.pdf").write_bytes(b"%PDF cl")
    (out_dir / "application_package.pdf").write_bytes(b"%PDF pkg")
    update_status(conn, job.id, JobStatus.GENERATED, output_dir=str(out_dir))
    return job


def test_export_copies_once_then_skips(db, tmp_path: Path):
    _seed_generated(db, tmp_path)
    cfg = Config()
    cfg.publish.downloads_dir = str(tmp_path / "Downloads" / "jobbot")

    created = export_documents(db, cfg, repo_root=tmp_path)
    assert len(created) == 1
    folder = created[0]
    assert folder.name == "acme-gmbh__senior-product-manager__00000001"
    assert (folder / "cv.pdf").read_bytes() == b"%PDF cv"
    assert (folder / "cover_letter.pdf").exists()
    assert (folder / "application_package.pdf").exists()

    # Second pass: folder exists, nothing new is exported.
    assert export_documents(db, cfg, repo_root=tmp_path) == []


def test_export_ignores_rows_without_docs(db, tmp_path: Path):
    job = JobPosting(
        id="remotive_0000000000000002", source="remotive",
        title="PM", company="NoDocs Inc",
        url="https://example.com/jobs/2", description="x",
    )
    upsert_new(db, [job])
    cfg = Config()
    cfg.publish.downloads_dir = str(tmp_path / "dl")
    assert export_documents(db, cfg, repo_root=tmp_path) == []


def test_regenerated_docs_replace_the_exported_copy(db, tmp_path: Path):
    """A rebuild must reach the folder the user actually opens.

    The exporter skipped any folder that already existed, so after today's
    CVs were regenerated from four pages to two, ~/Downloads/jobbot still
    held the four-page copies and nothing said so.
    """
    import os
    import time

    _seed_generated(db, tmp_path)
    out_dir = tmp_path / "output" / "pkg1"
    cfg = Config()
    cfg.publish.downloads_dir = str(tmp_path / "Downloads" / "jobbot")

    folder = export_documents(db, cfg, repo_root=tmp_path)[0]
    assert (folder / "cv.pdf").read_bytes() == b"%PDF cv"

    # Age the exported copy, the way a copy taken this morning would be, then
    # regenerate the source now. Backdating the target rather than
    # future-dating the source keeps the ordering physically possible: a copy
    # is always written after the file it came from.
    old = time.time() - 3600
    os.utime(folder / "cv.pdf", (old, old))
    src = out_dir / "cv.pdf"
    src.write_bytes(b"%PDF cv REBUILT two pages")

    created = export_documents(db, cfg, repo_root=tmp_path)
    assert created == [folder]
    assert (folder / "cv.pdf").read_bytes() == b"%PDF cv REBUILT two pages"

    # And it settles again: no further copying once it is current.
    assert export_documents(db, cfg, repo_root=tmp_path) == []
