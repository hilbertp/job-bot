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
