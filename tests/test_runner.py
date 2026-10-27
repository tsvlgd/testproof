"""Tests for project test command execution."""

from __future__ import annotations

import sys
from pathlib import Path

from testproof.runner import run_tests


def test_runner_classifies_nonzero_exit_as_killed(tmp_path: Path) -> None:
    result = run_tests(f'{sys.executable} -c "raise SystemExit(1)"', cwd=tmp_path)

    assert result.killed is True
    assert result.timed_out is False


def test_runner_classifies_zero_exit_as_survived(tmp_path: Path) -> None:
    result = run_tests(f'{sys.executable} -c "print(42)"', cwd=tmp_path)

    assert result.killed is False
    assert result.timed_out is False
    assert "42" in result.output


def test_runner_captures_timeout_output(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text(
        "import time\nprint('starting', flush=True)\ntime.sleep(2)\n",
        encoding="utf-8",
    )

    result = run_tests(f"{sys.executable} {script}", cwd=tmp_path, timeout_seconds=1)

    assert result.killed is False
    assert result.timed_out is True
    assert "starting" in result.output


def test_runner_accepts_quoted_arguments(tmp_path: Path) -> None:
    result = run_tests(f"{sys.executable} -c \"print('two words')\"", cwd=tmp_path)

    assert result.killed is False
    assert result.timed_out is False
    assert "two words" in result.output
