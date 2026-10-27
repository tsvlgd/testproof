"""Tests for verified repair."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from testproof.model import ModelClient, ModelConfig
from testproof.models import Mutant, MutationPoint
from testproof.repair import RepairEngine, _extract_test


def _make_mutant() -> Mutant:
    point = MutationPoint(
        id="abc123",
        path="shipping.py",
        line=6,
        column=19,
        end_line=6,
        end_column=21,
        operator="comparison",
        original=">=",
        replacement=">",
    )
    return Mutant(point=point, status="survived", duration_ms=100, output="2 passed")


def test_extract_test_from_plain_response() -> None:
    response = "def test_boundary():\n    assert shipping_fee(50) == 0\n"
    result = _extract_test(response)
    assert result is not None
    assert "def test_boundary" in result
    assert "assert shipping_fee(50) == 0" in result


def test_extract_test_from_markdown_block() -> None:
    response = "```python\ndef test_boundary():\n    assert shipping_fee(50) == 0\n```"
    result = _extract_test(response)
    assert result is not None
    assert "def test_boundary" in result


def test_extract_test_returns_none_for_empty() -> None:
    assert _extract_test("") is None
    assert _extract_test("   ") is None


def test_repair_rejects_invalid_model_response(tmp_path: Path) -> None:
    (tmp_path / "shipping.py").write_text("def f(): pass\n", encoding="utf-8")
    (tmp_path / "test_shipping.py").write_text("def test_f(): pass\n", encoding="utf-8")

    model = MagicMock(spec=ModelClient)
    model.complete.return_value = "This is not a test function"

    engine = RepairEngine(repo=tmp_path, test_command="python -c pass", model_client=model)
    from testproof.models import FileReport, Report, RunInfo, Summary, ToolInfo

    mutant = _make_mutant()
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
            test_command="python -c pass",
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
    assert result.rejected[0].reason == "model returned no valid test"


def test_model_config_defaults() -> None:
    config = ModelConfig(api_key="test-key")
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.model == "meta-llama/llama-3.1-8b-instruct"
    assert config.max_tokens == 500
    assert config.temperature == 0.0
