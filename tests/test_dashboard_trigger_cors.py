"""CORS for the static site's Run-now button -> local trigger endpoint."""
from __future__ import annotations

import pytest

from jobbot.dashboard.server import _load_legacy_dashboard_module

dashboard = _load_legacy_dashboard_module()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(dashboard, "_pages_origin",
                        lambda: "https://hilbertp.github.io")
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as c:
        yield c


def test_preflight_from_pages_origin_gets_cors_and_pna_headers(client):
    resp = client.options(
        "/api/runs/trigger",
        headers={
            "Origin": "https://hilbertp.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "https://hilbertp.github.io"
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    # Chromium requires this for public-site -> localhost requests.
    assert resp.headers["Access-Control-Allow-Private-Network"] == "true"


def test_preflight_from_other_origin_gets_no_cors_headers(client):
    resp = client.options(
        "/api/runs/trigger",
        headers={"Origin": "https://evil.example"},
    )
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_other_api_routes_get_no_cors_headers(client):
    resp = client.get("/api/runs", headers={"Origin": "https://hilbertp.github.io"})
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_pages_origin_derived_from_repo_url(monkeypatch):
    class Pub:
        pages_repo_url = "https://github.com/HilbertP/job-bot.git"

    class Cfg:
        publish = Pub()

    import jobbot.config
    monkeypatch.setattr(jobbot.config, "load_config", lambda: Cfg())
    assert dashboard._pages_origin() == "https://hilbertp.github.io"

    Pub.pages_repo_url = ""
    assert dashboard._pages_origin() == ""
