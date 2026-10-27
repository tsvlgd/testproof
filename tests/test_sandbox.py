"""Tests for isolated repository sandboxes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from testproof.sandbox import Sandbox


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_sandbox_is_a_copy_and_does_not_change_repository(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    before = _tree_hash(repo)

    with Sandbox(repo).create() as workspace:
        copied_source = workspace / "module.py"
        assert copied_source.read_text(encoding="utf-8") == "VALUE = 1\n"
        assert workspace != repo
        copied_source.write_text("VALUE = 2\n", encoding="utf-8")
        assert source.read_text(encoding="utf-8") == "VALUE = 1\n"

    assert _tree_hash(repo) == before
    assert not workspace.exists()


def test_sandbox_copies_repository_without_git_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text("private metadata", encoding="utf-8")
    (repo / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    with Sandbox(repo).create() as workspace:
        assert (workspace / "module.py").is_file()
        assert not (workspace / ".git").exists()
