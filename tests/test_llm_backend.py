"""LLM backend dispatch: API vs claude_cli (subscription limits)."""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

import jobbot.llm as llm
from jobbot.config import Secrets


def _secrets() -> Secrets:
    return Secrets(
        anthropic_api_key="sk-ant-test",
        gmail_address="x@example.com",
        gmail_app_password="pw",
        notify_to="x@example.com",
    )


@pytest.fixture(autouse=True)
def _fresh_cache():
    llm._reset_cache()
    yield
    llm._reset_cache()


def test_backend_env_override(monkeypatch):
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "claude_cli")
    assert llm.resolve_backend() == "claude_cli"
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "api")
    assert llm.resolve_backend() == "api"


def test_api_backend_parses_text_and_usage(monkeypatch):
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "api")
    fake_msg = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"score": 80}')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                              cache_creation_input_tokens=0,
                              cache_read_input_tokens=0),
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: fake_msg))
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: fake_client)

    resp = llm.complete(_secrets(), system="sys", user="user", max_tokens=800)
    assert resp.text == '{"score": 80}'
    assert resp.input_tokens == 100
    assert resp.usage.output_tokens == 20  # .usage shim for the recorder


def test_cli_backend_strips_api_key_and_parses_json(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "claude_cli")
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\n")
    monkeypatch.setenv("JOBBOT_CLAUDE_CLI", str(cli))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-be-stripped")

    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["env"] = kw["env"]
        captured["input"] = kw["input"]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({
            "type": "result", "is_error": False,
            "result": '{"score": 91}',
            "usage": {"input_tokens": 42, "output_tokens": 7},
        }), stderr="")

    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    resp = llm.complete(_secrets(), system="rubric", user="the job",
                        max_tokens=800)

    assert resp.text == '{"score": 91}'
    assert resp.input_tokens == 42
    # Billing isolation: the child must not inherit the API key, or the
    # CLI would silently bill credits instead of the subscription.
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    # nvm bin dir prepended so the CLI's node is resolvable under launchd.
    assert captured["env"]["PATH"].startswith(str(tmp_path))
    assert captured["cmd"][:2] == [str(cli), "-p"]
    assert "rubric" in captured["cmd"]  # --system-prompt value
    assert captured["input"] == "the job"


def test_cli_backend_nonzero_exit_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "claude_cli")
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\n")
    monkeypatch.setenv("JOBBOT_CLAUDE_CLI", str(cli))
    monkeypatch.setattr(llm.subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, stdout="",
                                                    stderr="usage limit"))
    with pytest.raises(llm.LlmError, match="usage limit"):
        llm.complete(_secrets(), system="s", user="u", max_tokens=10)


def test_cli_backend_error_payload_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBBOT_LLM_BACKEND", "claude_cli")
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\n")
    monkeypatch.setenv("JOBBOT_CLAUDE_CLI", str(cli))
    monkeypatch.setattr(llm.subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({
                            "is_error": True, "result": "boom"}), stderr=""))
    with pytest.raises(llm.LlmError, match="boom"):
        llm.complete(_secrets(), system="s", user="u", max_tokens=10)


def test_scorer_goes_through_backend(monkeypatch):
    """scoring._invoke_scorer must route through llm.complete."""
    from jobbot import scoring

    monkeypatch.setattr(
        scoring, "llm_complete",
        lambda *a, **kw: llm.LlmResponse(text=json.dumps({
            "score": 77, "reason": "solid fit",
            "breakdown": {"role_match": 80, "skills_match": 75,
                          "location_remote_fit": 90, "seniority_fit": 70},
        })),
    )
    result = scoring._invoke_scorer(_secrets(), "user msg", run_id=None)
    assert result.score == 77
    assert result.breakdown == {"role": 80, "skills": 75,
                                "location": 90, "seniority": 70}
