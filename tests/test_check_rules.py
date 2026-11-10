"""The rule checker fails on each kind of violation it exists to catch (W-75)."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("check_rules", Path(__file__).parents[1] / "tools" / "check_rules.py")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    (tmp_path / "specs").mkdir()
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry/hypotheses.json").write_text(json.dumps([{"id": "H-2026-001"}]))
    (tmp_path / "specs/0001-a.md").write_text("# 0001 A\n")
    (tmp_path / "specs/README.md").write_text("| [0001](0001-a.md) | A |\n")
    (tmp_path / "README.md").write_text("Evidence-graded statistics. H-2026-001.\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    def commit(author="Carlos Saritama <cssaritama@gmail.com>"):
        subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.name=x",
                "-c",
                "user.email=x@y",
                "commit",
                "-qm",
                "c",
                f"--author={author}",
            ],
            check=True,
        )

    commit()
    return module, tmp_path, commit


def test_clean_repository_passes(repo):
    module, _, _ = repo
    assert module.main(["--since", "2000-01-01"]) == 0


def test_unregistered_hypothesis_fails(repo):
    module, root, commit = repo
    (root / "specs/0001-a.md").write_text("# 0001 A\nTests H-2026-999.\n")
    commit()
    assert any("H-2026-999" in p for p in module.check_hypotheses())


def test_duplicate_and_unindexed_specifications_fail(repo):
    module, root, commit = repo
    (root / "specs/0001-b.md").write_text("# 0001 B\n")
    commit()
    problems = module.check_specs()
    assert any("0001 is used by more than one file" in p for p in problems)
    assert any("0001-b.md is not in" in p for p in problems)


def test_tool_names_and_claims_fail(repo):
    module, root, commit = repo
    (root / "README.md").write_text("Written with " + "Chat" + "GPT. Pure alpha, mathematically proven.\n")
    commit()
    assert module.check_tool_names()
    assert len(module.check_claims()) == 1


def test_data_files_fail(repo):
    module, root, commit = repo
    (root / "prices.csv").write_text("date,close\n")
    commit()
    assert module.check_data_files() == ["prices.csv is a data file outside examples/ and tests/"]


def test_foreign_author_and_missing_changelog_fail(repo):
    module, root, commit = repo
    (root / "src").mkdir()
    (root / "src/x.py").write_text("x = 1\n")
    commit(author="Someone Else <else@example.com>")
    problems = module.check_history("2000-01-01")
    assert any("authored by Someone Else" in p for p in problems)
    assert any("without a CHANGELOG.md change" in p for p in problems)
