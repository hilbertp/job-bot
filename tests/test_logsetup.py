"""Logging hygiene: plain non-TTY output and oversized-log trimming."""
from __future__ import annotations

import io
from pathlib import Path

import structlog

from jobbot.logsetup import configure_logging, trim_oversized_logs


def _reset_structlog():
    structlog.reset_defaults()


def test_non_tty_output_is_plain_and_compact():
    buf = io.StringIO()  # StringIO.isatty() is False
    configure_logging(buf)
    try:
        log = structlog.get_logger()
        try:
            raise ValueError("boom with a JobPosting local " + "x" * 50)
        except ValueError:
            log.error("scoring_error", job_id="abc123", exc_info=True)
        out = buf.getvalue()
        assert "scoring_error" in out
        assert "job_id" in out
        assert "\x1b[" not in out          # no ANSI color codes
        assert "│" not in out          # no box-drawing panels
        assert "ValueError" in out          # plain traceback retained
        # locals are NOT dumped: a plain traceback for this snippet stays
        # small, the rich-with-locals rendering ran to tens of KB.
        assert len(out) < 4000
    finally:
        _reset_structlog()


def test_tty_stream_keeps_colors():
    class FakeTty(io.StringIO):
        def isatty(self):
            return True

    buf = FakeTty()
    configure_logging(buf)
    try:
        structlog.get_logger().info("hello", key="value")
        assert "\x1b[" in buf.getvalue()
    finally:
        _reset_structlog()


def test_trim_oversized_logs(tmp_path: Path):
    big = tmp_path / "scrape.out.log"
    big.write_bytes(b"x" * 2048)
    small = tmp_path / "digest.err.log"
    small.write_bytes(b"y" * 10)
    other = tmp_path / "notes.txt"
    other.write_bytes(b"z" * 2048)

    trimmed = trim_oversized_logs(tmp_path, max_bytes=1024)

    assert trimmed == [big]
    assert big.stat().st_size == 0
    assert small.stat().st_size == 10
    assert other.stat().st_size == 2048  # only *.log files are touched
