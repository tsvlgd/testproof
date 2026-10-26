"""Tests for the Python mutation adapter."""

from __future__ import annotations

import ast

from testproof.adapters.python import PythonAdapter

ADAPTER = PythonAdapter()
SHIPPING = '''"""Shipping rules for the demonstration fixture."""


def shipping_fee(order_total: int, member: bool = False) -> int:
    """Return the shipping fee for an order."""
    if order_total >= 50 and not member:
        return 0
    return 5
'''


def test_discovery_finds_shipping_operators() -> None:
    points = ADAPTER.discover("shipping.py", SHIPPING, None)
    found = {(point.line, point.operator, point.original, point.replacement) for point in points}

    assert (6, "comparison", ">=", ">") in found
    assert (6, "boolean", "and", "or") in found
    assert (6, "boolean", "not ", "") in found
    assert (7, "return", "0", "None") in found
    assert (7, "constant", "0", "1") in found
    assert (8, "return", "5", "None") in found
    # 5 and 50 are not in our operator set (only 0 and 1 are)
    assert (8, "constant", "5", "6") not in found
    assert (6, "constant", "50", "51") not in found


def test_discovery_ignores_docstrings_and_strings() -> None:
    source = 'MESSAGE = "0"\n\n\ndef label() -> str:\n    """Return 1."""\n    return "True"\n'
    points = ADAPTER.discover("label.py", source, None)

    assert points == []


def test_discovery_ignores_annotations_and_defaults() -> None:
    source = "def enabled(flag: bool = True) -> int:\n    return 1\n"
    points = ADAPTER.discover("enabled.py", source, None)

    # True is a default, should be ignored.
    # 1 is in the function body: return mutation and constant mutation.
    pairs = [(point.line, point.operator, point.original, point.replacement) for point in points]
    assert (2, "return", "1", "None") in pairs
    assert (2, "constant", "1", "0") in pairs
    # The default True should be absent
    assert all(point.original != "True" for point in points)


def test_discovery_limits_points_to_changed_lines() -> None:
    points = ADAPTER.discover("shipping.py", SHIPPING, {8})

    assert points
    assert {point.line for point in points} == {8}


def test_discovery_skips_equivalent_arithmetic() -> None:
    source = "def adjust(value: int) -> int:\n    return value + 0\n"
    points = ADAPTER.discover("adjust.py", source, None)

    # The + 0 is equivalent arithmetic, should be skipped.
    # The 0 constant should still produce a constant mutation.
    # The return should produce a return mutation.
    operators = [point.operator for point in points]
    assert "arithmetic" not in operators
    assert "return" in operators


def test_discovery_ids_are_stable() -> None:
    first = ADAPTER.discover("shipping.py", SHIPPING, None)
    second = ADAPTER.discover("shipping.py", SHIPPING, None)

    assert [point.id for point in first] == [point.id for point in second]


def test_apply_splices_only_the_operator() -> None:
    point = next(
        point for point in ADAPTER.discover("shipping.py", SHIPPING, None) if point.original == ">="
    )

    mutated = ADAPTER.apply(SHIPPING, point)

    assert "if order_total > 50 and not member:" in mutated
    assert mutated.replace("> 50", ">= 50", 1) == SHIPPING
    assert ADAPTER.validate(mutated)


def test_validate_rejects_broken_syntax() -> None:
    assert ADAPTER.validate("def broken(:\n    pass\n") is False
    assert ADAPTER.validate(SHIPPING) is True


def test_apply_keeps_the_module_parseable() -> None:
    for point in ADAPTER.discover("shipping.py", SHIPPING, None):
        mutated = ADAPTER.apply(SHIPPING, point)
        ast.parse(mutated)
        assert ADAPTER.validate(mutated)
