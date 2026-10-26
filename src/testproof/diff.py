"""Resolve a git diff into changed files and changed line ranges."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
STATUS = Literal["added", "deleted", "modified", "renamed"]
MAX_UNTRACKED_BYTES = 2_000_000


class DiffError(RuntimeError):
    """Raised when TestProof cannot resolve a usable diff."""


@dataclass(frozen=True)
class LineRange:
    """An inclusive range of lines in the new version of a file."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            msg = f"Line ranges start at 1, got {self.start}"
            raise ValueError(msg)
        if self.end < self.start:
            msg = f"Line range end {self.end} is before start {self.start}"
            raise ValueError(msg)

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def __str__(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}-{self.end}"


@dataclass(frozen=True)
class ChangedFile:
    """One file touched by a diff."""

    path: str
    status: STATUS
    lines: tuple[LineRange, ...] = ()
    old_path: str | None = None

    @property
    def changed_line_count(self) -> int:
        return sum(line_range.count for line_range in self.lines)


@dataclass(frozen=True)
class Diff:
    """A repository change set between a base and a target revision or worktree."""

    base: str
    head: str
    files: tuple[ChangedFile, ...]

    @property
    def changed_paths(self) -> tuple[str, ...]:
        return tuple(changed.path for changed in self.files if changed.status != "deleted")

    @property
    def changed_line_count(self) -> int:
        return sum(changed.changed_line_count for changed in self.files)


def resolve_diff(repo: Path | str, base: str, head: str | None = None) -> Diff:
    """Return changed files and new file line ranges for a change set.

    When ``head`` is given, compare the merge base of ``base`` and ``head`` to
    ``head``. This is the committed pull request diff.

    When ``head`` is omitted, compare the merge base of ``base`` and ``HEAD`` to
    the working tree. The result includes staged, unstaged, and untracked files.
    The ``head`` field is set to ``"WORKTREE"`` so the mode is explicit.
    """

    repo_path = Path(repo).expanduser()
    if not repo_path.exists():
        msg = f"Repository path does not exist: {repo_path}"
        raise DiffError(msg)
    if not repo_path.is_dir():
        msg = f"Repository path is not a directory: {repo_path}"
        raise DiffError(msg)

    _git(repo_path, ["rev-parse", "--is-inside-work-tree"], "TestProof needs a git repository.")
    repo_root = Path(
        _git(
            repo_path,
            ["rev-parse", "--show-toplevel"],
            "TestProof needs a git repository.",
        ).strip()
    )
    _verify_revision(repo_root, base)

    if head is None:
        _verify_revision(repo_root, "HEAD")
        merge_base = _git(
            repo_root,
            ["merge-base", base, "HEAD"],
            f"Could not find a merge base between {base} and HEAD.",
        ).strip()
        command = [
            "-c",
            "core.quotePath=false",
            "diff",
            "--no-color",
            "--no-ext-diff",
            "--no-renames",
            "--no-prefix",
            "--unified=0",
            merge_base,
            "--",
        ]
        output = _git(repo_root, command, f"Could not diff {base} against the working tree.")
        tracked = _parse_diff(output)
        seen = {changed.path for changed in tracked}
        untracked = tuple(
            changed for changed in _untracked_files(repo_root) if changed.path not in seen
        )
        files = tuple(
            sorted(
                (*tracked, *untracked),
                key=lambda changed: (changed.path, changed.status),
            )
        )
        return Diff(base=base, head="WORKTREE", files=files)

    _verify_revision(repo_root, head)
    command = [
        "-c",
        "core.quotePath=false",
        "diff",
        "--no-color",
        "--no-ext-diff",
        "--no-renames",
        "--no-prefix",
        "--unified=0",
        f"{base}...{head}",
        "--",
    ]
    output = _git(repo_root, command, f"Could not diff {base} against {head}.")
    files = tuple(sorted(_parse_diff(output), key=lambda changed: (changed.path, changed.status)))
    return Diff(base=base, head=head, files=files)


def _verify_revision(repo: Path, revision: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{revision}^{{commit}}"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        reason = detail[-1] if detail else "unknown revision"
        msg = f"Cannot resolve revision {revision!r}: {reason}"
        raise DiffError(msg)


def _git(repo: Path, args: list[str], failure_message: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout

    detail = result.stderr.strip()
    if "not a git repository" in detail:
        msg = "TestProof needs a git repository. Run from the repo root or pass --repo."
        raise DiffError(msg)
    msg = f"{failure_message} {detail}" if detail else failure_message
    raise DiffError(msg)


def _untracked_files(repo: Path) -> tuple[ChangedFile, ...]:
    """Return untracked text files as added entries.

    Git does not include untracked files in ``git diff``, so the worktree mode
    reads them directly. Binary and oversized files are listed without line
    ranges because the mutation engine cannot grade them.
    """

    output = _git(
        repo,
        ["ls-files", "--others", "--exclude-standard", "-z"],
        "Could not list untracked files.",
    )
    changed: list[ChangedFile] = []
    for raw_path in output.split("\0"):
        if not raw_path:
            continue
        full_path = repo / raw_path
        try:
            if not full_path.is_file():
                continue
            size = full_path.stat().st_size
        except OSError:
            continue

        lines: tuple[LineRange, ...] = ()
        if size <= MAX_UNTRACKED_BYTES:
            try:
                data = full_path.read_bytes()
            except OSError:
                data = b""
            if b"\0" not in data:
                line_count = len(data.decode("utf-8", errors="replace").splitlines())
                if line_count:
                    lines = (LineRange(start=1, end=line_count),)

        changed.append(ChangedFile(path=raw_path, status="added", lines=lines))
    return tuple(changed)


def _parse_diff(output: str) -> tuple[ChangedFile, ...]:
    files: list[ChangedFile] = []
    path: str | None = None
    old_path: str | None = None
    status: STATUS = "modified"
    lines: list[LineRange] = []

    def flush() -> None:
        nonlocal path, old_path, status, lines
        if path is None and old_path is None:
            return
        resolved_path = path or old_path
        if resolved_path is None:
            return
        files.append(
            ChangedFile(
                path=resolved_path,
                status=status,
                lines=tuple(_merge_ranges(lines)),
                old_path=old_path if old_path != resolved_path else None,
            )
        )
        path = None
        old_path = None
        status = "modified"
        lines = []

    for line in output.splitlines():
        if line.startswith("diff --git "):
            flush()
            continue
        if line.startswith("new file mode "):
            status = "added"
            continue
        if line.startswith("deleted file mode "):
            status = "deleted"
            continue
        if line.startswith("rename to "):
            path = line.removeprefix("rename to ").strip()
            status = "renamed"
            continue
        if line.startswith("--- "):
            old_path = _parse_diff_path(line.removeprefix("--- "))
            continue
        if line.startswith("+++ "):
            new_path = _parse_diff_path(line.removeprefix("+++ "))
            if new_path is not None:
                path = new_path
            elif old_path is not None:
                path = old_path
            continue
        if line.startswith("@@"):
            match = HUNK_HEADER.match(line)
            if match is None:
                msg = f"Could not parse diff hunk header: {line}"
                raise DiffError(msg)
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            if count > 0:
                lines.append(LineRange(start=start, end=start + count - 1))
            continue

    flush()
    return tuple(files)


def _parse_diff_path(value: str) -> str | None:
    candidate = value.strip()
    if candidate == "/dev/null":
        return None
    if candidate.startswith('"') or candidate.endswith('"'):
        msg = f"Quoted diff paths are not supported: {candidate}"
        raise DiffError(msg)
    return candidate


def _merge_ranges(ranges: list[LineRange]) -> list[LineRange]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: item.start)
    merged = [ordered[0]]
    for item in ordered[1:]:
        previous = merged[-1]
        if item.start <= previous.end + 1:
            merged[-1] = LineRange(start=previous.start, end=max(previous.end, item.end))
        else:
            merged.append(item)
    return merged
