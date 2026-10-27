"""The same grading inputs should select the same mutants and score."""

from __future__ import annotations

import sys
from pathlib import Path

from testproof.engine import MutationEngine
from testproof.models import Report

FIXTURE = Path(__file__).parents[1] / "fixtures" / "shop"


def _grade_fixture() -> Report:
    engine = MutationEngine(
        repo=FIXTURE,
        test_command=f"{sys.executable} -m pytest -q",
    )
    return engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("shipping.py", None), ("test_shipping.py", None)],
        all_files=True,
    )


def _stable_signature(report: Report) -> tuple[float | None, list[tuple[str, str]]]:
    signature = [
        (mutant.point.id, mutant.status)
        for file_report in report.files
        for mutant in file_report.mutants
    ]
    return report.summary.score, signature


def test_repeated_fixture_runs_have_same_score_and_mutant_ids() -> None:
    first = _grade_fixture()
    second = _grade_fixture()

    first_ids = [mutant.point.id for file_report in first.files for mutant in file_report.mutants]
    second_ids = [mutant.point.id for file_report in second.files for mutant in file_report.mutants]

    assert _stable_signature(first) == _stable_signature(second)
    assert first_ids == second_ids
