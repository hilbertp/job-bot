"""HTTP server for the local dashboard. Bound to localhost only.

See ../dashboard/__init__.py for route list and PRD §7.10.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_legacy_dashboard_module():
    """Load src/jobbot/dashboard.py despite the dashboard package name collision."""
    module_path = Path(__file__).resolve().parents[1] / "dashboard.py"
    spec = importlib.util.spec_from_file_location("jobbot._legacy_dashboard", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load dashboard module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(host: str = "127.0.0.1", port: int = 5001) -> None:
    """Start the read-only dashboard server. Blocks until Ctrl+C."""
    dashboard_module = _load_legacy_dashboard_module()
    dashboard_module.run(host=host, port=port, debug=False)
