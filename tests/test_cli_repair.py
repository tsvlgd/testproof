"""Tests for the repair command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from testproof.cli import app

runner = CliRunner()

SHIPPING = (
    "def shipping_fee(order_total: int) -> int:\n"
    "    if order_total >= 50:\n"
    "        return 0\n"
    "    return 5\n"
)

SHIPPING_TEST = (
    "from shipping import shipping_fee\n\n"
    "def test_free_shipping():\n"
    "    assert shipping_fee(100) == 0\n\n"
    "def test_paid_shipping():\n"
    "    assert shipping_fee(10) == 5\n"
)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "shipping.py").write_text(SHIPPING, encoding="utf-8")
    (repo / "test_shipping.py").write_text(SHIPPING_TEST, encoding="utf-8")
    return repo


def _write_report(path: Path) -> None:
    report = {
        "schema_version": "1.0",
        "tool": {"name": "testproof", "version": "0.1.0"},
        "run": {
            "id": "run-1",
            "started_at": "2026-10-27T00:00:00Z",
            "duration_ms": 100,
            "base_ref": None,
            "head_ref": None,
            "target": "WORKTREE",
            "merge_base": None,
            "test_command": "python -m pytest -q",
            "language": "python",
            "threshold": None,
            "time_budget_ms": 300000,
            "max_mutants": 50,
            "all_files": True,
        },
        "summary": {
            "score": 83.3,
            "killed": 5,
            "survived": 1,
            "invalid": 0,
            "timeout": 0,
            "skipped": 0,
            "total": 6,
            "partial": False,
            "confidence": "high",
            "reason": "",
        },
        "files": [
            {
                "path": "shipping.py",
                "score": 83.3,
                "mutants": [
                    {
                        "point": {
                            "id": "abc123",
                            "path": "shipping.py",
                            "line": 2,
                            "column": 19,
                            "end_line": 2,
                            "end_column": 21,
                            "operator": "comparison",
                            "original": ">=",
                            "replacement": ">",
                        },
                        "status": "survived",
                        "duration_ms": 10,
                        "output": "2 passed",
                        "suspected_equivalent": False,
                    }
                ],
            }
        ],
        "errors": [],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def _prepare(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    repo = _make_repo(tmp_path)
    report = tmp_path / "report.json"
    _write_report(report)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    return repo, report


def test_repair_dry_run_uses_templates(tmp_path: Path, monkeypatch) -> None:
    repo, report = _prepare(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "repair",
            "--repo",
            str(repo),
            "--report",
            str(report),
            "--test-cmd",
            "python -m pytest -q",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Model: unavailable" in result.stdout
    assert "Kept: 1" in result.stdout
    assert "Deterministic template hits: 1" in result.stdout
    assert "Model attempts: 0" in result.stdout
    assert "assert shipping_fee(50) == 0" in result.stdout


def test_repair_json_output_is_machine_readable(tmp_path: Path, monkeypatch) -> None:
    repo, report = _prepare(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "repair",
            "--repo",
            str(repo),
            "--report",
            str(report),
            "--test-cmd",
            "python -m pytest -q",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["model"] == "unavailable"
    assert len(data["kept"]) == 1
    assert set(data["kept"][0]) == {"mutant_id", "test_code"}
    assert "assert shipping_fee(50) == 0" in data["kept"][0]["test_code"]
    assert data["rejected"] == []
    assert "Deterministic template hits" not in result.stdout
    assert data["template_hits"] == 1
    assert data["model_attempts"] == 0
    assert data["applied"] is False


def test_repair_apply_writes_verified_test(tmp_path: Path, monkeypatch) -> None:
    repo, report = _prepare(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "repair",
            "--repo",
            str(repo),
            "--report",
            str(report),
            "--test-cmd",
            "python -m pytest -q",
            "--apply",
        ],
    )

    assert result.exit_code == 0
    assert "Kept: 1" in result.stdout
    written = (repo / "test_shipping.py").read_text(encoding="utf-8")
    assert "assert shipping_fee(50) == 0" in written
    assert "test_repair_abc123_1" in written


def test_repair_without_templates_reports_missing_model(tmp_path: Path, monkeypatch) -> None:
    repo, report = _prepare(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "repair",
            "--repo",
            str(repo),
            "--report",
            str(report),
            "--test-cmd",
            "python -m pytest -q",
            "--dry-run",
            "--no-templates",
        ],
    )

    assert result.exit_code == 0
    assert "Rejected: 1" in result.stdout
    assert "model is not configured" in result.stdout
    assert "Model attempts: 1" in result.stdout
    assert "Deterministic template hits: 0" in result.stdout


def test_repair_with_model_reports_likely_equivalent(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        "def clamp(value: int, low: int, high: int) -> int:\n"
        "    if value <= low:\n"
        "        return low\n"
        "    if value >= high:\n"
        "        return high\n"
        "    return value\n",
        encoding="utf-8",
    )
    (repo / "test_calculator.py").write_text(
        "from calculator import clamp\n\ndef test_clamp():\n    assert clamp(5, 0, 10) == 5\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    _write_report(report)
    data = json.loads(report.read_text(encoding="utf-8"))
    mutant = data["files"][0]["mutants"][0]
    mutant["point"] = {
        "id": "abc123",
        "path": "calculator.py",
        "line": 2,
        "column": 13,
        "end_line": 2,
        "end_column": 15,
        "operator": "comparison",
        "original": "<=",
        "replacement": "<",
    }
    data["files"][0]["path"] = "calculator.py"
    report.write_text(json.dumps(data), encoding="utf-8")

    class FakeClient:
        model_name = "fake/model"

        def close(self) -> None:
            self.closed = True

    class FakeModelClient:
        @classmethod
        def from_env(cls, model_override=None):
            return FakeClient()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("testproof.cli.ModelClient", FakeModelClient)

    result = runner.invoke(
        app,
        [
            "repair",
            "--repo",
            str(repo),
            "--report",
            str(report),
            "--test-cmd",
            "python -m pytest -q",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Model: fake/model" in result.stdout
    assert "Likely equivalent: 1" in result.stdout
    assert "Likely equivalent abc123" in result.stdout
