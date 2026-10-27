"""End to end tests for deterministic mutation grading."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from testproof.engine import MutationEngine
from testproof.models import Report

FIXTURE = Path(__file__).parents[1] / "fixtures" / "shop"
TEST_COMMAND = f"{sys.executable} -m pytest -q"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _grade_fixture() -> Report:
    engine = MutationEngine(repo=FIXTURE, test_command=TEST_COMMAND)
    return engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("shipping.py", None)],
    )


def test_engine_scores_shipping_file_and_reports_boundary_survivor() -> None:
    before = _tree_hash(FIXTURE)
    report = _grade_fixture()

    assert _tree_hash(FIXTURE) == before
    assert report.summary.killed == 5
    assert report.summary.survived == 1
    assert report.summary.invalid == 0
    assert report.summary.timeout == 0
    assert report.summary.score == pytest.approx(500 / 6)

    survivors = [
        mutant
        for file_report in report.files
        for mutant in file_report.mutants
        if mutant.status == "survived"
    ]
    assert len(survivors) == 1
    assert survivors[0].point.path == "shipping.py"
    assert survivors[0].point.line == 6
    assert survivors[0].point.original == ">="
    assert survivors[0].point.replacement == ">"


def test_engine_scores_each_file_independently(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def value() -> int:\n    return 2\n", encoding="utf-8")
    tests = tmp_path / "test_a.py"
    tests.write_text(
        "from a import value\n\ndef test_value():\n    assert value() == 1\n", encoding="utf-8"
    )
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -m pytest -q")

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("a.py", None), ("b.py", None)],
    )

    scores = {file_report.path: file_report.score for file_report in report.files}
    assert scores["a.py"] == 100.0
    assert scores["b.py"] == 0.0
    # The aggregate score weights each mutant equally, rather than averaging file scores.
    assert report.summary.score == pytest.approx(200 / 3)


def test_engine_reports_skipped_mutants_when_budget_expires() -> None:
    engine = MutationEngine(repo=FIXTURE, test_command=TEST_COMMAND)
    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("shipping.py", None)],
        time_budget_seconds=0,
    )

    assert report.summary.partial is True
    assert report.summary.skipped > 0
    assert report.summary.reason
    assert report.summary.confidence == "low"
    assert all(
        mutant.status == "skipped" for file_report in report.files for mutant in file_report.mutants
    )


def test_engine_classifies_timed_out_mutant(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    test_script = tmp_path / "check.py"
    test_script.write_text(
        "from pathlib import Path\n"
        "import time\n"
        "if 'return None' in Path('module.py').read_text():\n"
        "    time.sleep(5)\n",
        encoding="utf-8",
    )
    engine = MutationEngine(
        repo=tmp_path,
        test_command=f"{sys.executable} check.py",
        test_timeout_seconds=1,
    )

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None)],
    )

    assert report.summary.timeout == 1
    assert report.summary.confidence == "medium"
    assert any(mutant.status == "timeout" for mutant in report.files[0].mutants)


def test_engine_marks_apply_failures_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "module.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")

    def fail_apply(_source, _point):
        raise ValueError("cannot apply mutation")

    monkeypatch.setattr(engine._adapter, "apply", fail_apply)
    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None)],
    )

    assert report.summary.invalid > 0
    assert report.summary.confidence == "medium"
    assert all(mutant.status == "invalid" for mutant in report.files[0].mutants)


def test_engine_reports_missing_file_as_error(tmp_path: Path) -> None:
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("missing.py", None)],
    )

    assert report.summary.score is None
    assert report.summary.partial is True
    assert report.summary.confidence == "low"
    assert len(report.errors) == 1
    assert report.errors[0].startswith("missing.py:")


def test_engine_rejects_a_failing_baseline(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c exit(1)")

    with pytest.raises(RuntimeError, match="Baseline test command failed"):
        engine.grade(
            target="WORKTREE",
            base_ref=None,
            head_ref=None,
            merge_base=None,
            changed_files=[("module.py", None)],
        )


def test_engine_rejects_path_outside_repository(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("../outside.py", None)],
    )

    assert report.summary.total == 0
    assert report.errors
    assert "Path escapes the sandbox" in report.errors[0]


def test_engine_rejects_nonpositive_test_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="test_timeout_seconds must be greater than zero"):
        MutationEngine(
            repo=tmp_path,
            test_command="true",
            test_timeout_seconds=0,
        )


def test_engine_rejects_negative_time_budget(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="time_budget_seconds cannot be negative"):
        MutationEngine(
            repo=tmp_path,
            test_command="true",
            time_budget_seconds=-1,
        )


def test_engine_rejects_negative_mutant_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_mutants cannot be negative"):
        MutationEngine(
            repo=tmp_path,
            test_command="true",
            max_mutants=-1,
        )


def test_engine_rejects_negative_run_budget(tmp_path: Path) -> None:
    engine = MutationEngine(repo=tmp_path, test_command="true")

    with pytest.raises(ValueError, match="time_budget_seconds cannot be negative"):
        engine.grade(
            target="WORKTREE",
            base_ref=None,
            head_ref=None,
            merge_base=None,
            changed_files=[],
            time_budget_seconds=-1,
        )


def test_engine_marks_mutant_cap_as_partial(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    engine = MutationEngine(
        repo=tmp_path,
        test_command=f"{sys.executable} -c pass",
        max_mutants=1,
    )

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None)],
    )

    assert report.summary.partial is True
    assert report.summary.skipped > 0
    assert "Mutant cap" in report.summary.reason


def test_engine_rejects_invalid_mutant_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "module.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")
    monkeypatch.setattr(engine._adapter, "validate", lambda _source: False)

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None)],
    )

    assert report.summary.invalid > 0
    assert report.summary.confidence == "medium"


def test_engine_handles_duplicate_changed_paths_once(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None), ("module.py", None)],
    )

    assert len(report.files) == 1


def test_engine_records_all_files_mode(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text("def value() -> int:\n    return 1\n", encoding="utf-8")
    engine = MutationEngine(repo=tmp_path, test_command=f"{sys.executable} -c pass")

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("module.py", None)],
        all_files=True,
    )

    assert report.run.all_files is True
