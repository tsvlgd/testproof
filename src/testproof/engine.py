"""Deterministic mutation grading orchestration."""

from __future__ import annotations

import hashlib
import json
import os
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
    """Grade changed Python code using isolated, deterministic mutants."""

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
        if test_timeout_seconds <= 0:
            msg = "test_timeout_seconds must be greater than zero"
            raise ValueError(msg)
        if time_budget_seconds < 0:
            msg = "time_budget_seconds cannot be negative"
            raise ValueError(msg)
        if max_mutants < 0:
            msg = "max_mutants cannot be negative"
            raise ValueError(msg)

        self._repo = repo.resolve()
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
        all_files: bool = False,
    ) -> Report:
        """Grade the supplied repository paths and optional changed line sets."""
        budget = self._time_budget_seconds if time_budget_seconds is None else time_budget_seconds
        if budget < 0:
            msg = "time_budget_seconds cannot be negative"
            raise ValueError(msg)

        normalized_files: dict[str, set[int] | None] = {}
        for path, lines in changed_files:
            if path not in normalized_files:
                normalized_files[path] = None if lines is None else set(lines)
            elif normalized_files[path] is None or lines is None:
                normalized_files[path] = None
            else:
                existing_lines = normalized_files[path]
                if existing_lines is not None:
                    existing_lines.update(lines)
        ordered_files = sorted(normalized_files.items())
        scope = [
            (path, sorted(lines) if lines is not None else None) for path, lines in ordered_files
        ]
        run_id = hashlib.sha256(
            json.dumps(
                [
                    str(self._repo),
                    self._test_command,
                    target,
                    base_ref,
                    head_ref,
                    merge_base,
                    scope,
                    self._max_mutants,
                    budget,
                    all_files,
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:10]

        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        grade_started = time.monotonic()

        def _sandbox_env(workspace: Path) -> dict[str, str]:
            env = dict(os.environ)
            env.pop("VIRTUAL_ENV", None)
            src_dir = workspace / "src"
            if src_dir.is_dir():
                existing = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")
            return env

        with Sandbox(self._repo).create() as baseline_workspace:
            baseline = run_tests(
                self._test_command,
                cwd=baseline_workspace,
                timeout_seconds=self._test_timeout_seconds,
                env=_sandbox_env(baseline_workspace),
            )
        if baseline.timed_out or baseline.killed:
            raise RuntimeError("Baseline test command failed; cannot compute a score")

        killed = 0
        survived = 0
        invalid = 0
        timeout = 0
        skipped = 0
        discovered_count = 0
        selected_count = 0
        file_reports: list[FileReport] = []
        errors: list[str] = []

        for rel_path, changed_lines in ordered_files:
            try:
                with Sandbox(self._repo).create() as discovery_workspace:
                    source_path = self._safe_path(discovery_workspace, rel_path)
                    source = source_path.read_text(encoding="utf-8")
                    points = self._adapter.discover(rel_path, source, changed_lines)
            except (OSError, ValueError) as exc:
                errors.append(f"{rel_path}: {exc}")
                continue

            if not points:
                errors.append(f"{rel_path}: no supported mutation points found")
                continue

            ordered_points = sorted(points, key=lambda point: point.id)
            discovered_count += len(ordered_points)
            remaining_capacity = max(0, self._max_mutants - selected_count)
            selected_points = ordered_points[:remaining_capacity]
            capped_points = ordered_points[remaining_capacity:]
            selected_count += len(selected_points)

            mutants: list[Mutant] = [
                Mutant(point=point, status="skipped") for point in capped_points
            ]
            skipped += len(capped_points)
            file_killed = 0
            file_survived = 0

            for point in selected_points:
                remaining_budget = budget - (time.monotonic() - grade_started)
                if remaining_budget <= 0:
                    mutants.append(Mutant(point=point, status="skipped"))
                    skipped += 1
                    continue

                # Use the remaining budget as the timeout if it's less than the test timeout
                effective_timeout = min(self._test_timeout_seconds, max(1, int(remaining_budget)))

                # Progress reporting
                import sys as _sys

                progress = selected_count - len(selected_points) + selected_points.index(point) + 1
                print(
                    f"  grading {rel_path}:{point.line} "
                    f"({point.operator} {point.original} -> {point.replacement}) "
                    f"[{progress}/{selected_count}]",
                    file=_sys.stderr,
                )

                mutant_started = time.monotonic()
                status: MutantStatus
                output = ""
                duration_ms = 0

                import sys as _sys

                progress = selected_count - len(selected_points) + selected_points.index(point) + 1
                detail = f"{point.operator} {point.original!r} -> {point.replacement!r}"
                print(
                    f"  [{progress}/{selected_count}] {rel_path}:{point.line} {detail}",
                    file=_sys.stderr,
                )
                try:
                    with Sandbox(self._repo).create() as mutant_workspace:
                        mutant_path = self._safe_path(mutant_workspace, rel_path)
                        original_source = mutant_path.read_text(encoding="utf-8")
                        mutated_source = self._adapter.apply(original_source, point)
                        if not self._adapter.validate(mutated_source):
                            status = "invalid"
                            output = "Mutation produced invalid Python syntax"
                        else:
                            mutant_path.write_text(mutated_source, encoding="utf-8")
                            result: TestResult = run_tests(
                                self._test_command,
                                cwd=mutant_workspace,
                                timeout_seconds=effective_timeout,
                                env=_sandbox_env(mutant_workspace),
                            )
                            output = result.output
                            if result.timed_out:
                                status = "timeout"
                            elif result.killed:
                                status = "killed"
                            else:
                                status = "survived"
                except (OSError, ValueError) as exc:
                    status = "invalid"
                    output = str(exc)

                duration_ms = int((time.monotonic() - mutant_started) * 1000)
                if status == "killed":
                    killed += 1
                    file_killed += 1
                elif status == "survived":
                    survived += 1
                    file_survived += 1
                elif status == "timeout":
                    timeout += 1
                elif status == "invalid":
                    invalid += 1

                mutants.append(
                    Mutant(
                        point=point,
                        status=status,
                        duration_ms=duration_ms,
                        output=output,
                    )
                )

            file_denominator = file_killed + file_survived
            file_score = file_killed / file_denominator * 100.0 if file_denominator else None
            file_reports.append(
                FileReport(
                    path=rel_path,
                    score=file_score,
                    mutants=tuple(sorted(mutants, key=lambda mutant: mutant.point.id)),
                )
            )

        denominator = killed + survived
        score = killed / denominator * 100.0 if denominator else None
        partial = skipped > 0 or selected_count < discovered_count or bool(errors)
        confidence: Confidence = "high"
        if partial or invalid > 0 or timeout > 0:
            confidence = "medium"
        if (
            (partial and skipped >= discovered_count / 2)
            or (timeout > 0 and invalid > 0)
            or (bool(errors) and not (killed or survived))
        ):
            confidence = "low"

        reasons: list[str] = []
        if errors:
            reasons.append(f"{len(errors)} file(s) could not be graded.")
        if capped_count := discovered_count - selected_count:
            reasons.append(
                f"Mutant cap selected {selected_count} of {discovered_count} "
                f"discovered mutants; {capped_count} were skipped."
            )
        budget_skipped = skipped - (discovered_count - selected_count)
        if budget_skipped:
            reasons.append(f"Time budget reached; skipped {budget_skipped} selected mutants.")

        duration_ms = int((time.monotonic() - grade_started) * 1000)
        report_run = RunInfo(
            id=run_id,
            started_at=started_at,
            duration_ms=duration_ms,
            base_ref=base_ref,
            head_ref=head_ref,
            target=target,
            merge_base=merge_base,
            test_command=self._test_command,
            language=self._language,
            threshold=self._threshold,
            time_budget_ms=int(budget * 1000),
            max_mutants=self._max_mutants,
            all_files=all_files,
        )
        summary = Summary(
            score=score,
            killed=killed,
            survived=survived,
            invalid=invalid,
            timeout=timeout,
            skipped=skipped,
            total=discovered_count,
            partial=partial,
            confidence=confidence,
            reason=" ".join(reasons),
        )
        return Report(
            schema_version="1.0",
            tool=ToolInfo(name="testproof", version=__version__),
            run=report_run,
            summary=summary,
            files=tuple(file_reports),
            errors=tuple(errors),
        )

    @staticmethod
    def _safe_path(workspace: Path, relative_path: str) -> Path:
        root = workspace.resolve()
        candidate = (root / relative_path).resolve()
        if not candidate.is_relative_to(root):
            msg = f"Path escapes the sandbox: {relative_path}"
            raise ValueError(msg)
        return candidate
