"""LLM invocation backends.

Two ways to reach Claude:

- "api" (default): the Anthropic Messages API with ANTHROPIC_API_KEY from
  .env. Billed per token against console.anthropic.com credits.
- "claude_cli": the locally installed Claude Code CLI in headless print
  mode (`claude -p`). Uses the CLI's own login, so calls draw on the
  user's Claude subscription (Pro/Max) limits instead of API credits.

Select via `llm_backend` in data/config.yaml, or override per-process with
the JOBBOT_LLM_BACKEND env var. The CLI binary is resolved from
JOBBOT_CLAUDE_CLI, then `claude_cli_path` in config, then $PATH; launchd
jobs run with a minimal PATH, so config should carry the absolute path.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import anthropic
import structlog

from .config import Secrets, load_config

log = structlog.get_logger()

DEFAULT_MODEL = "claude-sonnet-4-6"


class LlmError(RuntimeError):
    """A backend-level failure (process, transport, or malformed reply)."""


@dataclass
class LlmResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def usage(self) -> "LlmResponse":
        # Shape-compatible with the SDK message's .usage for the token
        # recorder in scoring._record_usage_if_present.
        return self


_backend_cache: str | None = None
_cli_path_cache: str | None = None


def _reset_cache() -> None:
    """Test hook: forget the resolved backend + CLI path."""
    global _backend_cache, _cli_path_cache
    _backend_cache = None
    _cli_path_cache = None


def resolve_backend() -> str:
    global _backend_cache
    env = os.environ.get("JOBBOT_LLM_BACKEND", "").strip()
    if env:
        return env
    if _backend_cache is None:
        _backend_cache = load_config().llm_backend
    return _backend_cache


def _resolve_cli_path() -> str:
    global _cli_path_cache
    env = os.environ.get("JOBBOT_CLAUDE_CLI", "").strip()
    if env:
        return env
    if _cli_path_cache is None:
        configured = (load_config().claude_cli_path or "").strip()
        _cli_path_cache = configured or shutil.which("claude") or ""
    if not _cli_path_cache:
        raise LlmError(
            "llm_backend is 'claude_cli' but no claude binary was found; "
            "set claude_cli_path in data/config.yaml to the absolute path "
            "(e.g. the output of `which claude`)."
        )
    return _cli_path_cache


def complete(
    secrets: Secrets,
    *,
    system: str,
    user: str,
    max_tokens: int,
    model: str = DEFAULT_MODEL,
    timeout_s: int = 600,
) -> LlmResponse:
    """One single-turn completion via the configured backend."""
    if resolve_backend() == "claude_cli":
        return _complete_cli(system=system, user=user, model=model,
                             timeout_s=timeout_s)
    return _complete_api(secrets, system=system, user=user,
                         max_tokens=max_tokens, model=model)


def _complete_api(secrets: Secrets, *, system: str, user: str,
                  max_tokens: int, model: str) -> LlmResponse:
    client = anthropic.Anthropic(api_key=secrets.anthropic_api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    usage = getattr(msg, "usage", None)

    def _u(name: str) -> int:
        try:
            return int(getattr(usage, name, 0) or 0)
        except (TypeError, ValueError):
            return 0

    return LlmResponse(
        text="".join(b.text for b in msg.content if b.type == "text"),
        input_tokens=_u("input_tokens"),
        output_tokens=_u("output_tokens"),
        cache_creation_input_tokens=_u("cache_creation_input_tokens"),
        cache_read_input_tokens=_u("cache_read_input_tokens"),
    )


def _complete_cli(*, system: str, user: str, model: str,
                  timeout_s: int) -> LlmResponse:
    cli = _resolve_cli_path()
    env = os.environ.copy()
    # The whole point of this backend is the CLI's subscription login;
    # an inherited API key would silently re-route billing to credits
    # (or fail with the very credit error this backend works around).
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    # launchd PATH is minimal; the nvm-installed CLI needs its own bin
    # dir (for node) on PATH.
    env["PATH"] = f"{Path(cli).parent}:{env.get('PATH', '')}"
    # Claude Code enables extended thinking by default; the API backend
    # never did. Measured on real scoring calls: ~2,000 output tokens and
    # ~38s per posting with thinking vs ~500 tokens / ~12s without, at
    # equal scores. Thinking off keeps scores calibrated to the API-era
    # scorer, roughly triples throughput, and stretches Max-plan limits.
    env["MAX_THINKING_TOKENS"] = "0"

    cmd = [
        cli, "-p",
        "--model", model,
        "--system-prompt", system,
        "--output-format", "json",
    ]
    try:
        # Neutral cwd: run outside the repo so the CLI does not load this
        # project's CLAUDE.md / settings into every scoring call.
        proc = subprocess.run(
            cmd, input=user, env=env, capture_output=True, text=True,
            timeout=timeout_s, cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired as exc:
        raise LlmError(f"claude -p timed out after {timeout_s}s") from exc
    if proc.returncode != 0:
        raise LlmError(
            f"claude -p exited {proc.returncode}: {proc.stderr.strip()[-500:]}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise LlmError(
            f"claude -p returned non-JSON output: {proc.stdout[:300]!r}"
        ) from exc
    if data.get("is_error"):
        raise LlmError(f"claude -p reported an error: {data.get('result', '')[:500]}")
    usage = data.get("usage") or {}

    def _u(name: str) -> int:
        try:
            return int(usage.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0

    return LlmResponse(
        text=str(data.get("result", "")),
        input_tokens=_u("input_tokens"),
        output_tokens=_u("output_tokens"),
        cache_creation_input_tokens=_u("cache_creation_input_tokens"),
        cache_read_input_tokens=_u("cache_read_input_tokens"),
    )
