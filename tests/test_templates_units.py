"""Unit tests for the deterministic template helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from testproof.models import Mutant, MutationPoint
from testproof.probe import ProbeOutcome
from testproof.templates import (
    _annotation_name,
    _clamp_cases,
    _default_values,
    _distinguishing_cases,
    _fallback_value,
    _fill_case,
    _find_function,
    _generic_values,
    _length_cases,
    _mutation_cases,
    _positional_params,
    _render_test,
    _seed_variants,
    _test_seeds,
    generate,
)


def _func(source: str) -> ast.FunctionDef:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def _mutant(
    line: int = 2,
    operator: str = "comparison",
    original: str = ">=",
    replacement: str = ">",
    *,
    path: str = "mod.py",
) -> Mutant:
    point = MutationPoint(
        id="abc123",
        path=path,
        line=line,
        column=0,
        end_line=line,
        end_column=1,
        operator=operator,
        original=original,
        replacement=replacement,
    )
    return Mutant(point=point, status="survived")


def test_find_function_returns_none_outside_a_function() -> None:
    assert _find_function(ast.parse("X = 1\n"), 1) is None


def test_positional_params_handles_keyword_only_arguments() -> None:
    required = _func("def f(a, *, b):\n    return a\n")
    optional = _func("def f(a, *, b=1):\n    return a\n")

    assert _positional_params(required) is None
    params = _positional_params(optional)
    assert params is not None
    assert [arg.arg for arg in params] == ["a"]


def test_annotation_name_handles_names_strings_and_none() -> None:
    assert _annotation_name(ast.Name(id="int")) == "int"
    assert _annotation_name(ast.Constant(value="float")) == "float"
    assert _annotation_name(None) is None
    assert _annotation_name(ast.Constant(value=1)) is None


def test_default_values_reads_only_literal_defaults() -> None:
    func = _func("def f(a, b=2, c='x', d=None, e=object()):\n    return a\n")

    defaults = _default_values(func, ["a", "b", "c", "d", "e"])

    assert defaults == {"b": 2, "c": "x", "d": None}
    assert _default_values(_func("def f(a):\n    return a\n"), ["a"]) == {}


def test_fill_case_rejects_extra_values_and_fills_missing_ones() -> None:
    assert _fill_case((1, 2), ["a"], {}, {}) is None
    assert _fill_case((1,), ["a", "b", "c"], {"b": 7}, {"c": "str"}) == (1, 7, "")


def test_fallback_value_prefers_names_then_annotations() -> None:
    assert _fallback_value("min_length", "int") == 0
    assert _fallback_value("low", "int") == 0
    assert _fallback_value("high", "int") == 10
    assert _fallback_value("base", "int") == 2
    assert _fallback_value("flag", "bool") is False
    assert _fallback_value("text", "str") == ""
    assert _fallback_value("ratio", "float") == 0.0
    assert _fallback_value("count", "int") == 0
    assert _fallback_value("other", None) == 0


def test_generic_values_covers_named_and_typed_parameters() -> None:
    assert _generic_values("max_length", None)[0] == 0
    assert _generic_values("low", None) == [0, 1, -1, 5]
    assert _generic_values("high", None) == [0, 5, 10, 100]
    assert _generic_values("flag", "bool") == [True, False]
    assert _generic_values("ratio", "float")[:2] == [0.0, 1.0]
    assert _generic_values("count", "int")[0] == -1
    assert "Password1!" in _generic_values("text", "str")
    assert _generic_values("other", None) == [0, 1, -1, "", "a", True, False]


def test_test_seeds_reads_literal_calls_and_skips_other_calls(tmp_path: Path) -> None:
    (tmp_path / "test_mod.py").write_text(
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
        "    add(a=1)\n"
        "    add(*args)\n"
        "    add(value)\n"
        "    helper.add(4, 5)\n"
        "    getattr(helper, 'add')(6, 7)\n",
        encoding="utf-8",
    )
    (tmp_path / "helper.py").write_text("add(9, 9)\n", encoding="utf-8")
    (tmp_path / "test_broken.py").write_text("def test(:\n", encoding="utf-8")

    assert set(_test_seeds(tmp_path, "add")) == {(1, 2), (4, 5)}


def test_seed_variants_handles_int_float_and_short_seeds() -> None:
    assert _seed_variants((5,), ["a", "b"], {"a": "int"}) == [(4,), (6,)]
    assert _seed_variants((2.5,), ["a"], {"a": "float"}) == [(1.5,), (3.5,)]
    assert _seed_variants((True,), ["a"], {"a": "int"}) == []
    assert _seed_variants((1, 2, 3), ["a"], {"a": "int"}) == [(0, 2, 3), (2, 2, 3)]


def test_mutation_cases_covers_length_numbers_reverse_strings_and_returns() -> None:
    length_cases = _mutation_cases(
        "if len(name) <= 15:",
        _mutant(),
        ["name"],
        {"name": "str"},
    )
    assert ("a" * 14,) in length_cases
    assert ("1" * 16,) in length_cases

    float_cases = _mutation_cases(
        "if total >= 2.5:",
        _mutant(),
        ["total"],
        {"total": "float"},
    )
    assert (1.5,) in float_cases
    assert (3.5,) in float_cases

    reverse_cases = _mutation_cases(
        "if 50 <= total:",
        _mutant(original="<=", replacement="<"),
        ["total"],
        {"total": "int"},
    )
    assert (49,) in reverse_cases
    assert (51,) in reverse_cases

    literal_cases = _mutation_cases(
        'if status == "open":',
        _mutant(original="==", replacement="!="),
        ["status"],
        {"status": "str"},
    )
    assert ("open",) in literal_cases
    assert ("openx",) in literal_cases
    assert ("",) in literal_cases

    digit_cases = _mutation_cases(
        "if name.isdigit() or not name:",
        _mutant(operator="boolean"),
        ["name"],
        {"name": "str"},
    )
    assert ("1234567890",) in digit_cases

    constant_cases = _mutation_cases(
        "return 0",
        _mutant(operator="constant", original="0", replacement="1"),
        ["count"],
        {"count": "int"},
    )
    assert (0,) in constant_cases
    assert (2,) in constant_cases

    return_cases = _mutation_cases(
        "return value",
        _mutant(operator="return", original="value", replacement="None"),
        ["text", "count", "flag"],
        {"text": "str", "count": "int", "flag": "bool"},
    )
    assert any(isinstance(case[0], str) for case in return_cases)
    assert any(case[1] == 150 for case in return_cases)
    assert any(case[2] is True for case in return_cases)


def test_mutation_cases_returns_empty_without_parameters() -> None:
    assert _mutation_cases("return 0", _mutant(), [], {}) == []


def test_clamp_cases_requires_low_high_and_builds_ranges() -> None:
    assert _clamp_cases("if value <= low:", ["value", "low"], {}) == []

    cases = _clamp_cases("if value <= low:", ["value", "low", "high"], {})

    assert (0, 0, 10) in cases
    assert (11, 0, 10) in cases
    assert (5, 0, 10) in cases


def test_length_cases_requires_text_and_max_length() -> None:
    assert _length_cases("if len(text) > max_length:", ["text"], {}) == []
    assert _length_cases("if len(text) > max_length:", ["max_length"], {}) == []

    cases = _length_cases("if len(text) > max_length:", ["text", "max_length"], {})

    assert ("hello", 0) in cases
    assert ("hello", 10) in cases


def test_distinguishing_cases_ignores_missing_and_unrepresentable_results() -> None:
    cases = [(1,), (2,), (3,)]
    original = [
        ProbeOutcome(ok=False, error="boom"),
        ProbeOutcome(ok=True, value_repr="1"),
        ProbeOutcome(ok=True, value_repr="2"),
    ]
    mutated = [
        ProbeOutcome(ok=True, value_repr="1"),
        ProbeOutcome(ok=False, error="unrepresentable"),
        ProbeOutcome(ok=False, error="ValueError: no"),
    ]

    assert _distinguishing_cases(cases, original, mutated) == [((3,), "2")]


def test_render_test_handles_bool_none_and_long_values() -> None:
    mutant = _mutant()

    assert "is True" in (_render_test("mod", "check", (1,), "True", mutant, 1) or "")
    assert "is None" in (_render_test("mod", "check", (1,), "None", mutant, 1) or "")
    assert "== 5" in (_render_test("mod", "check", (1,), "5", mutant, 1) or "")
    assert _render_test("mod", "check", (1,), "x" * 300, mutant, 1) is None


def test_generate_reports_missing_source_and_unimportable_module(tmp_path: Path) -> None:
    missing = generate(tmp_path, "missing.py", _mutant(path="missing.py"))
    assert "cannot read source" in missing.note

    (tmp_path / "bad-name.py").write_text(
        "def check(value: int) -> int:\n    return value > 1\n",
        encoding="utf-8",
    )
    unimportable = generate(tmp_path, "bad-name.py", _mutant(path="bad-name.py"))
    assert unimportable.note == "module is not importable"


def test_generate_reports_no_cases_for_required_keyword_only(tmp_path: Path) -> None:
    source = "def check(value: int, *, required: int) -> int:\n    return value > required\n"
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")

    result = generate(tmp_path, "mod.py", _mutant())

    assert result.candidates == ()
    assert result.note == "no candidate inputs"


def test_generate_reports_invalid_mutation_point(tmp_path: Path) -> None:
    source = "def check(value: int) -> int:\n    return value > 1\n"
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")
    (tmp_path / "test_mod.py").write_text(
        "from mod import check\n\ndef test_check():\n    assert check(2) == 1\n",
        encoding="utf-8",
    )

    result = generate(
        tmp_path,
        "mod.py",
        _mutant(original="<=", replacement="<"),
    )

    assert result.candidates == ()
    assert "cannot apply mutation" in result.note


def test_generate_reports_no_enclosing_function(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text('"""Module."""\n', encoding="utf-8")

    result = generate(tmp_path, "mod.py", _mutant(line=1))

    assert result.candidates == ()
    assert result.note == "no enclosing function found"
