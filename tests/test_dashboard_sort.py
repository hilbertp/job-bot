"""Sort UX on the dashboard.

Pins:
  - Stage 2 (match-score table) defaults to score-desc on page load so
    the user's highest-fit jobs land at the top without clicking.
  - Stage 3 (tailored shortlist) exposes sort controls covering base
    score, tailored score, the tailoring delta, and tie-breakers, with
    "best known score" as the default.
"""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from jobbot.dashboard.server import _load_legacy_dashboard_module


def _dashboard_html(tmp_path: Path, monkeypatch) -> str:
    db = tmp_path / "jobbot.db"
    monkeypatch.setattr("jobbot.state.DB_PATH", db)
    client = _load_legacy_dashboard_module().app.test_client()
    return client.get("/").get_data(as_text=True)


def test_stage2_match_score_table_defaults_to_score_descending(
    tmp_path: Path, monkeypatch,
) -> None:
    html = _dashboard_html(tmp_path, monkeypatch)

    assert "let stage1SortKey = 'score';" in html
    assert "let stage1SortDir = -1;" in html
    assert "paintStage1SortArrow();" in html


def test_stage2_score_column_is_marked_sortable(
    tmp_path: Path, monkeypatch,
) -> None:
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")

    score_th = soup.find("th", attrs={"data-stage1-sort": "score"})
    assert score_th is not None, "Stage 2 score column should be sortable"


def test_stage3_shortlist_has_sort_controls(
    tmp_path: Path, monkeypatch,
) -> None:
    html = _dashboard_html(tmp_path, monkeypatch)
    soup = BeautifulSoup(html, "html.parser")

    controls = soup.find(attrs={"data-shortlist-sort-controls": True})
    assert controls is not None, "Stage 3 should expose a sort controls block"

    select = soup.find("select", id="shortlist-sort-key")
    assert select is not None
    options = {opt.get("value"): opt.get_text(strip=True)
               for opt in select.find_all("option")}
    # Must cover the three score-style columns the user actually triages on,
    # plus a few tie-breakers. "Best score" is the default selected option.
    assert "tailored_or_score" in options
    assert "score" in options
    assert "score_tailored" in options
    assert "score_delta" in options
    selected = select.find("option", selected=True)
    assert selected is not None and selected.get("value") == "tailored_or_score"

    dir_btn = soup.find("button", id="shortlist-sort-dir")
    assert dir_btn is not None
    assert dir_btn.get("data-dir") == "desc"


def test_stage3_shortlist_sort_logic_uses_tailored_score_when_present(
    tmp_path: Path, monkeypatch,
) -> None:
    """`tailored_or_score` reads `score_tailored` when set, else `score` —
    so a card with only a base score and a card with a tailored score
    sort against the same axis ("best known fit")."""
    html = _dashboard_html(tmp_path, monkeypatch)

    assert "let shortlistSortKey = 'tailored_or_score';" in html
    assert "let shortlistSortDir = -1;" in html
    # The fallback branch — tailored if present, else base score — is what
    # makes the default sort meaningful when only some rows are rescored.
    assert "j.score_tailored !== null && j.score_tailored !== undefined" in html
