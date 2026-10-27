from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestResult:
    killed: bool
    timed_out: bool
    output: str
    duration_ms: int


def _decode_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def run_tests(cmd: str, cwd: Path, timeout_seconds: int = 30) -> TestResult:
    start = time.monotonic()
    try:
        result = subprocess.run(
            shlex.split(cmd),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestResult(
            killed=result.returncode != 0,
            timed_out=False,
            output=str(result.stdout) + str(result.stderr),
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as exc:
        output = _decode_output(exc.stdout) + _decode_output(exc.stderr)
        return TestResult(
            killed=False,
            timed_out=True,
            output=output,
            duration_ms=timeout_seconds * 1000,
        )
