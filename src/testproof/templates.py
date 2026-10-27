"""Deterministic test templates built from distinguishing inputs.

For common mutation shapes the engine can find a killing input without a model
call. The candidate inputs are executed against the original function and the
mutant in an isolated interpreter. Only inputs that produce different results
are turned into tests, so every template is grounded in observed behavior.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from testproof.adapters.python import PythonAdapter
from testproof.models import Mutant
from testproof.probe import ProbeOutcome, module_for, probe_cases
from testproof.sandbox import Sandbox

MAX_CASES = 120
MAX_TEMPLATES = 5
_MAX_LITERAL_LENGTH = 200


@dataclass(frozen=True)
class TemplateResult:
    """Candidate tests and the evidence that produced them."""

    candidates: tuple[str, ...]
    cases_tried: int
    distinguishing: int
    equivalent_hint: bool
    note: str = ""


def generate(repo: Path, file_path: str, mutant: Mutant) -> TemplateResult:
    """Generate tests for a mutant without calling a model."""
    source_path = repo / file_path
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as exc:
        return TemplateResult((), 0, 0, False, f"cannot read source: {exc}")

    func = _find_function(tree, mutant.point.line)
    if func is None:
        return TemplateResult((), 0, 0, False, "no enclosing function found")

    module_info = module_for(repo, file_path)
    if module_info is None:
        return TemplateResult((), 0, 0, False, "module is not importable")
    module, _ = module_info

    cases = build_cases(repo, file_path, source, mutant, func)
    if not cases:
        return TemplateResult((), 0, 0, False, "no candidate inputs")

    with Sandbox(repo).create() as workspace:
        original, error = probe_cases(workspace, module, func.name, cases)
        if error is not None or original is None:
            return TemplateResult((), len(cases), 0, False, f"probe failed: {error}")

        target = workspace / file_path
        try:
            mutated_source = PythonAdapter().apply(source, mutant.point)
            target.write_text(mutated_source, encoding="utf-8")
        except (OSError, ValueError) as exc:
            return TemplateResult((), len(cases), 0, False, f"cannot apply mutation: {exc}")

        mutated, error = probe_cases(workspace, module, func.name, cases)
        if error is not None or mutated is None:
            return TemplateResult((), len(cases), 0, False, f"mutant probe failed: {error}")

    distinguishing = _distinguishing_cases(cases, original, mutated)
    candidates: list[str] = []
    for index, (case, expected) in enumerate(distinguishing[:MAX_TEMPLATES], 1):
        rendered = _render_test(module, func.name, case, expected, mutant, index)
        if rendered is not None:
            candidates.append(rendered)

    equivalent_hint = not distinguishing and _clamp_like(func)
    if distinguishing:
        note = f"{len(distinguishing)} distinguishing input(s) found"
    elif equivalent_hint:
        note = "no distinguishing input found; the mutation may be equivalent"
    else:
        note = "no distinguishing input found"
    return TemplateResult(
        candidates=tuple(candidates),
        cases_tried=len(cases),
        distinguishing=len(distinguishing),
        equivalent_hint=equivalent_hint,
        note=note,
    )


def build_cases(
    repo: Path,
    file_path: str,
    source: str,
    mutant: Mutant,
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[object, ...]]:
    """Build candidate argument tuples for one mutant."""
    params = _positional_params(func)
    if params is None:
        return []
    names = [arg.arg for arg in params]
    types = {arg.arg: _annotation_name(arg.annotation) for arg in params}
    defaults = _default_values(func, names)

    cases: list[tuple[object, ...]] = []
    seen: set[str] = set()

    def add(case: tuple[object, ...] | list[object]) -> None:
        values = _fill_case(tuple(case), names, defaults, types)
        if values is None:
            return
        key = repr(values)
        if key in seen:
            return
        seen.add(key)
        cases.append(values)

    line = _line_at(source, mutant.point.line)
    for case in _mutation_cases(line, mutant, names, types):
        add(case)

    for seed in _test_seeds(repo, func.name):
        add(seed)
        for variant in _seed_variants(seed, names, types):
            add(variant)

    for index, param_name in enumerate(names):
        for generic_value in _generic_values(param_name, types.get(param_name)):
            values = [defaults.get(name, _fallback_value(name, types.get(name))) for name in names]
            values[index] = generic_value
            add(values)

    if not names:
        add(())

    return cases[:MAX_CASES]


def _find_function(tree: ast.AST, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.lineno <= line <= (node.end_lineno or node.lineno)
    ]
    if not matches:
        return None
    return min(matches, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)


def _positional_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg] | None:
    args = func.args
    if args.kwonlyargs:
        required = [
            arg
            for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False)
            if default is None
        ]
        if required:
            return None
    return [*args.posonlyargs, *args.args]


def _annotation_name(annotation: ast.AST | None) -> str | None:
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value
    return None


def _default_values(
    func: ast.FunctionDef | ast.AsyncFunctionDef, names: list[str]
) -> dict[str, object]:
    defaults: dict[str, object] = {}
    positional = [*func.args.posonlyargs, *func.args.args]
    if not func.args.defaults:
        return defaults
    for arg, default in zip(
        positional[-len(func.args.defaults) :], func.args.defaults, strict=False
    ):
        if isinstance(default, ast.Constant):
            defaults[arg.arg] = default.value
    return defaults


def _fill_case(
    case: tuple[object, ...],
    names: list[str],
    defaults: dict[str, object],
    types: dict[str, str | None],
) -> tuple[object, ...] | None:
    if len(case) > len(names):
        return None
    values = list(case)
    for name in names[len(values) :]:
        if name in defaults:
            values.append(defaults[name])
        else:
            values.append(_fallback_value(name, types.get(name)))
    return tuple(values)


def _fallback_value(name: str, annotation: str | None) -> object:
    if "length" in name:
        return 0
    if name in ("low", "lo", "minimum", "min_value"):
        return 0
    if name in ("high", "hi", "maximum", "max_value"):
        return 10
    if name in ("base", "a", "b", "x", "y"):
        return 2
    if annotation == "bool":
        return False
    if annotation == "str":
        return ""
    if annotation == "float":
        return 0.0
    if annotation == "int":
        return 0
    return 0


def _generic_values(name: str, annotation: str | None) -> list[object]:
    if "length" in name:
        return [0, 1, 2, 5, 8, 10, 15]
    if name in ("low", "lo", "minimum", "min_value"):
        return [0, 1, -1, 5]
    if name in ("high", "hi", "maximum", "max_value"):
        return [0, 5, 10, 100]
    if annotation == "bool":
        return [True, False]
    if annotation == "float":
        return [0.0, 1.0, -1.0, 10.5, 50.0, 100.0, 101.0]
    if annotation == "int":
        return [-1, 0, 1, 2, 5, 10, 50, 99, 100, 101, 150, 151]
    if annotation == "str":
        return _string_values()
    return [0, 1, -1, "", "a", True, False]


def _string_values() -> list[object]:
    values: list[object] = [
        "",
        "a",
        "abc",
        "aaaaaaaa",
        "AAAAAAAA",
        "11111111",
        "!!!!!!!!",
        "aaaaaaaA",
        "aaaaaaaa1",
        "aaaaaaaa!",
        "11111111!",
        "AAAAAAAA!",
        "Password1!",
        "password",
        "PASSWORD1!",
        "1234567890",
        "12345abcde",
        "123456789012345",
        "1234567890123456",
        "user@example.com",
        "user@@example.com",
        "user@",
        "@example.com",
        "a@b",
        "hello",
    ]
    return values


def _test_seeds(repo: Path, func_name: str) -> list[tuple[object, ...]]:
    seeds: list[tuple[object, ...]] = []
    seen: set[str] = set()
    for path in _test_files(repo):
        try:
            text = path.read_text(encoding="utf-8")
            if len(text) > 200_000:
                continue
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called = node.func.attr
            else:
                continue
            if called != func_name:
                continue
            if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
                continue
            values: list[object] = []
            for arg in node.args:
                if not isinstance(arg, ast.Constant):
                    values = []
                    break
                values.append(arg.value)
            if not values:
                continue
            key = repr(tuple(values))
            if key not in seen:
                seen.add(key)
                seeds.append(tuple(values))
    return seeds


def _test_files(repo: Path) -> list[Path]:
    found: list[Path] = []
    for path in repo.rglob("*.py"):
        parts = set(path.parts)
        if parts.intersection({".git", ".venv", "__pycache__", "node_modules"}):
            continue
        name = path.name
        if name.startswith("test_") or name.endswith("_test.py"):
            found.append(path)
    return sorted(found)


def _seed_variants(
    seed: tuple[object, ...], names: list[str], types: dict[str, str | None]
) -> list[tuple[object, ...]]:
    variants: list[tuple[object, ...]] = []
    for index, value in enumerate(seed):
        if index >= len(names):
            break
        annotation = types.get(names[index])
        if annotation == "int" and isinstance(value, int) and not isinstance(value, bool):
            for delta in (-1, 1):
                changed = list(seed)
                changed[index] = value + delta
                variants.append(tuple(changed))
        elif annotation == "float" and isinstance(value, float):
            for float_delta in (-1.0, 1.0):
                changed = list(seed)
                changed[index] = value + float_delta
                variants.append(tuple(changed))
    return variants


def _mutation_cases(
    line: str,
    mutant: Mutant,
    names: list[str],
    types: dict[str, str | None],
) -> list[tuple[object, ...]]:
    cases: list[tuple[object, ...]] = []
    if not names:
        return cases

    def add(**values: object) -> None:
        cases.append(
            tuple(values.get(name, _fallback_value(name, types.get(name))) for name in names)
        )

    match = re.search(r"len\((\w+)\)\s*[<>]=?\s*(-?\d+)", line)
    if match:
        name, raw = match.groups()
        length = int(raw)
        for length_value in (length - 1, length, length + 1):
            add(**{name: "a" * max(0, length_value)})
            add(**{name: "1" * max(0, length_value)})

    match = re.search(r"(\w+)\s*[<>]=?\s*(-?\d+(?:\.\d+)?)", line)
    if match:
        name, raw = match.groups()
        number = float(raw)
        if number.is_integer():
            numbers: list[object] = [int(number) - 1, int(number), int(number) + 1]
        else:
            numbers = [number - 1, number, number + 1]
        for numeric_value in numbers:
            add(**{name: numeric_value})

    match = re.search(r"(-?\d+(?:\.\d+)?)\s*[<>]=?\s*(\w+)", line)
    if match:
        raw, name = match.groups()
        reverse_number = float(raw)
        if reverse_number.is_integer():
            reverse_numbers: list[object] = [
                int(reverse_number) - 1,
                int(reverse_number),
                int(reverse_number) + 1,
            ]
        else:
            reverse_numbers = [reverse_number - 1, reverse_number, reverse_number + 1]
        for numeric_value in reverse_numbers:
            add(**{name: numeric_value})

    match = re.search(r"(\w+)\s*(==|!=)\s*(['\"])(.*?)\3", line)
    if match:
        name, _, _, literal = match.groups()
        for literal_value in (literal, literal + "x", literal[:-1], ""):
            add(**{name: literal_value})

    if "isdigit" in line or "not " in line:
        for name in names:
            if types.get(name) == "str":
                for string_value in ("", "abc", "12345abcde", "1234567890"):
                    add(**{name: string_value})

    if "and" in line or "or" in line or mutant.point.operator == "boolean":
        for name in names:
            if types.get(name) == "str":
                for boolean_string in _string_values():
                    add(**{name: boolean_string})

    if mutant.point.operator == "constant" and mutant.point.original in ("0", "1"):
        for name in names:
            if types.get(name) in ("int", "float"):
                for constant_value in (-1, 0, 1, 2):
                    add(**{name: constant_value})

    if mutant.point.operator == "return" or mutant.point.operator == "constant":
        for name in names:
            if types.get(name) == "str":
                for return_string in _string_values():
                    add(**{name: return_string})
            elif types.get(name) in ("int", "float"):
                for return_value in (-1, 0, 1, 2, 50, 100, 101, 150):
                    add(**{name: return_value})
            elif types.get(name) == "bool":
                for bool_value in (True, False):
                    add(**{name: bool_value})

    cases.extend(_clamp_cases(line, names, types))
    cases.extend(_length_cases(line, names, types))
    return cases


def _clamp_cases(
    line: str, names: list[str], types: dict[str, str | None]
) -> list[tuple[object, ...]]:
    if len(names) < 3 or "low" not in names or "high" not in names:
        return []
    cases: list[tuple[object, ...]] = []
    for low, high in ((0, 10), (-10, 10), (0, 100), (5, 5)):
        for value in (low - 1, low, (low + high) // 2, high, high + 1):
            values = {
                "value": value,
                "item": value,
                "low": low,
                "high": high,
            }
            cases.append(
                tuple(values.get(name, _fallback_value(name, types.get(name))) for name in names)
            )
    return cases


def _length_cases(
    line: str, names: list[str], types: dict[str, str | None]
) -> list[tuple[object, ...]]:
    if "max_length" not in names:
        return []
    text_name = next((name for name in names if name != "max_length"), None)
    if text_name is None:
        return []
    cases: list[tuple[object, ...]] = []
    for length in (0, 2, 5, 10):
        cases.append(tuple("hello" if name == text_name else length for name in names))
    return cases


def _distinguishing_cases(
    cases: list[tuple[object, ...]],
    original: list[ProbeOutcome],
    mutated: list[ProbeOutcome],
) -> list[tuple[tuple[object, ...], str]]:
    found: list[tuple[tuple[object, ...], str]] = []
    for case, before, after in zip(cases, original, mutated, strict=False):
        if not before.ok or before.value_repr is None:
            continue
        if after.ok:
            if after.value_repr != before.value_repr:
                found.append((case, before.value_repr))
        elif after.error and after.error not in ("unrepresentable",):
            found.append((case, before.value_repr))
    return found


def _render_test(
    module: str,
    func_name: str,
    case: tuple[object, ...],
    expected_repr: str,
    mutant: Mutant,
    index: int,
) -> str | None:
    if len(expected_repr) > _MAX_LITERAL_LENGTH:
        return None
    args = ", ".join(repr(value) for value in case)
    test_name = f"test_repair_{mutant.point.id}_{index}"
    if expected_repr in ("True", "False"):
        assertion = f"assert {func_name}({args}) is {expected_repr}"
    elif expected_repr == "None":
        assertion = f"assert {func_name}({args}) is None"
    else:
        assertion = f"assert {func_name}({args}) == {expected_repr}"
    return (
        f"from {module} import {func_name}\n\n\n"
        f"def {test_name}():\n"
        f"    # Mutation at {mutant.point.path}:{mutant.point.line}: "
        f"{mutant.point.operator} {mutant.point.original} becomes "
        f"{mutant.point.replacement}.\n"
        f"    {assertion}\n"
    )


def _clamp_like(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    names = {arg.arg for arg in [*func.args.posonlyargs, *func.args.args]}
    return bool(
        names.intersection({"low", "lo", "minimum", "min_value"})
        and names.intersection({"high", "hi", "maximum", "max_value"})
    )


def _line_at(source: str, line: int) -> str:
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1]
    return ""
