"""Tests for report rendering."""

from __future__ import annotations

import json

from testproof.models import (
    FileReport,
    Mutant,
    MutationPoint,
    Report,
    RunInfo,
    Summary,
    ToolInfo,
)
from testproof.report import to_json, to_markdown


def _make_report(score: float | None = 83.3, threshold: float | None = 80.0) -> Report:
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
    mutant = Mutant(point=point, status="survived", duration_ms=100, output="2 passed")
    file_report = FileReport(path="shipping.py", score=score, mutants=(mutant,))
    run = RunInfo(
        id="run1",
        started_at="2026-01-01T00:00:00Z",
        duration_ms=1000,
        base_ref="HEAD",
        head_ref="HEAD",
        target="WORKTREE",
        merge_base=None,
        test_command="pytest -q",
        language="python",
        threshold=threshold,
        time_budget_ms=300000,
        max_mutants=50,
        all_files=True,
    )
    summary = Summary(
        score=score,
        killed=5,
        survived=1,
        invalid=0,
        timeout=0,
        skipped=0,
        total=6,
        partial=False,
        confidence="high",
    )
    return Report(
        schema_version="1.0",
        tool=ToolInfo(name="testproof", version="0.1.0"),
        run=run,
        summary=summary,
        files=(file_report,),
        errors=(),
    )


def test_to_json_round_trips() -> None:
    report = _make_report()
    text = to_json(report)
    data = json.loads(text)
    assert data["summary"]["score"] == 83.3
    assert data["files"][0]["path"] == "shipping.py"


def test_to_markdown_contains_score() -> None:
    report = _make_report()
    md = to_markdown(report)
    assert "83.3%" in md
    assert "shipping.py" in md
    assert ">=" in md
    assert ">" in md


def test_to_markdown_contains_caveat() -> None:
    report = _make_report()
    md = to_markdown(report)
    assert "does not prove correctness" in md


def test_to_markdown_contains_survivor() -> None:
    report = _make_report()
    md = to_markdown(report)
    assert "Survivors" in md
    assert "shipping.py:6" in md


def test_to_markdown_pass_status() -> None:
    report = _make_report(score=83.3, threshold=50.0)
    md = to_markdown(report)
    assert "pass" in md


def test_to_markdown_fail_status() -> None:
    report = _make_report(score=83.3, threshold=90.0)
    md = to_markdown(report)
    assert "fail" in md


def test_to_markdown_partial_run() -> None:
    report = _make_report()
    from testproof.models import Summary

    partial_summary = Summary(
        score=83.3,
        killed=5,
        survived=1,
        invalid=0,
        timeout=0,
        skipped=2,
        total=8,
        partial=True,
        confidence="medium",
        reason="Time budget reached",
    )
    from dataclasses import replace

    report = replace(report, summary=partial_summary)
    md = to_markdown(report)
    assert "Partial run" in md
    assert "Time budget reached" in md


def test_to_markdown_with_errors() -> None:
    from dataclasses import replace

    report = _make_report()
    report = replace(report, errors=("file.py: error",))
    md = to_markdown(report)
    assert "Errors" in md
    assert "file.py: error" in md


def test_to_markdown_no_survivors() -> None:
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
    mutant = Mutant(point=point, status="killed", duration_ms=100, output="1 passed")
    file_report = FileReport(path="shipping.py", score=100.0, mutants=(mutant,))
    from dataclasses import replace

    report = _make_report()
    report = replace(report, files=(file_report,))
    md = to_markdown(report)
    assert "Survivors" not in md


def test_to_markdown_none_score() -> None:
    report = _make_report(score=None)
    md = to_markdown(report)
    assert "N/A" in md
