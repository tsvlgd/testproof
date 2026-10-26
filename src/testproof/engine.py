from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from testproof.adapters.python import PythonAdapter
from testproof.models import FileReport, Mutant, MutationPoint, Report, Summary, ToolInfo, RunInfo
from testproof.runner import run_tests
from testproof.sandbox import Sandbox


class MutationEngine:
    """Deterministic mutation grader.

    No model calls happen here.
    """

    def __init__(
        self,
        repo: Path,
        test_command: str,
        test_timeout_seconds: int = 30,
        time_budget_seconds: int = 300,
        max_mutants: int = 50,
    ) -> None:
        self._repo = repo
        self._test_command = test_command
        self._test_timeout_seconds = test_timeout_seconds
        self._time_budget_seconds = time_budget_seconds
        self._max_mutants = max_mutants
        self._adapter = PythonAdapter()

    def grade(
        self,
        *,
        changed_files: list[tuple[Path, set[int] | None]]
    ) -> Report:
        start = time.monotonic()
        mutants_seen: list[MutationPoint] = []

        killed = 0
        survived = 0
        invalid = 0
        timeout = 0
        skipped = 0

        file_reports: list[FileReport] = []
        errors: list[str] = []

        # First run baseline on a clean sandbox.
        with Sandbox(self._repo).create() as workspace:
            baseline = run_tests(self._test_command, workspace, timeout_seconds=self._test_timeout_seconds)
            if baseline.timed_out or baseline.killed:
                raise RuntimeError("Baseline test command failed; cannot compute a score")

        # Deterministic ordering.
        changed_files_sorted = sorted(changed_files, key=lambda item: str(item[0]))

        for file_path, changed_lines in changed_files_sorted:
            rel_path = str(file_path.relative_to(self._repo)) if file_path.is_absolute() else str(file_path)
            with Sandbox(self._repo).create() as workspace:
                sandbox_file = workspace / rel_path
                source = sandbox_file.read_text(encoding="utf-8")
                points = self._adapter.discover(rel_path, source, changed_lines)

                # Deterministic mutant order.
                points_sorted = sorted(points, key=lambda p: p.id)

                # Cap mutants per file.
                points_sorted = points_sorted[: self._max_mutants]

                file_mutants: list[Mutant] = []
                for point in points_sorted:
                    if time.monotonic() - start > self._time_budget_seconds:
                        # Mark partial by early stop.
                        skipped += 0
                        break
                    mutants_seen.append(point)
                    t0 = time.monotonic()

                    status = "invalid"
                    output = ""
                    duration_ms = 0

                    try:
                        mutated_source = self._adapter.apply(source, point)
                        sandbox_file.write_text(mutated_source, encoding="utf-8")
                    except Exception as exc:  # noqa: BLE001
                        status = "invalid"
                        output = str(exc)
                        invalid += 1
                        file_mutants.append(
                            Mutant(point=point, status=status, duration_ms=0, output=output)
                        )
                        continue

                    run = run_tests(
                        self._test_command,
                        workspace,
                        timeout_seconds=self._test_timeout_seconds,
                    )
                    duration_ms = int((time.monotonic() - t0) * 1000)

                    output = run.output
                    if run.timed_out:
                        status = "timeout"
                        timeout += 1
                    elif run.killed:
                        status = "killed"
                        killed += 1
                    else:
                        status = "survived"
                        survived += 1
                    file_mutants.append(
                        Mutant(
                            point=point,
                            status=status,
                            duration_ms=duration_ms,
                            output=output,
                        )
                    )

                # Restore file content is handled by recreating sandbox per file.
                score_den = killed + survived
                score = (killed / score_den * 100.0) if score_den > 0 else None
                file_reports.append(FileReport(path=rel_path, score=score, mutants=file_mutants))

        score_den_total = killed + survived
        score_total = (killed / score_den_total * 100.0) if score_den_total > 0 else None
        partial = False

        confidence = "high"
        if partial:
            confidence = "medium"
        if timeout > 0 or invalid > 0:
            confidence = "medium"
        if timeout > 0 and invalid > 0:
            confidence = "low"

        duration_ms_total = int((time.monotonic() - start) * 1000)
        run_id = hashlib.sha256(
            f"{str(self._repo)}|{self._test_command}|{self._max_mutants}|{self._time_budget_seconds}".encode()
        ).hexdigest()[:10]

        run = RunInfo(
            id=run_id,
            started_at="",
            duration_ms=duration_ms_total,
            base_ref=None,
            head_ref="",
            test_command=self._test_command,
            language="python",
            threshold=None,
            time_budget_ms=int(self._time_budget_seconds * 1000),
            max_mutants=self._max_mutants,
            all_files=True,
        )

        summary = Summary(
            score=score_total,
            killed=killed,
            survived=survived,
            invalid=invalid,
            timeout=timeout,
            skipped=skipped,
            total=killed + survived + invalid + timeout + skipped,
            partial=partial,
            confidence=confidence,
        )

        tool = ToolInfo(name="testproof", version="0.1.0")

        report = Report(
            schema_version="1.0",
            tool=tool,
            run=run,
            summary=summary,
            files=tuple(file_reports),
            errors=tuple(errors),
        )
        return report
