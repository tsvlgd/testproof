"""Tests for the command line interface."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from testproof import __version__
from testproof.cli import app

runner = CliRunner()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "TestProof")
    _git(repo, "config", "user.email", "testproof@example.com")
    (repo / "shipping.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "initial")
    (repo / "shipping.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo, "commit", "--quiet", "-am", "change value")
    return repo


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"testproof {__version__}"


def test_diff_command_renders_text(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = runner.invoke(app, ["diff", "--base", "HEAD~1", "--repo", str(repo)])

    assert result.exit_code == 0
    assert "Base: HEAD~1" in result.stdout
    assert "Target: working tree" in result.stdout
    assert "Changed files: 1" in result.stdout
    assert "shipping.py" in result.stdout
    assert "lines 1" in result.stdout


def test_diff_command_renders_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = runner.invoke(
        app,
        ["diff", "--base", "HEAD~1", "--repo", str(repo), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["head"] == "WORKTREE"
    assert payload["files"][0]["path"] == "shipping.py"
    assert payload["files"][0]["status"] == "modified"
    assert payload["files"][0]["lines"] == [{"start": 1, "end": 1}]


def test_diff_command_handles_no_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    result = runner.invoke(
        app,
        ["diff", "--base", "HEAD", "--repo", str(repo)],
    )

    assert result.exit_code == 0
    assert "No changed files." in result.stdout


def test_diff_command_defaults_to_worktree(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text("VALUE = 3\n", encoding="utf-8")
    (repo / "coupon.py").write_text("DISCOUNT = 1\n", encoding="utf-8")

    result = runner.invoke(app, ["diff", "--repo", str(repo)])

    assert result.exit_code == 0
    assert "Base: HEAD" in result.stdout
    assert "Target: working tree" in result.stdout
    assert "shipping.py" in result.stdout
    assert "coupon.py" in result.stdout


def test_diff_command_head_mode_ignores_worktree(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text("VALUE = 3\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["diff", "--base", "HEAD", "--head", "HEAD", "--repo", str(repo)],
    )

    assert result.exit_code == 0
    assert "Target: HEAD" in result.stdout
    assert "No changed files." in result.stdout


def test_diff_command_returns_two_on_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["diff", "--base", "HEAD", "--repo", str(tmp_path)])

    assert result.exit_code == 2
    assert "Error:" in result.stderr
    assert "git repository" in result.stderr
