"""LLMFillAdapter (universal fallback for unknown ATSes) tests.

The point of this adapter is to handle European Mittelstand recruiting
sites (scope-recruiting.de, TeamTailor, Personio variants) that no
specific adapter covers, by asking Claude to map scraped form fields to
profile values.

We do NOT call real Claude in tests, the LLM is mocked. We DO use a
real procilon-shaped form-fields fixture (extracted live from
procilongroup.scope-recruiting.de on 2026-05-16) so the prompt
construction and mapping-application logic are exercised against
production-shaped data.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from jobbot.applier.adapters.llm_fill import LLMFillAdapter
from jobbot.models import GeneratedDocs, JobPosting
from jobbot.profile import Profile


# Real form-field shape extracted from procilon's scope-recruiting.de
# apply form on 2026-05-16. Use this as the canonical fixture so the
# adapter is unit-tested against actual production data.
PROCILON_FIELDS: list[dict[str, Any]] = [
    {"tag": "SELECT", "type": "select-one", "name": "com",
     "id": "scope-location-select", "placeholder": None, "label": None,
     "required": False, "options": [{"value": "1001", "text": "Berlin"}]},
    {"tag": "SELECT", "type": "select-one", "name": "gender",
     "id": "6a085aefd9c6a", "placeholder": None, "label": None,
     "required": False, "options": [
         {"value": "male", "text": "Herr"},
         {"value": "female", "text": "Frau"},
         {"value": "diverse", "text": "Divers"},
     ]},
    {"tag": "INPUT", "type": "text", "name": "first_name",
     "id": "6a085aefd9ca5", "placeholder": "Vorname *", "label": None,
     "required": False, "options": None},
    {"tag": "INPUT", "type": "text", "name": "last_name",
     "id": "6a085aefd9cdb", "placeholder": "Nachname *", "label": None,
     "required": False, "options": None},
    {"tag": "INPUT", "type": "text", "name": "email",
     "id": "6a085aefd9d3a", "placeholder": "E-Mail Adresse *", "label": None,
     "required": False, "options": None},
    {"tag": "INPUT", "type": "text", "name": "mobile_phone",
     "id": "6a085aefd9de6", "placeholder": "Mobiltelefonnummer *", "label": None,
     "required": False, "options": None},
    {"tag": "INPUT", "type": "text", "name": "salary",
     "id": "6a085aefd9e11", "placeholder": "Gehaltsvorstellung  *", "label": None,
     "required": False, "options": None},
]


def _profile() -> Profile:
    return Profile(
        personal={
            "full_name": "Philipp Hilbert",
            "email": "hilbert@true-north.berlin",
            "phone": "+357 94101644",
            "location": {"city": "Berlin", "country": "Germany"},
            "links": {"linkedin": "https://linkedin.com/in/x"},
        },
        preferences={"application_salary_eur_year": 125000, "notice_period_weeks": 4},
    )


def _job() -> JobPosting:
    return JobPosting(
        id="proc1", source="linkedin",
        title="Product Owner (m/w/d)", company="procilon GROUP",
        url="https://procilongroup.scope-recruiting.de/?page=job&id=106044",
        apply_url="https://procilongroup.scope-recruiting.de/?page=job&id=106044",
        description="...",
    )


def _docs(tmp_path) -> GeneratedDocs:
    out = tmp_path / "out"
    out.mkdir()
    cv = out / "cv.pdf"; cv.write_bytes(b"%PDF cv")
    cl = out / "cover_letter.pdf"; cl.write_bytes(b"%PDF cl")
    return GeneratedDocs(
        cv_md="# CV\n", cv_html="<h1>CV</h1>",
        cover_letter_md="...", cover_letter_html="<p>...</p>",
        output_dir=str(out),
        cv_pdf=str(cv), cover_letter_pdf=str(cl),
    )


# ---------------------------------------------------------------------------
# adapter contract
# ---------------------------------------------------------------------------

def test_registered_after_specific_adapters_before_generic():
    """LLMFill must sit between specific ATS adapters (GH/Lever/etc.) and
    GenericAdapter. Order matters because the runner picks the first
    `matches()`-positive adapter; flipping LLMFill ahead of Greenhouse
    would silently route every Greenhouse job through the LLM path."""
    from jobbot.applier.runner import _load_adapters
    names = [a.name for a in _load_adapters()]
    assert "llm_fill" in names
    assert names[-1] == "generic", f"generic must remain last: {names}"
    assert names.index("llm_fill") == names.index("generic") - 1
    # Specific adapters must precede llm_fill
    for specific in ("greenhouse", "lever", "workday", "recruitee"):
        assert names.index(specific) < names.index("llm_fill"), (
            f"{specific} must precede llm_fill in adapter order"
        )


def test_public_methods_exist():
    a = LLMFillAdapter(anthropic_api_key="x")
    for attr in ("name", "matches", "fill", "submit"):
        assert hasattr(a, attr)
    assert a.name == "llm_fill"


# ---------------------------------------------------------------------------
# matches()
# ---------------------------------------------------------------------------

def test_matches_when_page_has_inputs():
    page = MagicMock()
    page.locator.return_value.count.return_value = 14
    a = LLMFillAdapter(anthropic_api_key="x")
    assert a.matches("https://anywhere.example/job", page) is True


def test_does_not_match_when_page_has_no_inputs():
    page = MagicMock()
    page.locator.return_value.count.return_value = 0
    a = LLMFillAdapter(anthropic_api_key="x")
    assert a.matches("https://anywhere.example/job", page) is False


# ---------------------------------------------------------------------------
# submit() is dry-run only in v1
# ---------------------------------------------------------------------------

def test_submit_raises_so_supervised_human_clicks_send():
    a = LLMFillAdapter(anthropic_api_key="x")
    with pytest.raises(NotImplementedError):
        a.submit(MagicMock())


# ---------------------------------------------------------------------------
# fill() with a mocked Claude
# ---------------------------------------------------------------------------

def _mock_claude_response(text: str):
    """Build a fake Anthropic SDK response that returns the given text."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def test_fill_applies_mapping_from_claude(tmp_path, monkeypatch):
    """Happy path: Claude returns a clean mapping; the adapter walks it
    and calls page.locator(sel).fill / select_option for each entry."""
    a = LLMFillAdapter(anthropic_api_key="x")
    page = MagicMock()
    # First scrape: procilon shape. Second scrape (file inputs): empty.
    page.evaluate.side_effect = [PROCILON_FIELDS, []]
    page.locator.return_value.count.return_value = 0  # no reveal button found

    # Each locator(sel).first returns a fresh mock with .count()=1 and
    # working .fill / .select_option.
    locators_called: list[tuple[str, str, str]] = []
    def _locator(sel):
        loc = MagicMock()
        first = MagicMock()
        first.count.return_value = 1
        def _fill(value, **_kw):
            locators_called.append((sel, "fill", value))
        def _select(value=None, **_kw):
            locators_called.append((sel, "select_option", value))
        first.fill.side_effect = _fill
        first.select_option.side_effect = _select
        loc.first = first
        loc.count.return_value = 0  # no reveal button
        return loc
    page.locator = MagicMock(side_effect=_locator)

    claude_payload = '''{"fills": [
        {"selector": "#6a085aefd9ca5", "value": "Philipp",     "kind": "text"},
        {"selector": "#6a085aefd9cdb", "value": "Hilbert",     "kind": "text"},
        {"selector": "#6a085aefd9d3a", "value": "hilbert@true-north.berlin", "kind": "text"},
        {"selector": "#6a085aefd9de6", "value": "+357 94101644",            "kind": "text"},
        {"selector": "#6a085aefd9e11", "value": "125000",      "kind": "text"},
        {"selector": "[name='gender']", "value": "diverse",     "kind": "select_option"}
    ]}'''
    fake_msg = _mock_claude_response(claude_payload)
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("anthropic.Anthropic", return_value=fake_client):
        a.fill(page, _job(), _profile(), _docs(tmp_path))

    by_sel = {(s, k): v for s, k, v in locators_called}
    assert by_sel[("#6a085aefd9ca5", "fill")] == "Philipp"
    assert by_sel[("#6a085aefd9cdb", "fill")] == "Hilbert"
    assert by_sel[("#6a085aefd9d3a", "fill")] == "hilbert@true-north.berlin"
    assert by_sel[("#6a085aefd9e11", "fill")] == "125000"
    assert by_sel[("[name='gender']", "select_option")] == "diverse"


def test_fill_does_nothing_without_api_key(tmp_path, monkeypatch):
    """No API key -> skip cleanly. No Claude call, no page interaction
    beyond the noop reveal check."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a = LLMFillAdapter(anthropic_api_key=None)
    page = MagicMock()
    page.locator.return_value.count.return_value = 0
    page.evaluate.return_value = PROCILON_FIELDS
    a.fill(page, _job(), _profile(), _docs(tmp_path))
    # Crucially: Anthropic was not constructed, no LLM call attempted.
    # evaluate is also not called for field scraping when the key is missing.
    page.evaluate.assert_not_called()


def test_fill_tolerates_bad_json_from_claude(tmp_path):
    """If Claude returns junk, the adapter logs and skips, it does not
    crash the apply attempt."""
    a = LLMFillAdapter(anthropic_api_key="x")
    page = MagicMock()
    page.evaluate.side_effect = [PROCILON_FIELDS, []]
    page.locator.return_value.count.return_value = 0

    fake_msg = _mock_claude_response("not json at all, sorry")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("anthropic.Anthropic", return_value=fake_client):
        a.fill(page, _job(), _profile(), _docs(tmp_path))
    # Should complete without raising; no fills applied is acceptable.


def test_fill_strips_markdown_fences_around_json(tmp_path):
    """Claude sometimes wraps JSON in ```json fences despite the prompt.
    The adapter should still parse the inner JSON."""
    a = LLMFillAdapter(anthropic_api_key="x")
    page = MagicMock()
    page.evaluate.side_effect = [PROCILON_FIELDS, []]

    locators_called: list[tuple[str, str, str]] = []
    def _locator(sel):
        loc = MagicMock()
        first = MagicMock(); first.count.return_value = 1
        first.fill.side_effect = lambda v, **_: locators_called.append((sel, "fill", v))
        loc.first = first
        loc.count.return_value = 0
        return loc
    page.locator = MagicMock(side_effect=_locator)

    fenced = '```json\n{"fills":[{"selector":"#x","value":"v","kind":"text"}]}\n```'
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_claude_response(fenced)
    with patch("anthropic.Anthropic", return_value=fake_client):
        a.fill(page, _job(), _profile(), _docs(tmp_path))
    assert ("#x", "fill", "v") in locators_called


def test_fill_second_pass_uploads_files_revealed_by_select(tmp_path):
    """The procilon-pattern: doc-type select reveals a file input AFTER
    the first pass fills the select. Second-pass scrape must catch the
    new file input and the adapter must call set_input_files on it."""
    a = LLMFillAdapter(anthropic_api_key="x")
    page = MagicMock()
    # First scrape: no file input. Second scrape: a file input that
    # only became visible after the select was filled in pass 1.
    file_field = [{
        "tag": "INPUT", "type": "file", "name": "cv_upload",
        "id": "cv-input", "placeholder": None, "label": "CV",
        "required": True, "options": None,
    }]
    page.evaluate.side_effect = [PROCILON_FIELDS, file_field]

    upload_paths: list[tuple[str, str]] = []
    def _locator(sel):
        loc = MagicMock()
        first = MagicMock(); first.count.return_value = 1
        first.fill.side_effect = lambda v, **_: None
        first.select_option.side_effect = lambda **kw: None
        first.set_input_files.side_effect = lambda path, **_: upload_paths.append((sel, path))
        loc.first = first
        loc.count.return_value = 0
        return loc
    page.locator = MagicMock(side_effect=_locator)

    first_pass = '{"fills":[{"selector":"[name=\\"welchesdokumentmchte\\"]","value":"cv","kind":"select_option"}]}'
    cv_path = str(tmp_path / "out" / "cv.pdf")
    second_pass = '{"fills":[{"selector":"#cv-input","value":"' + cv_path + '","kind":"file"}]}'

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        _mock_claude_response(first_pass),
        _mock_claude_response(second_pass),
    ]
    with patch("anthropic.Anthropic", return_value=fake_client):
        a.fill(page, _job(), _profile(), _docs(tmp_path))

    assert any(sel == "#cv-input" and path == cv_path for sel, path in upload_paths), (
        f"second pass did not upload to revealed file input: {upload_paths}"
    )


def test_fill_per_field_failure_does_not_abort_remaining_mappings(tmp_path):
    """If one .fill() raises (selector found nothing, or timed out),
    the adapter should log and move on so the human reviewer still
    gets a partially filled form."""
    a = LLMFillAdapter(anthropic_api_key="x")
    page = MagicMock()
    page.evaluate.side_effect = [PROCILON_FIELDS, []]

    filled: list[tuple[str, str]] = []
    def _locator(sel):
        loc = MagicMock()
        first = MagicMock(); first.count.return_value = 1
        if sel == "#broken":
            first.fill.side_effect = TimeoutError("element detached")
        else:
            first.fill.side_effect = lambda v, **_: filled.append((sel, v))
        loc.first = first
        loc.count.return_value = 0
        return loc
    page.locator = MagicMock(side_effect=_locator)

    payload = '''{"fills":[
        {"selector":"#good1","value":"A","kind":"text"},
        {"selector":"#broken","value":"B","kind":"text"},
        {"selector":"#good2","value":"C","kind":"text"}
    ]}'''
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_claude_response(payload)
    with patch("anthropic.Anthropic", return_value=fake_client):
        a.fill(page, _job(), _profile(), _docs(tmp_path))
    assert ("#good1", "A") in filled
    assert ("#good2", "C") in filled, (
        "third fill skipped after second failed; per-field failures must "
        "not abort the pass"
    )
