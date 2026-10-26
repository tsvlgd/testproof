from __future__ import annotations

import hashlib
import time
from pathlib import Path

from testproof import __version__
from testproof.adapters.python import PythonAdapter
from testproof.models import (
    Confidence,
    FileReport,
    Mutant,
    MutantStatus,
    Report,
    RunInfo,
    Summary,
    ToolInfo,
)
from testproof.runner import TestResult, run_tests
from testproof.sandbox import Sandbox


class MutationEngine:
    """Deterministic grade implementation for Phase 1."""

    def __init__(
        self,
        repo: Path,
        test_command: str,
        *,
        test_timeout_seconds: int = 30,
        time_budget_seconds: int = 300,
        max_mutants: int = 50,
        language: str = "python",
        threshold: float | None = None,
    ) -> None:
        self._repo = repo
        self._test_command = test_command
        self._test_timeout_seconds = test_timeout_seconds
        self._time_budget_seconds = time_budget_seconds
        self._max_mutants = max_mutants
        self._adapter = PythonAdapter()
        self._language = language
        self._threshold = threshold

    def grade(
        self,
        *,
        target: str,
        base_ref: str | None,
        head_ref: str | None,
        merge_base: str | None,
        changed_files: list[tuple[str, set[int] | None]],
        time_budget_seconds: int | None = None,
    ) -> Report:
        """Grade and return a Report.

        changed_files is a list of (relative_path, changed_line_set_or_None).
        """

        budget = self._time_budget_seconds if time_budget_seconds is None else time_budget_seconds

        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        run_id = hashlib.sha256(
            f"{str(self._repo)}|{self._test_command}|{target}|{base_ref}|{head_ref}|{merge_base}|{self._max_mutants}|{budget}".encode()
        ).hexdigest()[:10]

        killed = 0
        survived = 0
        invalid = 0
        timeout = 0
        skipped = 0

        file_reports: list[FileReport] = []
        errors: list[str] = []

        # Baseline on a clean sandbox.
        with Sandbox(self._repo).create() as workspace:
            baseline = run_tests(
                self._test_command, cwd=workspace, timeout_seconds=self._test_timeout_seconds
            )
            if baseline.timed_out or baseline.killed:
                raise RuntimeError("Baseline test command failed; cannot compute a score")

        start = time.monotonic()

        # Deterministic file order.
        for rel_path, changed_lines in sorted(changed_files, key=lambda x: x[0]):
            points = []
            with Sandbox(self._repo).create() as workspace:
                sandbox_file = workspace / rel_path
                source = sandbox_file.read_text(encoding="utf-8")
                points = self._adapter.discover(rel_path, source, changed_lines)

                # Deterministic mutant order.
                points_sorted = sorted(points, key=lambda p: p.id)[: self._max_mutants]

                mutants: list[Mutant] = []

                for point in points_sorted:
                    if time.monotonic() - start > budget:
                        # Deterministic phase 1 does not stop early in this scaffold.
                        # Mark remaining mutants as skipped and continue.
                        skipped += 1
                        continue

                    t0 = time.monotonic()
                    status: MutantStatus
                    output: str
                    duration_ms: int

                    try:
                        mutated_source = self._adapter.apply(source, point)
                        sandbox_file.write_text(mutated_source, encoding="utf-8")
                    except Exception as exc:  # noqa: BLE001
                        status = "invalid"
                        output = str(exc)
                        invalid += 1
                        duration_ms = 0
                        mutants.append(
                            Mutant(
                                point=point, status=status, duration_ms=duration_ms, output=output
                            )
                        )
                        continue

                    run: TestResult = run_tests(
                        self._test_command,
                        cwd=workspace,
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

                    mutants.append(
                        Mutant(
                            point=point,
                            status=status,
                            duration_ms=duration_ms,
                            output=output,
                        )
                    )

            score_den = killed + survived
            score = (killed / score_den * 100.0) if score_den > 0 else None
            file_reports.append(FileReport(path=rel_path, score=score, mutants=tuple(mutants)))

        score_den_total = killed + survived
        score_total = (killed / score_den_total * 100.0) if score_den_total > 0 else None
        partial = False

        confidence: Confidence = "high"
        if partial:
            confidence = "medium"
        if timeout > 0 or invalid > 0:
            confidence = "medium"
        if timeout > 0 and invalid > 0:
            confidence = "low"

        duration_ms_total = int((time.monotonic() - start) * 1000)

        report_run = RunInfo(
            id=run_id,
            started_at=started_at,
            duration_ms=duration_ms_total,
            base_ref=base_ref,
            head_ref=head_ref,
            target=target,
            merge_base=merge_base,
            test_command=self._test_command,
            language=self._language,
            threshold=self._threshold,
            time_budget_ms=int(budget * 1000),
            max_mutants=self._max_mutants,
            all_files=False,
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

        tool = ToolInfo(name="testproof", version=__version__)

        return Report(
            schema_version="1.0",
            tool=tool,
            run=report_run,
            summary=summary,
            files=tuple(file_reports),
            errors=tuple(errors),
        )
