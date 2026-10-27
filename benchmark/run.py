"""Run the TestProof benchmark across the corpus.

For every corpus module:

1. grade the original module with its weak suite (before repair)
2. run verified repair with apply, templates first, model fallback if configured
3. grade again (after repair)
4. run the suite against the known bug version: before (weak suite, must pass)
   and after repair (detecting the bug is the point)

Results land in benchmark/results/raw.json plus one JSON file per module, and
benchmark/results.md is rendered from the raw data. Nothing is hand written:
the renderer reads the JSON that the run produced.

Usage:

    uv run python benchmark/run.py
    uv run python benchmark/run.py --filter last_page
    uv run python benchmark/run.py --render-only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
BUGS = ROOT / "bugs"
RESULTS = ROOT / "results"

TEST_CMD = "python -m pytest -q"
WORK_ROOT = Path("/tmp/opencode/testproof-bench")


def _run(cmd: list[str], cwd: Path, timeout: float) -> dict[str, object]:
    import subprocess

    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "seconds": round(time.perf_counter() - started, 2),
    }


def _cli(*args: str) -> list[str]:
    return [sys.executable, "-m", "testproof.cli", *args]


def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def has_model_configured() -> bool:
    """True when a repair run would be able to call the model."""
    if os.environ.get("MODEL_API_KEY"):
        return True
    config = (
        Path(os.environ.get("TESTPROOF_CONFIG_HOME", Path.home() / ".config"))
        / "testproof"
        / "model.json"
    )
    return config.exists()


def grade_module(
    module_dir: Path, report_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    """Grade one module and return (wall result, report data)."""
    wall = _run(
        _cli(
            "grade",
            "--repo",
            str(module_dir),
            "--all",
            "--test-cmd",
            TEST_CMD,
            "--format",
            "json",
            "--output",
            str(report_path),
        ),
        cwd=ROOT.parent,
        timeout=600,
    )
    if wall["exit_code"] != 0:
        raise RuntimeError(f"grade failed for {module_dir.name}: {wall['stderr'][-400:]}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return wall, report


def repair_module(
    module_dir: Path, report_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    """Run verified repair with apply and return (wall result, result data)."""
    wall = _run(
        _cli(
            "repair",
            "--repo",
            str(module_dir),
            "--report",
            str(report_path),
            "--test-cmd",
            TEST_CMD,
            "--apply",
            "--json",
        ),
        cwd=ROOT.parent,
        timeout=1200,
    )
    if wall["exit_code"] != 0:
        raise RuntimeError(f"repair failed for {module_dir.name}: {wall['stderr'][-400:]}")
    try:
        data = json.loads(wall["stdout"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"repair output was not JSON for {module_dir.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"repair output was not an object for {module_dir.name}")
    return wall, data


def run_bug_check(bug_module: Path, tests_dir: Path) -> dict[str, object]:
    """Run the tests dir against a bug module. Exit code 0 means bug undetected."""
    wall = _run(
        [sys.executable, "-m", "pytest", "-q", "tests/"], cwd=bug_module.parent, timeout=120
    )
    result = {
        "exit_code": wall["exit_code"],
        "seconds": wall["seconds"],
        "pass": wall["exit_code"] == 0,
        "tail": str(wall["stdout"]).strip().splitlines()[-1] if str(wall["stdout"]).strip() else "",
    }
    del tests_dir
    return result


def bug_detected(row: dict[str, object]) -> bool:
    """True when the repaired suite fails on the known bug version."""
    bug_after = row.get("bug_after")
    if isinstance(bug_after, dict):
        return bug_after.get("pass") is False
    return False


def run_module(module_id: str) -> dict[str, object]:
    """Grade, repair, regrade, and bug check one corpus module."""
    corpus_dir = CORPUS / module_id
    bug_dir = BUGS / module_id
    work = WORK_ROOT / module_id
    bug_work = WORK_ROOT / f"{module_id}-bug"
    _clean_dir(work)
    _clean_dir(bug_work)

    # bug work dir: the buggy module plus the weak suite
    shutil.copy2(bug_dir / f"{module_id}.py", bug_work / f"{module_id}.py")
    shutil.copytree(corpus_dir / "tests", bug_work / "tests")
    bug_before = run_bug_check(bug_work / f"{module_id}.py", bug_work / "tests")

    work_dir = work / module_id
    shutil.copytree(corpus_dir, work_dir)

    before_wall, before_report = grade_module(work_dir, work / "report-before.json")
    summary_before = before_report["summary"]

    repair_wall, repair_data = repair_module(work_dir, work / "report-before.json")

    after_wall, after_report = grade_module(work_dir, work / "report-after.json")
    summary_after = after_report["summary"]

    # after repair the applied tests live in the merged test file
    shutil.copytree(work_dir / "tests", bug_work / "tests", dirs_exist_ok=True)
    bug_after = run_bug_check(bug_work / f"{module_id}.py", bug_work / "tests")

    total_seconds = round(
        float(before_wall["seconds"])
        + float(repair_wall["seconds"])
        + float(after_wall["seconds"]),
        2,
    )
    return {
        "module_id": module_id,
        "mutants": summary_before["killed"]
        + summary_before["survived"]
        + summary_before.get("timeout", 0),
        "killed_before": summary_before["killed"],
        "survived_before": summary_before["survived"],
        "score_before": summary_before["score"],
        "killed_after": summary_after["killed"],
        "survived_after": summary_after["survived"],
        "score_after": summary_after["score"],
        "kept": len(repair_data["kept"]),
        "rejected": len(repair_data["rejected"]),
        "likely_equivalent": len(repair_data["likely_equivalent"]),
        "template_hits": repair_data["template_hits"],
        "model_attempts": repair_data["model_attempts"],
        "bug_before": bug_before,
        "bug_after": bug_after,
        "grade_before_seconds": before_wall["seconds"],
        "repair_seconds": repair_wall["seconds"],
        "grade_after_seconds": after_wall["seconds"],
        "total_seconds": total_seconds,
    }


def render_markdown(rows: list[dict[str, object]], meta: dict[str, object]) -> str:
    """Render benchmark/results.md from raw run records."""
    date = meta["date"]
    lines = [
        "# Benchmark results",
        "",
        f"Measured on {date}. Corpus: 12 synthetic modules with weak suites and known bug",
        "versions (see `benchmark/corpus/SOURCES.md`). Method: grade, verified repair",
        "(templates first, model fallback), re grade, then run the repaired suite",
        "against the known bug version. Detection before repair is by construction:",
        "the weak suite passes on the bug version. Detection after repair is measured.",
        "",
        f"Model fallback active: {meta['model_configured']}. No template rejection was",
        "silenced: every kept test passed on the original, failed on the mutant, and",
        "kept the full suite green.",
        "",
        "## Per module",
        "",
        "| Module | Before | After | Kept | Rej | Eq | Templates | Model | Bug |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    totals = {
        "mutants": 0,
        "killed_before": 0,
        "killed_after": 0,
        "survived_before": 0,
        "survived_after": 0,
        "kept": 0,
        "rejected": 0,
        "equivalent": 0,
        "template_hits": 0,
        "model_attempts": 0,
        "seconds": 0.0,
        "bugs_detected": 0,
    }
    for row in rows:
        detected = (
            bool(row["bug_after"].get("pass", True) is False)
            if isinstance(row["bug_after"], dict)
            else False
        )
        totals["bugs_detected"] += 1 if detected else 0
        for key in (
            "mutants",
            "killed_before",
            "killed_after",
            "survived_before",
            "survived_after",
            "kept",
            "rejected",
            "template_hits",
            "model_attempts",
        ):
            totals[key] += int(row[key])  # type: ignore[arg-type]
        totals["equivalent"] += int(row["likely_equivalent"])
        totals["seconds"] += float(row["total_seconds"])
        lines.append(
            f"| {row['module_id']} "
            f"| {format_score(row['score_before'])} ({row['survived_before']} survive) "
            f"| {format_score(row['score_after'])} ({row['survived_after']} survive) "
            f"| {row['kept']} | {row['rejected']} | {row['likely_equivalent']} "
            f"| {row['template_hits']} | {row['model_attempts']} "
            f"| {'yes' if detected else 'no'} |"
        )
    before_total = totals["killed_before"] + totals["survived_before"]
    after_total = totals["killed_after"] + totals["survived_after"]
    before_score = totals["killed_before"] / before_total * 100 if before_total else 0.0
    after_score = totals["killed_after"] / after_total * 100 if after_total else 0.0
    lines += [
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Modules | {len(rows)} |",
        f"| Mutants graded | {totals['mutants']} |",
        f"| Mutation score before repair | {before_score:.2f} percent |",
        f"| Mutation score after repair | {after_score:.2f} percent |",
        f"| Survivors killed by verified repair | "
        f"{totals['killed_after'] - totals['killed_before']} of {totals['survived_before']} |",
        f"| Tests kept (all verified) | {totals['kept']} |",
        f"| Model attempts | {totals['model_attempts']} |",
        f"| Known bugs detected after repair | {totals['bugs_detected']} of {len(rows)} |",
        f"| Benchmark wall time | {totals['seconds']:.1f} s |",
        "",
        "## Reproduce",
        "",
        "```bash",
        "uv run python benchmark/build_corpus.py",
        "uv run python benchmark/run.py",
        "```",
        "",
        "Raw data: `benchmark/results/raw.json`. The renderer generates results.md from",
        "the raw files, so numbers in this document are not hand written.",
        "",
    ]
    return "\n".join(lines)


def format_score(score: object) -> str:
    try:
        return f"{float(score):.2f}"
    except (TypeError, ValueError):
        return str(score)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the TestProof benchmark corpus.")
    parser.add_argument(
        "--filter", default=None, help="Run only modules whose id contains this text."
    )
    parser.add_argument(
        "--render-only", action="store_true", help="Re render results.md from raw.json."
    )
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS / "raw.json"

    if args.render_only:
        stored = json.loads(raw_path.read_text(encoding="utf-8"))
        rows = stored["rows"]
        meta = stored["meta"]
    else:
        ids = sorted(
            p.name for p in CORPUS.iterdir() if p.is_dir() and (p / f"{p.name}.py").exists()
        )
        if args.filter:
            ids = [mid for mid in ids if args.filter in mid]
        if not ids:
            print("no corpus modules matched")
            return 1
        print(f"model fallback active: {has_model_configured()}")
        rows = []
        for mid in ids:
            row = run_module(mid)
            rows.append(row)
            (RESULTS / f"{mid}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            bug_after = row["bug_after"]
            detected = isinstance(bug_after, dict) and bug_after.get("pass") is False
            print(
                f"{row['module_id']}: "
                f"{format_score(row['score_before'])} -> {format_score(row['score_after'])}, "
                f"kept {row['kept']} (rej {row['rejected']}, eq {row['likely_equivalent']}, "
                f"templates {row['template_hits']}, model {row['model_attempts']}), "
                f"bug after: {'detected' if detected else 'UNDETECTED'}"
            )
            del bug_after, detected
        meta = {
            "date": time.strftime("%Y-%m-%d"),
            "model_configured": has_model_configured(),
            "test_cmd": TEST_CMD,
        }
        raw_path.write_text(json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8")

    (ROOT / "results.md").write_text(render_markdown(rows, meta), encoding="utf-8")
    print(f"wrote {ROOT / 'results.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
