"""Shared test isolation.

The pipeline serialises runs with a file lock in the system temp dir, which
the test process shares with the real scheduled runs. Running pytest while a
run was in flight therefore made 18 pipeline tests fail: `run_once()` found
the live run's lock, returned "already running", and every assertion about
scored rows came up empty. Point the lock somewhere private for the whole
session so the suite's result never depends on what the Mac is doing.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_run_lock(tmp_path_factory):
    import os

    lock_dir = tmp_path_factory.mktemp("run-lock")
    prev = os.environ.get("JOBBOT_RUN_LOCK_DIR")
    os.environ["JOBBOT_RUN_LOCK_DIR"] = str(lock_dir)
    yield
    if prev is None:
        os.environ.pop("JOBBOT_RUN_LOCK_DIR", None)
    else:
        os.environ["JOBBOT_RUN_LOCK_DIR"] = prev
