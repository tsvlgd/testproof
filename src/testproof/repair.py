"""Verified repair: propose tests with an open model, verify with the engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from testproof.model import ModelClient
from testproof.models import Mutant, Report
from testproof.runner import run_tests
from testproof.sandbox import Sandbox


@dataclass(frozen=True)
class VerificationRecord:
    """Evidence for a proposed test."""

    test_id: str
    mutant_id: str
    passes_on_original: bool
    fails_on_mutant: bool
    full_suite_passes: bool
    has_assertion: bool
    touches_production_code: bool
    decision: str  # "kept" or "rejected"
    reason: str


@dataclass
class RepairResult:
    """Result of a repair run."""

    kept: list[tuple[str, str]] = field(default_factory=list)  # (mutant_id, test_code)
    rejected: list[VerificationRecord] = field(default_factory=list)
    applied: bool = False


class RepairEngine:
    """Propose and verify tests for surviving mutants."""

    def __init__(
        self,
        repo: Path,
        test_command: str,
        model_client: ModelClient,
    ) -> None:
        self._repo = repo.resolve()
        self._test_command = test_command
        self._model = model_client

    def repair(
        self,
        report: Report,
        *,
        dry_run: bool = False,
        apply: bool = False,
    ) -> RepairResult:
        result = RepairResult(applied=apply)

        survivors = [(f.path, m) for f in report.files for m in f.mutants if m.status == "survived"]

        for i, (file_path, mutant) in enumerate(survivors, 1):
            test_id = f"t-{i:03d}"
            candidate = self._propose_test(file_path, mutant)
            if candidate is None:
                record = VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=False,
                    fails_on_mutant=False,
                    full_suite_passes=False,
                    has_assertion=False,
                    touches_production_code=False,
                    decision="rejected",
                    reason="model returned no valid test",
                )
                result.rejected.append(record)
                continue

            has_assertion = "assert" in candidate
            record = self._verify(file_path, mutant, candidate, test_id)
            record = VerificationRecord(
                test_id=record.test_id,
                mutant_id=record.mutant_id,
                passes_on_original=record.passes_on_original,
                fails_on_mutant=record.fails_on_mutant,
                full_suite_passes=record.full_suite_passes,
                has_assertion=has_assertion,
                touches_production_code=False,
                decision=record.decision,
                reason=record.reason,
            )

            if record.decision == "kept":
                result.kept.append((mutant.point.id, candidate))
                if apply:
                    self._apply_test(file_path, candidate)
            else:
                result.rejected.append(record)

        return result

    def _propose_test(self, file_path: str, mutant: Mutant) -> str | None:
        """Ask the model for a test that kills the mutant."""
        source_path = self._repo / file_path
        if not source_path.exists():
            return None
        source = source_path.read_text(encoding="utf-8")

        # Find test file
        test_path = self._find_test_file(file_path)
        existing_tests = ""
        if test_path is not None and test_path.exists():
            existing_tests = test_path.read_text(encoding="utf-8")

        prompt = _build_prompt(
            file_path=file_path,
            source=source,
            existing_tests=existing_tests,
            mutant=mutant,
        )

        try:
            response = self._model.complete(prompt)
        except Exception:
            return None

        # Extract test function from response
        return _extract_test(response)

    def _verify(
        self, file_path: str, mutant: Mutant, candidate: str, test_id: str
    ) -> VerificationRecord:
        """Verify a candidate test against the mutant."""
        passes_on_original = False
        fails_on_mutant = False
        full_suite_passes = False

        with Sandbox(self._repo).create() as workspace:
            # Write candidate test to temp file
            test_file = workspace / f"test_repair_{test_id.replace('-', '_')}.py"
            test_file.write_text(candidate, encoding="utf-8")

            # 1. Run on original code - must pass
            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=30,
            )
            passes_on_original = not result.killed and not result.timed_out

            if not passes_on_original:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=False,
                    fails_on_mutant=False,
                    full_suite_passes=False,
                    has_assertion="assert" in candidate,
                    touches_production_code=False,
                    decision="rejected",
                    reason="candidate fails on original code",
                )

            # 2. Apply mutant and run - must fail
            source_path = workspace / file_path
            original_source = source_path.read_text(encoding="utf-8")
            mutated_source = self._apply_mutation(original_source, mutant)
            source_path.write_text(mutated_source, encoding="utf-8")

            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=30,
            )
            fails_on_mutant = result.killed and not result.timed_out

            # Restore original
            source_path.write_text(original_source, encoding="utf-8")

            if not fails_on_mutant:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=True,
                    fails_on_mutant=False,
                    full_suite_passes=False,
                    has_assertion="assert" in candidate,
                    touches_production_code=False,
                    decision="rejected",
                    reason="candidate does not kill the mutant",
                )

            # 3. Full suite on original - must pass
            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=30,
            )
            full_suite_passes = not result.killed and not result.timed_out

            if not full_suite_passes:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=True,
                    fails_on_mutant=True,
                    full_suite_passes=False,
                    has_assertion="assert" in candidate,
                    touches_production_code=False,
                    decision="rejected",
                    reason="candidate breaks the full suite",
                )

            return VerificationRecord(
                test_id=test_id,
                mutant_id=mutant.point.id,
                passes_on_original=True,
                fails_on_mutant=True,
                full_suite_passes=True,
                has_assertion="assert" in candidate,
                touches_production_code=False,
                decision="kept",
                reason="killed mutant and passed full suite",
            )

    def _apply_mutation(self, source: str, mutant: Mutant) -> str:
        """Apply a mutation point to source."""
        from testproof.adapters.python import PythonAdapter

        adapter = PythonAdapter()
        return adapter.apply(source, mutant.point)

    def _find_test_file(self, source_path: str) -> Path | None:
        """Find the test file for a source file."""
        source = Path(source_path)
        # Try common patterns
        candidates = [
            self._repo / f"test_{source.name}",
            self._repo / f"{source.stem}_test.py",
            self._repo / "tests" / f"test_{source.name}",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _apply_test(self, file_path: str, test_code: str) -> None:
        """Apply a verified test to the test file."""
        test_path = self._find_test_file(file_path)
        if test_path is None:
            # Create a new test file
            source = Path(file_path)
            test_path = self._repo / f"test_{source.name}"
        existing = test_path.read_text(encoding="utf-8") if test_path.exists() else ""
        test_path.write_text(existing + "\n\n" + test_code + "\n", encoding="utf-8")


def _build_prompt(
    file_path: str,
    source: str,
    existing_tests: str,
    mutant: Mutant,
) -> str:
    """Build the repair prompt."""
    return f"""You are a test engineer. Given a Python function, a mutation,
and existing tests, write one new test function that:
1. Passes on the original code
2. Fails on the mutated code
3. Uses the same test framework and imports as existing tests
4. Contains at least one assertion
5. Does not modify production code

File: {file_path}
Line: {mutant.point.line}
Operator: {mutant.point.operator}
Original: {mutant.point.original}
Replacement: {mutant.point.replacement}

Original source:
```python
{source}
```

Mutated source (the bug):
```python
{mutant.point.original} -> {mutant.point.replacement}
```

Existing tests:
```python
{existing_tests}
```

Output ONLY the test function. No explanation, no markdown, no extra text.
"""


def _extract_test(response: str) -> str | None:
    """Extract a test function from the model response."""
    # Remove markdown code blocks
    response = re.sub(r"```python\s*", "", response)
    response = re.sub(r"```\s*", "", response)
    response = response.strip()

    if not response:
        return None

    # Find the test function and any preceding imports
    match = re.search(
        r"((?:^(?:from |import ).*\n)*)(def test_\w+\(.*?\):.*)", response, re.DOTALL | re.MULTILINE
    )
    if match:
        imports = match.group(1).strip()
        func = match.group(2).strip()
        if imports:
            return imports + "\n\n" + func
        return func

    # If no def test_ found, check if it starts with def
    if response.startswith("def "):
        return response

    return None
