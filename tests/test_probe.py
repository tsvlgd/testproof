"""Tests for the isolated function probe."""

from __future__ import annotations

from pathlib import Path

from testproof.probe import module_for, probe_cases


def test_module_for_flat_layout(tmp_path: Path) -> None:
    result = module_for(tmp_path, "shipping.py")
    assert result is not None
    module, root = result
    assert module == "shipping"
    assert root == tmp_path


def test_module_for_src_layout(tmp_path: Path) -> None:
    (tmp_path / "src" / "shop").mkdir(parents=True)
    (tmp_path / "src" / "shop" / "shipping.py").write_text("", encoding="utf-8")
    result = module_for(tmp_path, "src/shop/shipping.py")
    assert result is not None
    module, root = result
    assert module == "shop.shipping"
    assert root == tmp_path / "src"


def test_probe_cases_returns_values(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    outcomes, error = probe_cases(tmp_path, "calc", "add", [(2, 3), (5, 1)])

    assert error is None
    assert outcomes is not None
    assert [outcome.value_repr for outcome in outcomes] == ["5", "6"]


def test_probe_cases_reports_import_error(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    outcomes, error = probe_cases(tmp_path, "calc", "add", [(2, 3)])

    assert outcomes is None
    assert error is not None
    assert "RuntimeError" in error


def test_probe_cases_handles_function_errors(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text(
        "def divide(a: int, b: int) -> float:\n"
        "    if b == 0:\n"
        "        raise ValueError('no')\n"
        "    return a / b\n",
        encoding="utf-8",
    )

    outcomes, error = probe_cases(tmp_path, "calc", "divide", [(4, 2), (4, 0)])

    assert error is None
    assert outcomes is not None
    assert outcomes[0].ok is True
    assert outcomes[0].value_repr == "2.0"
    assert outcomes[1].ok is False
    assert outcomes[1].error is not None
    assert "ValueError" in outcomes[1].error


def test_module_for_rejects_absolute_path_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"
    assert module_for(tmp_path, str(outside)) is None


def test_module_for_rejects_non_python_and_invalid_names(tmp_path: Path) -> None:
    assert module_for(tmp_path, "notes.txt") is None
    assert module_for(tmp_path, "bad-name.py") is None


def test_module_for_handles_package_init(tmp_path: Path) -> None:
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop" / "__init__.py").write_text("", encoding="utf-8")

    result = module_for(tmp_path, "shop/__init__.py")

    assert result is not None
    assert result[0] == "shop"


def test_probe_cases_returns_empty_for_no_cases(tmp_path: Path) -> None:
    assert probe_cases(tmp_path, "calc", "add", []) == ([], None)


def test_probe_cases_skips_unrepresentable_values(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    outcomes, error = probe_cases(tmp_path, "calc", "add", [(object(), 1)])

    assert outcomes == []
    assert error is None


def test_probe_cases_reports_timeout(tmp_path: Path) -> None:
    (tmp_path / "slow.py").write_text(
        "import time\n\ndef wait() -> int:\n    time.sleep(5)\n    return 1\n",
        encoding="utf-8",
    )

    outcomes, error = probe_cases(tmp_path, "slow", "wait", [()], timeout_seconds=1)

    assert outcomes is None
    assert error is not None
    assert "probe failed" in error


def test_probe_cases_reports_missing_json_when_target_exits(tmp_path: Path) -> None:
    (tmp_path / "exit.py").write_text(
        "def stop() -> int:\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )

    outcomes, error = probe_cases(tmp_path, "exit", "stop", [()])

    assert outcomes is None
    assert error is not None
    assert "probe returned no JSON" in error
