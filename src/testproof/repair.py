"""Verified repair: propose tests, then prove them against the mutant."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from testproof.model import ModelClient
from testproof.models import Mutant, Report
from testproof.runner import run_tests
from testproof.sandbox import Sandbox, isolated_env
from testproof.templates import TemplateResult
from testproof.templates import generate as generate_templates


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
    equivalent: list[str] = field(default_factory=list)
    applied: bool = False
    template_hits: int = 0
    model_attempts: int = 0

    @property
    def survivors(self) -> int:
        return len(self.kept) + len(self.rejected) + len(self.equivalent)


class RepairEngine:
    """Propose and verify tests for surviving mutants."""

    def __init__(
        self,
        repo: Path,
        test_command: str,
        model_client: ModelClient | None,
        *,
        verify_timeout_seconds: int = 60,
    ) -> None:
        self._repo = repo.resolve()
        self._test_command = test_command
        self._model = model_client
        self._verify_timeout_seconds = verify_timeout_seconds

    def repair(
        self,
        report: Report,
        *,
        dry_run: bool = False,
        apply: bool = False,
        force_model: bool = False,
        use_templates: bool = True,
    ) -> RepairResult:
        del dry_run
        result = RepairResult(applied=apply)

        survivors = [(f.path, m) for f in report.files for m in f.mutants if m.status == "survived"]

        for i, (file_path, mutant) in enumerate(survivors, 1):
            test_id = f"t-{i:03d}"

            if use_templates:
                template = generate_templates(self._repo, file_path, mutant)
            else:
                template = TemplateResult((), 0, 0, False, "deterministic templates disabled")
            template_reasons: list[str] = []
            template_kept = False
            for j, template_code in enumerate(template.candidates, 1):
                record = self._verify(file_path, mutant, template_code, f"{test_id}-t{j}")
                if record.decision == "kept":
                    result.kept.append((mutant.point.id, template_code))
                    result.template_hits += 1
                    if apply:
                        self._apply_test(file_path, template_code)
                    template_kept = True
                    break
                template_reasons.append(f"{record.test_id}: {record.reason}")
            if template_kept:
                continue

            if template.equivalent_hint and not force_model:
                result.equivalent.append(mutant.point.id)
                continue

            feedback = _template_feedback(template, template_reasons)
            model_code, model_error = self._propose_test(file_path, mutant, feedback=feedback)
            result.model_attempts += 1
            if model_code is None:
                result.rejected.append(
                    VerificationRecord(
                        test_id=test_id,
                        mutant_id=mutant.point.id,
                        passes_on_original=False,
                        fails_on_mutant=False,
                        full_suite_passes=False,
                        has_assertion=False,
                        touches_production_code=False,
                        decision="rejected",
                        reason=_no_model_reason(template, self._model is None, model_error),
                    )
                )
                continue

            record = self._verify(file_path, mutant, model_code, test_id)
            if record.decision == "kept":
                result.kept.append((mutant.point.id, model_code))
                if apply:
                    self._apply_test(file_path, model_code)
            else:
                result.rejected.append(record)

        return result

    def _propose_test(
        self,
        file_path: str,
        mutant: Mutant,
        *,
        feedback: str = "",
    ) -> tuple[str | None, str | None]:
        """Ask the model for a test that kills the mutant.

        Returns the test code and an error message. Exactly one is set.
        """
        if self._model is None:
            return None, "model is not configured"
        source_path = self._repo / file_path
        if not source_path.exists():
            return None, f"source file not found: {file_path}"
        source = source_path.read_text(encoding="utf-8")

        test_path = self._find_test_file(file_path)
        existing_tests = ""
        if test_path is not None and test_path.exists():
            existing_tests = test_path.read_text(encoding="utf-8")

        prompt = _build_prompt(
            file_path=file_path,
            function_source=_function_source(source, mutant.point.line),
            mutated_line=_line_at(source, mutant.point.line),
            existing_tests=existing_tests,
            mutant=mutant,
            feedback=feedback,
        )

        try:
            response = self._model.complete(prompt)
        except Exception as exc:
            return None, f"model call failed: {type(exc).__name__}: {exc}"

        candidate = _extract_test(response, existing_tests)
        if candidate is None:
            return None, "model response did not contain a test function"
        return candidate, None

    def _verify(
        self, file_path: str, mutant: Mutant, candidate: str, test_id: str
    ) -> VerificationRecord:
        """Verify a candidate test against the mutant."""
        passes_on_original = False
        fails_on_mutant = False
        full_suite_passes = False
        has_assertion = "assert" in candidate

        if not has_assertion:
            return VerificationRecord(
                test_id=test_id,
                mutant_id=mutant.point.id,
                passes_on_original=False,
                fails_on_mutant=False,
                full_suite_passes=False,
                has_assertion=False,
                touches_production_code=False,
                decision="rejected",
                reason="candidate has no assertion",
            )

        with Sandbox(self._repo).create() as workspace:
            test_file = _candidate_test_path(workspace, test_id)
            if "import" not in candidate and "from " not in candidate:
                test_path = self._find_test_file(file_path)
                if test_path is not None and test_path.exists():
                    existing = test_path.read_text(encoding="utf-8")
                    imports = [
                        line
                        for line in existing.splitlines()
                        if line.startswith("import ") or line.startswith("from ")
                    ]
                    if imports:
                        candidate = "\n".join(imports) + "\n\n" + candidate
            test_file.write_text(candidate, encoding="utf-8")
            env = isolated_env(workspace)

            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=self._verify_timeout_seconds,
                env=env,
            )
            passes_on_original = not result.killed and not result.timed_out

            if not passes_on_original:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=False,
                    fails_on_mutant=False,
                    full_suite_passes=False,
                    has_assertion=has_assertion,
                    touches_production_code=False,
                    decision="rejected",
                    reason="candidate fails on original code",
                )

            source_path = workspace / file_path
            original_source = source_path.read_text(encoding="utf-8")
            mutated_source = self._apply_mutation(original_source, mutant)
            source_path.write_text(mutated_source, encoding="utf-8")

            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=self._verify_timeout_seconds,
                env=env,
            )
            fails_on_mutant = result.killed and not result.timed_out

            source_path.write_text(original_source, encoding="utf-8")

            if not fails_on_mutant:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=True,
                    fails_on_mutant=False,
                    full_suite_passes=False,
                    has_assertion=has_assertion,
                    touches_production_code=False,
                    decision="rejected",
                    reason="candidate does not kill the mutant",
                )

            result = run_tests(
                self._test_command,
                cwd=workspace,
                timeout_seconds=self._verify_timeout_seconds,
                env=env,
            )
            full_suite_passes = not result.killed and not result.timed_out

            if not full_suite_passes:
                return VerificationRecord(
                    test_id=test_id,
                    mutant_id=mutant.point.id,
                    passes_on_original=True,
                    fails_on_mutant=True,
                    full_suite_passes=False,
                    has_assertion=has_assertion,
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
                has_assertion=has_assertion,
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
        """Find an existing test file for a source file."""
        source = Path(source_path)
        candidates = [
            self._repo / "tests" / f"test_{source.name}",
            self._repo / "tests" / f"{source.stem}_test.py",
            self._repo / f"test_{source.name}",
            self._repo / f"{source.stem}_test.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _apply_test(self, file_path: str, test_code: str) -> None:
        """Append a verified test to the project test file.

        Add only imports the file does not already have, then append the test
        body. Reapplying a repair must not duplicate the suite header.
        """
        test_path = self._find_test_file(file_path)
        if test_path is None:
            tests_dir = self._repo / "tests"
            if tests_dir.is_dir():
                test_path = tests_dir / f"test_{Path(file_path).name}"
            else:
                test_path = self._repo / f"test_{Path(file_path).name}"
        existing = test_path.read_text(encoding="utf-8") if test_path.exists() else ""
        imports, body = _split_test_code(test_code)
        if not body:
            return
        if existing:
            missing = [line for line in imports if line not in existing]
            if missing:
                existing = "\n".join(missing) + "\n\n" + existing.lstrip()
            test_path.write_text(
                existing.rstrip() + "\n\n\n" + body.strip() + "\n",
                encoding="utf-8",
            )
            return
        prefix = "\n".join(imports) + "\n\n" if imports else ""
        test_path.write_text(prefix + body.strip() + "\n", encoding="utf-8")


_MUTATION_HINTS: dict[str, str] = {
    "comparison": (
        "The mutation changes a comparison operator. Find the exact boundary "
        "value where the original and the mutant disagree."
    ),
    "boolean": (
        "The mutation changes a boolean operator. Find an input where only one "
        "part of the condition is true, so and/or produce different results."
    ),
    "arithmetic": (
        "The mutation changes an arithmetic operator. Find an input where the "
        "two operations produce different results."
    ),
    "return": (
        "The mutation replaces a return expression with None. Find an input that "
        "reaches that return statement and show that the original does not return None."
    ),
    "constant": (
        "The mutation changes a constant such as 0, 1, True, or False. Find an "
        "input that reaches the changed constant and show the original result."
    ),
}


def _build_prompt(
    file_path: str,
    function_source: str,
    mutated_line: str,
    existing_tests: str,
    mutant: Mutant,
    feedback: str = "",
) -> str:
    """Build the repair prompt with a worked example and mutation hints."""
    hint = _MUTATION_HINTS.get(
        mutant.point.operator, "Find an input that distinguishes the two versions."
    )
    feedback_block = f"\nDeterministic probe result:\n{feedback}\n" if feedback else ""
    return f"""You are a test engineer repairing a surviving mutant in a Python test suite.

Goal: write one test that passes on the original code, fails on the mutated code,
and still passes when added to the full suite.

Worked example:
Original: def shipping_fee(total: int) -> int: return 0 if total >= 50 else 5
Mutation: comparison >= becomes > at line 2
At total=50 the original returns 0 and the mutant returns 5.
Test: assert shipping_fee(50) == 0

Step 1: Read the mutation.
The original line uses `{mutant.point.original}`. The mutant changes it to
`{mutant.point.replacement}`. {hint}

Step 2: Find the distinguishing input.
Ask: what input makes the original produce a different observable result from
the mutant? Prefer a boundary value, an empty or negative value, a single
condition, or a value that exercises the changed constant.

Step 3: Write the test.
The test must pass on the original code, fail on the mutant, use the existing
test framework, and contain at least one assertion. Do not change production
code. Use the existing imports when they already import the function.

File: {file_path}
Line: {mutant.point.line}
Operator: {mutant.point.operator}
Original: {mutant.point.original}
Replacement: {mutant.point.replacement}

Mutated line:
```python
{mutated_line}
```

Function source:
```python
{function_source}
```

Existing tests:
```python
{existing_tests}
```
{feedback_block}
Output exactly one fenced Python code block containing the complete test and
its imports. Do not include reasoning after the block.
"""


def _extract_test(response: str, existing_tests: str = "") -> str | None:
    """Extract one new test function and its imports from the model response.

    Models sometimes echo the existing suite and append a new test. Keep only
    the first test whose name is not already present so applying repair does
    not duplicate the suite.
    """
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", response, re.DOTALL)
    for block in blocks:
        if re.search(r"\bdef test_\w+\s*\(", block):
            response = block
            break

    response = re.sub(r"```python\s*", "", response)
    response = re.sub(r"```\s*", "", response)
    response = response.strip()

    if not response:
        return None

    existing_names = _test_names(existing_tests)

    try:
        tree = ast.parse(response)
    except SyntaxError:
        return _extract_test_fallback(response, existing_names)

    imports: list[str] = []
    seen: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        line = ast.get_source_segment(response, node)
        if line and line not in seen:
            seen.add(line)
            imports.append(line)

    lines = response.splitlines()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_") or node.name in existing_names:
            continue
        start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        end = node.end_lineno or node.lineno
        func = "\n".join(lines[start - 1 : end])
        if imports:
            return "\n".join(imports) + "\n\n" + func
        return func

    return None


def _split_test_code(test_code: str) -> tuple[list[str], str]:
    """Split test code into imports and the test body."""
    lines = test_code.strip().splitlines()
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        fallback_imports = [line for line in lines if line.startswith(("import ", "from "))]
        body = "\n".join(
            line for line in lines if not line.startswith(("import ", "from "))
        ).strip()
        return fallback_imports, body

    imports: list[str] = []
    body_start = len(lines)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            segment = ast.get_source_segment(test_code, node)
            if segment:
                imports.append(segment)
            continue
        start = node.lineno
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        body_start = min(body_start, start)
    return imports, "\n".join(lines[body_start - 1 :]).strip()


def _test_names(source: str) -> set[str]:
    """Return every test function name defined in a source string."""
    if not source.strip():
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set(re.findall(r"^\s*(?:async )?def (test_\w+)\s*\(", source, re.MULTILINE))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _extract_test_fallback(response: str, existing_names: set[str]) -> str | None:
    """Extract a test when the response is not valid Python."""
    matches = list(re.finditer(r"^(?:async )?def (test_\w+)\s*\(", response, re.MULTILINE))
    for index, match in enumerate(matches):
        name = match.group(1)
        if name in existing_names:
            continue
        start = match.start()
        lines = response[:start].splitlines()
        while lines and lines[-1].lstrip().startswith("@"):
            start -= len(lines[-1]) + 1
            lines.pop()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        func = response[start:end].strip()
        imports = [
            line for line in response[:start].splitlines() if line.startswith(("import ", "from "))
        ]
        if imports:
            return "\n".join(imports) + "\n\n" + func
        return func
    return None


def _template_feedback(template: TemplateResult, reasons: list[str]) -> str:
    parts = [template.note]
    if reasons:
        parts.append(
            "Accepted template tests were rejected for these reasons: " + "; ".join(reasons)
        )
    return ". ".join(part for part in parts if part)


def _no_model_reason(
    template: TemplateResult,
    model_missing: bool = False,
    model_error: str | None = None,
) -> str:
    if model_missing:
        return "model is not configured and deterministic templates found no test" + (
            f"; {template.note}" if template.note else ""
        )
    parts = ["model returned no valid test"]
    if model_error:
        parts.append(model_error)
    if template.note:
        parts.append(template.note)
    return "; ".join(parts)


def _function_source(source: str, line: int) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= line <= (node.end_lineno or node.lineno)
    ]
    if not matches:
        return source
    func = min(matches, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
    lines = source.splitlines()
    start = max(0, func.lineno - 1)
    end = func.end_lineno or func.lineno
    return "\n".join(lines[start:end])


def _line_at(source: str, line: int) -> str:
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1]
    return ""


def _candidate_test_path(workspace: Path, test_id: str) -> Path:
    name = f"test_repair_{test_id.replace('-', '_')}.py"
    tests_dir = workspace / "tests"
    if tests_dir.is_dir():
        return tests_dir / name
    return workspace / name
