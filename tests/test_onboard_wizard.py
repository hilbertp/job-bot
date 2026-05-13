"""`jobbot init` interactive wizard tests.

The wizard's job is to turn a focused Q&A into four valid config files.
Tests pin the contracts:

- A scripted "happy path" produces all four files with the user's answers.
- The generated profile.yaml is valid YAML and loads cleanly into the
  Profile model the rest of the codebase consumes.
- The generated config.yaml has the user's role queries woven into the
  per-source `queries:` blocks (so Stage 2 will show their target jobs,
  not the shipped PM defaults).
- The wizard does NOT overwrite a pre-existing file without confirmation
  (the "kept yours" branch).
- The wizard NEVER bakes the original author's name or email into the
  generated files (this is the "polluted for newcomers" foot gun).
"""
from __future__ import annotations

import io
from pathlib import Path

import yaml

from jobbot import onboard
from jobbot.profile import Profile


def _drive_wizard(monkeypatch, tmp_path: Path, answers: list[str]):
    """Run the wizard with `answers` queued as stdin lines."""
    monkeypatch.setattr(onboard, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(onboard, "DATA_DIR", tmp_path / "data")
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr("builtins.input", lambda _prompt: answers.pop(0))
    return onboard.run()


HAPPY_PATH_ANSWERS = [
    # 1. Who are you
    "Jane Doe",                  # full name
    "jane@example.com",          # personal email
    "+1 555 1234",               # phone
    "New York",                  # city
    "United States",             # country
    "America/New_York",          # timezone
    # 2. Online presence
    "https://linkedin.com/in/jane",
    "",                          # github (blank → kept blank)
    "",                          # website
    # 3. Email accounts
    "jane@gmail.com",            # gmail
    "jane@gmail.com",            # notify_to
    # 4. Target roles
    "Sous Chef, Chef de Partie",
    # 5. Preferences
    "n",                         # remote? n
    "y",                         # on-site ok? y
    "y",                         # relocate? y
    "US permanent resident",     # work auth
    # 6. Salary
    "55000",                     # min
    "75000",                     # max
    # 7. Languages
    "en_native, es_fluent",
    # 8. Deal-breaker industries
    "gambling, tobacco",
    # 9. Skills
    "à la carte, HACCP",
    "pastry, wine pairing",
    # 10. Existing CV (blank = skip)
    "",
    # 11. Cover letter sample (blank = skip)
    "",
]


def test_wizard_writes_all_four_files(monkeypatch, tmp_path: Path) -> None:
    rc = _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    assert rc == 0
    for relpath in (".env", "data/profile.yaml",
                    "data/config.yaml", "data/base_cv.md"):
        assert (tmp_path / relpath).exists(), f"missing {relpath}"


def test_wizard_profile_yaml_is_valid_and_loads_into_profile_model(
    monkeypatch, tmp_path: Path,
) -> None:
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    data = yaml.safe_load((tmp_path / "data" / "profile.yaml").read_text())
    profile = Profile.model_validate(data)

    assert profile.personal["full_name"] == "Jane Doe"
    assert profile.personal["email"] == "jane@example.com"
    assert profile.personal["location"]["city"] == "New York"
    assert profile.personal["links"]["linkedin"] == "https://linkedin.com/in/jane"
    assert profile.preferences["remote"] is False
    assert profile.preferences["on_site_ok"] is True
    assert profile.preferences["desired_salary_eur"]["min"] == 55000
    assert profile.preferences["desired_salary_eur"]["max"] == 75000


def test_wizard_target_roles_make_it_into_config_queries(
    monkeypatch, tmp_path: Path,
) -> None:
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    config_text = (tmp_path / "data" / "config.yaml").read_text()
    # The roles must appear in the per-source queries — that's what
    # determines which jobs the bot actually fetches.
    assert "Sous Chef" in config_text
    assert "Chef de Partie" in config_text
    # And the LinkedIn source must NEVER auto-submit (ToS rail).
    assert "auto_submit: false" in config_text


def test_wizard_base_cv_includes_users_name_and_target_roles(
    monkeypatch, tmp_path: Path,
) -> None:
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    cv = (tmp_path / "data" / "base_cv.md").read_text()
    assert cv.startswith("# Jane Doe")
    assert "jane@example.com" in cv
    assert "Sous Chef" in cv  # roles surface in the prompt-guidance paragraph


def test_wizard_does_not_bake_in_original_authors_identity(
    monkeypatch, tmp_path: Path,
) -> None:
    """The "polluted templates" foot gun: a newcomer running the wizard
    must NEVER end up with the original author's name, email, or
    business domain in their generated files."""
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    for relpath in (".env", "data/profile.yaml",
                    "data/config.yaml", "data/base_cv.md"):
        text = (tmp_path / relpath).read_text()
        assert "Philipp Hilbert" not in text, f"original author's name leaked into {relpath}"
        assert "hilbertp@gmail.com" not in text, f"original author's gmail leaked into {relpath}"
        assert "hilbert@true-north" not in text, f"original author's business SMTP leaked into {relpath}"
        assert "philipp@projuncta" not in text, f"original author's old email leaked into {relpath}"


def test_wizard_does_not_overwrite_existing_files_when_user_declines(
    monkeypatch, tmp_path: Path,
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "profile.yaml").write_text("pre-existing content")
    (tmp_path / "data" / "config.yaml").write_text("pre-existing content")
    (tmp_path / "data" / "base_cv.md").write_text("pre-existing content")
    (tmp_path / ".env").write_text("pre-existing content")

    # Same happy-path answers, but four "n" responses inserted for the
    # overwrite prompts (one per target file).
    answers = list(HAPPY_PATH_ANSWERS) + ["n", "n", "n", "n"]
    _drive_wizard(monkeypatch, tmp_path, answers)

    for relpath in (".env", "data/profile.yaml",
                    "data/config.yaml", "data/base_cv.md"):
        assert (tmp_path / relpath).read_text() == "pre-existing content", (
            f"{relpath} was overwritten despite the user declining"
        )


def test_wizard_dry_run_is_default_in_generated_config(
    monkeypatch, tmp_path: Path,
) -> None:
    """Critical safety rail: a newcomer's freshly-generated config MUST
    start with apply.dry_run: true so nothing can be sent until they
    explicitly opt in."""
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    config = yaml.safe_load((tmp_path / "data" / "config.yaml").read_text())
    assert config["apply"]["dry_run"] is True


def test_wizard_generates_top_n_knob_in_config(
    monkeypatch, tmp_path: Path,
) -> None:
    """Product journey stage 4: only top-N shortlist gets tailored docs.
    A fresh config must expose `digest.generate_top_n` so the user can
    tune it without editing source."""
    _drive_wizard(monkeypatch, tmp_path, list(HAPPY_PATH_ANSWERS))
    config = yaml.safe_load((tmp_path / "data" / "config.yaml").read_text())
    assert config["digest"]["generate_top_n"] == 5


def test_wizard_ingests_cv_into_corpus_with_primary_prefix(
    monkeypatch, tmp_path: Path,
) -> None:
    """Stage 1 onboarding: a user pointing at an existing CV file should
    have it copied into data/corpus/cvs/ with the PRIMARY_ prefix the
    distiller requires."""
    src_cv = tmp_path / "my_real_cv.md"
    src_cv.write_text("# My CV\n\nReal content goes here.\n")

    answers = list(HAPPY_PATH_ANSWERS)
    # Replace the two blank "skip" entries (positions -2, -1) with paths.
    answers[-2] = str(src_cv)
    answers[-1] = ""  # still skip cover letter for this test
    _drive_wizard(monkeypatch, tmp_path, answers)

    cvs_dir = tmp_path / "data" / "corpus" / "cvs"
    assert cvs_dir.exists(), "corpus/cvs/ should be created on ingest"
    files = list(cvs_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "PRIMARY_my_real_cv.md"
    assert files[0].read_text() == "# My CV\n\nReal content goes here.\n"


def test_wizard_ingests_cover_letter_without_primary_prefix(
    monkeypatch, tmp_path: Path,
) -> None:
    """Cover letters don't carry the PRIMARY_ prefix — only CVs do.
    The distiller treats CLs as voice signal, not a canonical fact source."""
    src_cl = tmp_path / "sample_letter.md"
    src_cl.write_text("Dear hiring manager,\n\nSample of my style.\n")

    answers = list(HAPPY_PATH_ANSWERS)
    answers[-2] = ""  # skip CV
    answers[-1] = str(src_cl)
    _drive_wizard(monkeypatch, tmp_path, answers)

    cls_dir = tmp_path / "data" / "corpus" / "cover_letters"
    assert cls_dir.exists()
    files = list(cls_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "sample_letter.md"
    assert not files[0].name.startswith("PRIMARY_")


def test_wizard_rejects_unsupported_corpus_file_types(
    monkeypatch, tmp_path: Path, capsys,
) -> None:
    """Distiller only handles pdf/docx/md/txt. A user pointing at a .doc
    or .rtf should be told it was skipped, and no file should appear in
    the corpus."""
    src_bad = tmp_path / "old_cv.rtf"
    src_bad.write_text("rtf content")

    answers = list(HAPPY_PATH_ANSWERS)
    answers[-2] = str(src_bad)
    # After the rejection prints, the prompt fires again; supply a
    # blank to break out of the loop.
    answers.insert(-1, "")
    _drive_wizard(monkeypatch, tmp_path, answers)

    cvs_dir = tmp_path / "data" / "corpus" / "cvs"
    assert not cvs_dir.exists() or not list(cvs_dir.iterdir())
