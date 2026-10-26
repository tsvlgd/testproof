"""Tests for the git diff resolver."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from testproof.diff import DiffError, LineRange, resolve_diff


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
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total >= 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "initial")
    return repo


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", message)


def _git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_diff_resolves_changed_files(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total > 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    (repo / "coupon.py").write_text(
        "def discount(total: int) -> int:\n    return total // 10\n",
        encoding="utf-8",
    )
    _commit_all(repo, "change shipping and add coupon")

    diff = resolve_diff(repo, "HEAD~1", "HEAD")

    assert diff.base == "HEAD~1"
    assert diff.head == "HEAD"
    assert diff.changed_paths == ("coupon.py", "shipping.py")
    by_path = {changed.path: changed for changed in diff.files}
    assert by_path["shipping.py"].status == "modified"
    assert by_path["shipping.py"].lines == (LineRange(start=2, end=2),)
    assert by_path["coupon.py"].status == "added"
    assert by_path["coupon.py"].lines == (LineRange(start=1, end=2),)


def test_diff_resolves_multiple_hunks(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total > 50:\n"
        "        return 0\n"
        "    return 7\n",
        encoding="utf-8",
    )
    _commit_all(repo, "change two lines")

    diff = resolve_diff(repo, "HEAD~1", "HEAD")

    assert len(diff.files) == 1
    assert diff.files[0].lines == (
        LineRange(start=2, end=2),
        LineRange(start=4, end=4),
    )
    assert diff.changed_line_count == 2


def test_diff_handles_no_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    diff = resolve_diff(repo, "HEAD", "HEAD")

    assert diff.files == ()
    assert diff.changed_line_count == 0


def test_diff_handles_deleted_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").unlink()
    _commit_all(repo, "delete shipping")

    diff = resolve_diff(repo, "HEAD~1", "HEAD")

    assert len(diff.files) == 1
    assert diff.files[0].path == "shipping.py"
    assert diff.files[0].status == "deleted"
    assert diff.files[0].lines == ()
    assert diff.changed_paths == ()


def test_diff_handles_path_with_space(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping rules.py").write_text("VALUE = 2\n", encoding="utf-8")
    _commit_all(repo, "add file with a space")

    diff = resolve_diff(repo, "HEAD~1", "HEAD")

    assert [changed.path for changed in diff.files] == ["shipping rules.py"]


def test_diff_rejects_missing_repository(tmp_path: Path) -> None:
    with pytest.raises(DiffError, match="does not exist"):
        resolve_diff(tmp_path / "missing", "HEAD")


def test_diff_rejects_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(DiffError, match="git repository"):
        resolve_diff(tmp_path, "HEAD")


def test_diff_rejects_unknown_revision(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    with pytest.raises(DiffError, match="Cannot resolve revision"):
        resolve_diff(repo, "does-not-exist")


def test_diff_worktree_includes_uncommitted_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total > 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    (repo / "coupon.py").write_text(
        "def discount(total: int) -> int:\n    return total // 10\n",
        encoding="utf-8",
    )

    diff = resolve_diff(repo, "HEAD")

    assert diff.head == "WORKTREE"
    by_path = {changed.path: changed for changed in diff.files}
    assert set(by_path) == {"coupon.py", "shipping.py"}
    assert by_path["shipping.py"].status == "modified"
    assert by_path["shipping.py"].lines == (LineRange(start=2, end=2),)
    assert by_path["coupon.py"].status == "added"
    assert by_path["coupon.py"].lines == (LineRange(start=1, end=2),)


def test_diff_worktree_includes_staged_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total > 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    _git(repo, "add", "shipping.py")

    diff = resolve_diff(repo, "HEAD")

    assert diff.changed_paths == ("shipping.py",)
    assert diff.files[0].lines == (LineRange(start=2, end=2),)


def test_diff_worktree_respects_gitignore(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    _commit_all(repo, "ignore generated file")
    (repo / "ignored.py").write_text("VALUE = 1\n", encoding="utf-8")

    diff = resolve_diff(repo, "HEAD")

    assert diff.files == ()


def test_diff_worktree_uses_merge_base(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main_branch = _git_output(repo, "branch", "--show-current")
    _git(repo, "checkout", "-b", "feature")
    (repo / "feature.py").write_text("FEATURE = 1\n", encoding="utf-8")
    _commit_all(repo, "feature change")
    _git(repo, "checkout", main_branch)
    (repo / "main.py").write_text("MAIN = 1\n", encoding="utf-8")
    _commit_all(repo, "main change")
    _git(repo, "checkout", "feature")
    (repo / "shipping.py").write_text(
        "def shipping_fee(total: int) -> int:\n"
        "    if total > 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )

    diff = resolve_diff(repo, main_branch)

    paths = set(diff.changed_paths)
    assert "feature.py" in paths
    assert "shipping.py" in paths
    assert "main.py" not in paths


def test_diff_worktree_handles_no_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    diff = resolve_diff(repo, "HEAD")

    assert diff.head == "WORKTREE"
    assert diff.files == ()


def test_diff_worktree_includes_untracked_path_with_space(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping rules.py").write_text("VALUE = 2\n", encoding="utf-8")

    diff = resolve_diff(repo, "HEAD")

    assert [changed.path for changed in diff.files] == ["shipping rules.py"]
    assert diff.files[0].status == "added"
    assert diff.files[0].lines == (LineRange(start=1, end=1),)


def test_diff_worktree_lists_binary_untracked_file_without_lines(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "image.bin").write_bytes(b"\x00\x01\x02")

    diff = resolve_diff(repo, "HEAD")

    assert [changed.path for changed in diff.files] == ["image.bin"]
    assert diff.files[0].status == "added"
    assert diff.files[0].lines == ()


def test_diff_commit_mode_ignores_worktree(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "shipping.py").write_text("VALUE = 3\n", encoding="utf-8")
    (repo / "coupon.py").write_text("VALUE = 4\n", encoding="utf-8")

    diff = resolve_diff(repo, "HEAD", "HEAD")

    assert diff.head == "HEAD"
    assert diff.files == ()


def test_diff_resolves_paths_from_a_subdirectory(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    package = repo / "pkg"
    package.mkdir()
    (package / "rules.py").write_text("VALUE = 1\n", encoding="utf-8")
    _commit_all(repo, "add package")
    (package / "rules.py").write_text("VALUE = 2\n", encoding="utf-8")

    diff = resolve_diff(package, "HEAD")

    assert diff.changed_paths == ("pkg/rules.py",)
    assert diff.files[0].lines == (LineRange(start=1, end=1),)
