"""Tests for deterministic repair templates."""

from __future__ import annotations

from pathlib import Path

from testproof.models import Mutant, MutationPoint
from testproof.templates import generate


def _mutant(
    path: str,
    line: int,
    operator: str,
    original: str,
    replacement: str,
    *,
    column: int = 0,
    end_line: int | None = None,
    end_column: int = 0,
) -> Mutant:
    point = MutationPoint(
        id="abc123",
        path=path,
        line=line,
        column=column,
        end_line=end_line or line,
        end_column=end_column,
        operator=operator,
        original=original,
        replacement=replacement,
    )
    return Mutant(point=point, status="survived")


def test_generate_boundary_test_for_comparison(tmp_path: Path) -> None:
    (tmp_path / "shipping.py").write_text(
        "def shipping_fee(order_total: int) -> int:\n"
        "    if order_total >= 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    (tmp_path / "test_shipping.py").write_text(
        "from shipping import shipping_fee\n\n"
        "def test_free():\n"
        "    assert shipping_fee(100) == 0\n\n"
        "def test_paid():\n"
        "    assert shipping_fee(10) == 5\n",
        encoding="utf-8",
    )

    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)
    result = generate(tmp_path, "shipping.py", mutant)

    assert result.equivalent_hint is False
    assert result.distinguishing >= 1
    assert any("assert shipping_fee(50) == 0" in candidate for candidate in result.candidates)


def test_generate_constant_test_for_clamp_score(tmp_path: Path) -> None:
    (tmp_path / "validator.py").write_text(
        "def clamp_score(score: int) -> int:\n"
        "    if score < 0:\n"
        "        return 0\n"
        "    if score > 100:\n"
        "        return 100\n"
        "    return score\n",
        encoding="utf-8",
    )
    (tmp_path / "test_validator.py").write_text(
        "from validator import clamp_score\n\n"
        "def test_clamp():\n"
        "    assert clamp_score(50) == 50\n",
        encoding="utf-8",
    )

    mutant = _mutant("validator.py", 3, "constant", "0", "1", column=15, end_column=16)
    result = generate(tmp_path, "validator.py", mutant)

    assert result.distinguishing >= 1
    assert any("clamp_score(-1) == 0" in candidate for candidate in result.candidates)


def test_generate_boolean_test_for_password(tmp_path: Path) -> None:
    (tmp_path / "validator.py").write_text(
        "def is_strong_password(password: str) -> bool:\n"
        "    if len(password) < 8:\n"
        "        return False\n"
        "    has_upper = any(c.isupper() for c in password)\n"
        "    has_lower = any(c.islower() for c in password)\n"
        "    has_digit = any(c.isdigit() for c in password)\n"
        "    has_special = any(c in '!@#$%^&*' for c in password)\n"
        "    return has_upper and has_lower and has_digit and has_special\n",
        encoding="utf-8",
    )
    (tmp_path / "test_validator.py").write_text(
        "from validator import is_strong_password\n\n"
        "def test_password():\n"
        "    assert is_strong_password('Password1!') is True\n",
        encoding="utf-8",
    )

    mutant = _mutant("validator.py", 8, "boolean", "and", "or", column=21, end_column=24)
    result = generate(tmp_path, "validator.py", mutant)

    assert result.distinguishing >= 1
    assert any("is False" in candidate for candidate in result.candidates)
    assert any(
        "AAAAAAAA" in candidate or "!!!!!!!!" in candidate for candidate in result.candidates
    )


def test_generate_reports_equivalent_clamp_comparison(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text(
        "def clamp(value: int, low: int, high: int) -> int:\n"
        "    if value <= low:\n"
        "        return low\n"
        "    if value >= high:\n"
        "        return high\n"
        "    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "test_calculator.py").write_text(
        "from calculator import clamp\n\ndef test_clamp():\n    assert clamp(5, 0, 10) == 5\n",
        encoding="utf-8",
    )

    mutant = _mutant("calculator.py", 2, "comparison", "<=", "<", column=13, end_column=15)
    result = generate(tmp_path, "calculator.py", mutant)

    assert result.candidates == ()
    assert result.equivalent_hint is True


def test_generate_returns_note_when_module_cannot_import(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text(
        "def value() -> int:\n    return 0\n\nraise RuntimeError('import exploded')\n",
        encoding="utf-8",
    )
    (tmp_path / "test_broken.py").write_text(
        "def test_value():\n    assert True\n",
        encoding="utf-8",
    )

    mutant = _mutant("broken.py", 2, "return", "0", "None", column=11, end_column=12)
    result = generate(tmp_path, "broken.py", mutant)

    assert result.candidates == ()
    assert "probe failed" in result.note
