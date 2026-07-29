"""Logging hygiene for scheduled runs.

Unconfigured structlog renders colored output and rich tracebacks with
full local-variable dumps. Under launchd that lands in logs/*.log: one
failing run once wrote ~150 MB of ANSI panels (a 12 GB log file after a
few weeks). Two counter-measures:

- configure_logging(): TTY-aware structlog setup. Interactive terminals
  keep the pretty colored renderer; anything else (launchd log files,
  pipes, CI) gets plain text and compact plain tracebacks.
- trim_oversized_logs(): safety net that truncates any logs/*.log that
  still grew past the cap. launchd opens StandardOutPath with O_APPEND,
  so truncating in place is safe even mid-run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import structlog

from .config import REPO_ROOT

MAX_LOG_BYTES = 100 * 1024 * 1024  # 100 MB


def configure_logging(stream=None) -> None:
    stream = stream if stream is not None else sys.stdout
    pretty = hasattr(stream, "isatty") and stream.isatty()
    renderer = structlog.dev.ConsoleRenderer(
        colors=pretty,
        exception_formatter=structlog.dev.plain_traceback,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=True),
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(stream),
        cache_logger_on_first_use=False,
    )


def trim_oversized_logs(logs_dir: Path | None = None,
                        max_bytes: int = MAX_LOG_BYTES) -> list[Path]:
    """Truncate any *.log over max_bytes. Returns the trimmed paths."""
    logs_dir = logs_dir or REPO_ROOT / "logs"
    trimmed: list[Path] = []
    if not logs_dir.is_dir():
        return trimmed
    log = structlog.get_logger()
    for path in sorted(logs_dir.glob("*.log")):
        try:
            size = path.stat().st_size
            if size <= max_bytes:
                continue
            os.truncate(path, 0)
            trimmed.append(path)
            log.info("log_truncated", file=str(path), old_size_bytes=size)
        except OSError as exc:
            log.warning("log_trim_failed", file=str(path), error=str(exc))
    return trimmed
