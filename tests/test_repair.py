"""Tests for verified repair."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from testproof.model import ModelClient, ModelConfig
from testproof.models import Mutant, MutationPoint
from testproof.repair import RepairEngine, _build_prompt, _extract_test, _split_test_code


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


def test_extract_test_ignores_reasoning_before_code() -> None:
    response = (
        "Distinguishing input: 50.\n\n"
        "```python\nfrom shipping import shipping_fee\n\n"
        "def test_boundary():\n    assert shipping_fee(50) == 0\n```\n"
    )
    result = _extract_test(response)
    assert result is not None
    assert result.startswith("from shipping import shipping_fee")
    assert "def test_boundary" in result


def test_extract_test_keeps_return_annotation() -> None:
    response = (
        "```python\nfrom shipping import shipping_fee\n\n"
        "def test_boundary() -> None:\n"
        "    assert shipping_fee(50) == 0\n```\n"
    )
    result = _extract_test(response)
    assert result is not None
    assert result.startswith("from shipping import shipping_fee")
    assert "def test_boundary() -> None:" in result
    assert "assert shipping_fee(50) == 0" in result


def test_extract_test_keeps_only_one_new_test_from_an_echoed_suite() -> None:
    response = (
        "```python\nfrom shipping import shipping_fee\n\n"
        "def test_existing():\n"
        "    assert shipping_fee(100) == 0\n\n"
        "def test_boundary():\n"
        "    assert shipping_fee(50) == 0\n\n"
        "def test_other():\n"
        "    assert shipping_fee(10) == 5\n```\n"
    )
    existing = (
        "from shipping import shipping_fee\n\n"
        "def test_existing():\n"
        "    assert shipping_fee(100) == 0\n"
    )

    result = _extract_test(response, existing)

    assert result is not None
    assert "def test_boundary" in result
    assert "def test_existing" not in result
    assert "def test_other" not in result


def test_extract_test_returns_none_when_all_tests_already_exist() -> None:
    response = (
        "from shipping import shipping_fee\n\n"
        "def test_existing():\n"
        "    assert shipping_fee(100) == 0\n"
    )
    existing = (
        "from shipping import shipping_fee\n\n"
        "def test_existing():\n"
        "    assert shipping_fee(100) == 0\n"
    )

    assert _extract_test(response, existing) is None


def test_extract_test_handles_decorated_test() -> None:
    response = (
        "import pytest\n"
        "from shipping import shipping_fee\n\n"
        "@pytest.mark.parametrize('total', [50, 51])\n"
        "def test_boundary(total):\n"
        "    assert shipping_fee(total) == 0\n"
    )

    result = _extract_test(response)

    assert result is not None
    assert "@pytest.mark.parametrize" in result
    assert "def test_boundary" in result


def test_split_test_code_separates_imports_and_decorated_body() -> None:
    imports, body = _split_test_code(
        "import pytest\n"
        "from shipping import shipping_fee\n\n"
        "@pytest.mark.parametrize('total', [50])\n"
        "def test_boundary(total):\n"
        "    assert shipping_fee(total) == 0\n"
    )

    assert imports == ["import pytest", "from shipping import shipping_fee"]
    assert body.startswith("@pytest.mark.parametrize")
    assert "def test_boundary" in body


def test_extract_test_returns_none_for_empty() -> None:
    assert _extract_test("") is None
    assert _extract_test("   ") is None


def test_build_prompt_contains_reasoning_and_hint() -> None:
    prompt = _build_prompt(
        file_path="shipping.py",
        function_source="def shipping_fee(total: int) -> int:\n    return 0\n",
        mutated_line="    if total >= 50:",
        existing_tests="def test_free():\n    assert shipping_fee(100) == 0\n",
        mutant=_make_mutant(),
        feedback="no distinguishing input found",
    )

    assert "Worked example" in prompt
    assert "Step 1" in prompt
    assert "Step 2" in prompt
    assert "boundary" in prompt
    assert "no distinguishing input found" in prompt
    assert "fenced Python code block" in prompt


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
    assert result.rejected[0].reason.startswith("model returned no valid test")


def test_model_config_defaults() -> None:
    config = ModelConfig(api_key="test-key")
    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.model == "qwen/qwen3-235b-a22b-2507"
    assert config.max_tokens == 1200
    assert config.temperature == 0.0
