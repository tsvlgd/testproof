"""Integration test for repair with a mocked model."""

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


def test_repair_keeps_valid_test(tmp_path: Path) -> None:
    # Set up a small repo
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

    # Mock model that returns a valid boundary test
    model = MagicMock(spec=ModelClient)
    model.complete.return_value = (
        "from shipping import shipping_fee\n\n"
        "def test_boundary():\n"
        "    assert shipping_fee(50) == 0\n"
    )

    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)

    point = MutationPoint(
        id="abc123",
        path="shipping.py",
        line=2,
        column=19,
        end_line=2,
        end_column=21,
        operator="comparison",
        original=">=",
        replacement=">",
    )
    mutant = Mutant(point=point, status="survived", duration_ms=100, output="2 passed")
    report = Report(
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
            test_command="python -m pytest -q",
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
        files=(FileReport(path="shipping.py", score=83.3, mutants=(mutant,)),),
        errors=(),
    )

    result = engine.repair(report, dry_run=True)
    assert len(result.kept) == 1
    assert len(result.rejected) == 0
    assert result.kept[0][0] == "abc123"
    assert "assert shipping_fee(50) == 0" in result.kept[0][1]


def test_repair_rejects_test_that_does_not_kill(tmp_path: Path) -> None:
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
    # Model proposes a test that passes on both original and mutant (doesn't kill)
    model.complete.return_value = "def test_always_passes():\n    assert True\n"

    engine = RepairEngine(repo=tmp_path, test_command="python -m pytest -q", model_client=model)

    point = MutationPoint(
        id="abc123",
        path="shipping.py",
        line=2,
        column=19,
        end_line=2,
        end_column=21,
        operator="comparison",
        original=">=",
        replacement=">",
    )
    mutant = Mutant(point=point, status="survived", duration_ms=100, output="2 passed")
    report = Report(
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
            test_command="python -m pytest -q",
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
        files=(FileReport(path="shipping.py", score=83.3, mutants=(mutant,)),),
        errors=(),
    )

    result = engine.repair(report, dry_run=True)
    assert len(result.kept) == 0
    assert len(result.rejected) == 1
    # The test passes on original but also passes on mutant (doesn't kill)
    assert (
        "does not kill" in result.rejected[0].reason
        or "breaks" in result.rejected[0].reason
        or "fails on original" in result.rejected[0].reason
    )
