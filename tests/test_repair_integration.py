"""Integration tests for repair with a mocked model."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from testproof.model import ModelClient
from testproof.models import (
    FileReport,
    Mutant,
    MutationPoint,
    Report,
    RunInfo,
    Summary,
    ToolInfo,
)
from testproof.repair import RepairEngine


def _report(path: str, mutant: Mutant, test_command: str) -> Report:
    return Report(
        schema_version="1.0",
        tool=ToolInfo(name="testproof", version="0.1.0"),
        run=RunInfo(
            id="r1",
            started_at="2026-01-01T00:00:00Z",
            duration_ms=100,
            base_ref=None,
            head_ref=None,
            target="WORKTREE",
            merge_base=None,
            test_command=test_command,
            language="python",
            threshold=None,
            time_budget_ms=300000,
            max_mutants=50,
            all_files=True,
        ),
        summary=Summary(
            score=83.3,
            killed=5,
            survived=1,
            invalid=0,
            timeout=0,
            skipped=0,
            total=6,
            partial=False,
            confidence="high",
        ),
        files=(FileReport(path=path, score=83.3, mutants=(mutant,)),),
        errors=(),
    )


def _mutant(
    path: str,
    line: int,
    operator: str,
    original: str,
    replacement: str,
    *,
    column: int,
    end_column: int,
) -> Mutant:
    point = MutationPoint(
        id="abc123",
        path=path,
        line=line,
        column=column,
        end_line=line,
        end_column=end_column,
        operator=operator,
        original=original,
        replacement=replacement,
    )
    return Mutant(point=point, status="survived", duration_ms=100, output="2 passed")


def test_repair_uses_template_before_model(tmp_path: Path) -> None:
    (tmp_path / "shipping.py").write_text(
        "def shipping_fee(order_total: int) -> int:\n"
        "    if order_total >= 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    (tmp_path / "test_shipping.py").write_text(
        "from shipping import shipping_fee\n\n"
        "def test_free_shipping():\n"
        "    assert shipping_fee(100) == 0\n\n"
        "def test_paid_shipping():\n"
        "    assert shipping_fee(10) == 5\n",
        encoding="utf-8",
    )

    model = MagicMock(spec=ModelClient)
    model.complete.return_value = (
        "from shipping import shipping_fee\n\n"
        "def test_boundary():\n"
        "    assert shipping_fee(50) == 0\n"
    )
    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)
    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)

    result = engine.repair(_report("shipping.py", mutant, "python -m pytest -q"), dry_run=True)

    assert len(result.kept) == 1
    assert len(result.rejected) == 0
    assert result.kept[0][0] == "abc123"
    assert "assert shipping_fee(50) == 0" in result.kept[0][1]
    assert result.template_hits == 1
    assert result.model_attempts == 0
    model.complete.assert_not_called()


def test_repair_rejects_test_that_does_not_kill(tmp_path: Path) -> None:
    (tmp_path / "pick.py").write_text(
        "def pick(value: int) -> int:\n    if value > 0:\n        return value\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "test_pick.py").write_text(
        "from pick import pick\n\ndef test_pick():\n    assert pick(1) == 1\n",
        encoding="utf-8",
    )

    model = MagicMock(spec=ModelClient)
    model.complete.return_value = "def test_always_passes():\n    assert True\n"
    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)
    mutant = _mutant("pick.py", 2, "comparison", ">", ">=", column=13, end_column=14)

    result = engine.repair(_report("pick.py", mutant, "python -m pytest -q"), dry_run=True)

    assert len(result.kept) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "candidate does not kill the mutant"
    assert result.model_attempts == 1
    model.complete.assert_called_once()


def test_repair_skips_model_for_likely_equivalent(tmp_path: Path) -> None:
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

    model = MagicMock(spec=ModelClient)
    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)
    mutant = _mutant("calculator.py", 2, "comparison", "<=", "<", column=13, end_column=15)

    result = engine.repair(_report("calculator.py", mutant, "python -m pytest -q"), dry_run=True)

    assert result.kept == []
    assert result.rejected == []
    assert result.equivalent == ["abc123"]
    model.complete.assert_not_called()


def test_repair_reports_model_call_error(tmp_path: Path) -> None:
    (tmp_path / "pick.py").write_text(
        "def pick(value: int) -> int:\n    if value > 0:\n        return value\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "test_pick.py").write_text(
        "from pick import pick\n\ndef test_pick():\n    assert pick(1) == 1\n",
        encoding="utf-8",
    )

    model = MagicMock(spec=ModelClient)
    model.complete.side_effect = RuntimeError("upstream down")
    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)
    mutant = _mutant("pick.py", 2, "comparison", ">", ">=", column=13, end_column=14)

    result = engine.repair(_report("pick.py", mutant, "python -m pytest -q"), dry_run=True)

    assert len(result.rejected) == 1
    assert "model call failed: RuntimeError: upstream down" in result.rejected[0].reason


def test_verify_preserves_imports_from_existing_test(tmp_path: Path) -> None:
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
        "    assert shipping_fee(100) == 0\n",
        encoding="utf-8",
    )
    engine = RepairEngine(
        repo=tmp_path,
        test_command="python -m pytest -q",
        model_client=MagicMock(spec=ModelClient),
    )
    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)

    record = engine._verify(
        "shipping.py",
        mutant,
        "def test_boundary():\n    assert shipping_fee(50) == 0\n",
        "t-import",
    )

    assert record.decision == "kept"
    assert record.passes_on_original is True
    assert record.fails_on_mutant is True
    assert record.full_suite_passes is True


def test_verify_rejects_candidate_without_assertion(tmp_path: Path) -> None:
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
        "    assert shipping_fee(100) == 0\n",
        encoding="utf-8",
    )
    engine = RepairEngine(
        repo=tmp_path,
        test_command="python -m pytest -q",
        model_client=MagicMock(spec=ModelClient),
    )
    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)

    record = engine._verify("shipping.py", mutant, "def test_empty():\n    pass\n", "t-empty")

    assert record.decision == "rejected"
    assert record.reason == "candidate has no assertion"


def test_repair_apply_creates_test_file_when_missing(tmp_path: Path) -> None:
    (tmp_path / "shipping.py").write_text(
        "def shipping_fee(order_total: int) -> int:\n"
        "    if order_total >= 50:\n"
        "        return 0\n"
        "    return 5\n",
        encoding="utf-8",
    )
    (tmp_path / "test_other.py").write_text(
        "def test_placeholder():\n    assert True\n",
        encoding="utf-8",
    )
    engine = RepairEngine(
        repo=tmp_path,
        test_command="python -m pytest -q",
        model_client=MagicMock(spec=ModelClient),
    )
    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)

    result = engine.repair(
        _report("shipping.py", mutant, "python -m pytest -q"),
        dry_run=False,
        apply=True,
    )

    assert len(result.kept) == 1
    created = tmp_path / "test_shipping.py"
    assert created.exists()
    assert "assert shipping_fee(50) == 0" in created.read_text(encoding="utf-8")


def test_repair_apply_does_not_duplicate_existing_imports(tmp_path: Path) -> None:
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
        "    assert shipping_fee(100) == 0\n",
        encoding="utf-8",
    )
    engine = RepairEngine(
        repo=tmp_path,
        test_command="python -m pytest -q",
        model_client=MagicMock(spec=ModelClient),
    )
    mutant = _mutant("shipping.py", 2, "comparison", ">=", ">", column=19, end_column=21)

    result = engine.repair(
        _report("shipping.py", mutant, "python -m pytest -q"),
        dry_run=False,
        apply=True,
    )

    assert len(result.kept) == 1
    written = (tmp_path / "test_shipping.py").read_text(encoding="utf-8")
    assert written.count("from shipping import shipping_fee") == 1
    assert written.count("def test_repair_") == 1
