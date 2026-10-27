"""Command line entry point for TestProof."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Literal

import typer

from testproof import __version__
from testproof.diff import ChangedFile, Diff, DiffError, resolve_diff
from testproof.engine import MutationEngine
from testproof.model import ModelClient
from testproof.repair import RepairEngine
from testproof.report import to_json, to_markdown

app = typer.Typer(
    help="Grade whether a test suite catches bugs.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"testproof {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            callback=_version_callback,
            is_eager=True,
            help="Show the TestProof version and exit.",
        ),
    ] = False,
) -> None:
    """TestProof command line interface."""

    del version


@app.command("diff")
def diff_command(
    base: Annotated[
        str,
        typer.Option(help="Base revision to compare from. Defaults to HEAD."),
    ] = "HEAD",
    head: Annotated[
        str | None,
        typer.Option(
            help=(
                "Head revision to compare to. Omit to compare against the working tree, "
                "including staged and untracked files."
            )
        ),
    ] = None,
    repo: Annotated[
        Path,
        typer.Option(help="Repository root. Defaults to the current directory."),
    ] = Path(),
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the diff as JSON instead of text."),
    ] = False,
) -> None:
    """List changed files and changed line ranges for a base and a target."""

    try:
        diff = resolve_diff(repo=repo, base=base, head=head)
    except DiffError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(_diff_payload(diff), indent=2))
        return

    typer.echo(f"Base: {diff.base}")
    typer.echo(f"Target: {_target_label(diff.head)}")
    if not diff.files:
        typer.echo("No changed files.")
        return

    typer.echo(f"Changed files: {len(diff.files)}")
    for changed in diff.files:
        typer.echo(f"  {_describe(changed)}")
    line_word = "line" if diff.changed_line_count == 1 else "lines"
    typer.echo(f"Changed {line_word}: {diff.changed_line_count}")


def _target_label(head: str) -> str:
    return "working tree" if head == "WORKTREE" else head


def _describe(changed: ChangedFile) -> str:
    if not changed.lines:
        return f"{changed.status:<9} {changed.path}"
    ranges = ", ".join(str(line_range) for line_range in changed.lines)
    return f"{changed.status:<9} {changed.path}  lines {ranges}"


def _diff_payload(diff: Diff) -> dict[str, object]:
    return {
        "base": diff.base,
        "head": diff.head,
        "changed_line_count": diff.changed_line_count,
        "files": [
            {
                "path": changed.path,
                "status": changed.status,
                "old_path": changed.old_path,
                "lines": [
                    {"start": line_range.start, "end": line_range.end}
                    for line_range in changed.lines
                ],
            }
            for changed in diff.files
        ],
    }


@app.command("grade")
def grade_command(
    repo: Annotated[
        Path,
        typer.Option(help="Repository root. Defaults to the current directory."),
    ] = Path(),
    base: Annotated[str, typer.Option(help="Base revision to compare from.")] = "HEAD",
    head: Annotated[
        str | None,
        typer.Option(help="Head revision to compare to. Omit to compare against working tree."),
    ] = None,
    test_cmd: Annotated[str, typer.Option(help="Test command to run for grading.")] = "pytest -q",
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the report as JSON."),
    ] = False,
    all_files: Annotated[
        bool,
        typer.Option("--all", help="Grade all files instead of diff-scoped."),
    ] = False,
    output_format: Annotated[
        Literal["json", "text", "markdown"],
        typer.Option("--format", help="Output format: text, json, or markdown."),
    ] = "text",
    threshold: Annotated[
        float | None,
        typer.Option("--threshold", help="Minimum mutation score to pass."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the report to a file."),
    ] = None,
) -> None:
    """Grade whether a test suite catches bugs."""

    original_repo = repo
    try:
        # When --head names a commit, grade the source at that commit
        if head is not None and head != "WORKTREE":
            temp_dir = tempfile.mkdtemp(prefix="testproof-head-")
            archive_proc = subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", head],
                capture_output=True,
                check=True,
            )
            extract_proc = subprocess.run(
                ["tar", "-xf", "-", "-C", temp_dir],
                input=archive_proc.stdout,
                capture_output=True,
            )
            if extract_proc.returncode != 0:
                raise RuntimeError(
                    f"Failed to extract commit source: {extract_proc.stderr.decode()}"
                )
            repo = Path(temp_dir)

        if all_files:
            repo = repo.resolve()
            changed_files: list[tuple[str, set[int] | None]] = []
            excluded = {
                ".git",
                ".venv",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            }
            for path in repo.rglob("*.py"):
                relative = path.relative_to(repo)
                if excluded.intersection(relative.parts):
                    continue
                # Skip test files and documentation
                if relative.name.startswith("test_") or relative.name.endswith("_test.py"):
                    continue
                changed_files.append((relative.as_posix(), None))
            target = "WORKTREE"
            merge_base = None
            base_ref = None
            head_ref = None
        else:
            diff = resolve_diff(repo=original_repo, base=base, head=head)
            changed_files = []
            for changed in diff.files:
                # Skip non-Python files, test files, and documentation
                if not changed.path.endswith(".py"):
                    continue
                if changed.path.startswith("docs/") or changed.path.startswith("scripts/"):
                    continue
                basename = Path(changed.path).name
                if basename.startswith("test_") or basename.endswith("_test.py"):
                    continue
                line_set = None
                if changed.lines:
                    line_set = {ln for rng in changed.lines for ln in range(rng.start, rng.end + 1)}
                changed_files.append((changed.path, line_set))
            target = "HEAD" if head is not None and head != "WORKTREE" else "WORKTREE"
            merge_base = None
            base_ref = diff.base
            head_ref = diff.head

        engine = MutationEngine(repo=repo, test_command=test_cmd, threshold=threshold)
        report = engine.grade(
            target=target,
            base_ref=base_ref,
            head_ref=head_ref,
            merge_base=merge_base,
            changed_files=changed_files,
            all_files=all_files,
        )
    except DiffError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    # Determine output content
    if output_format == "json" or as_json:
        content = to_json(report)
    elif output_format == "markdown":
        content = to_markdown(report)
    else:
        content = None

    # Write to file if requested
    if output is not None:
        output.write_text(content if content is not None else to_json(report), encoding="utf-8")

    # Print to stdout
    if content is not None:
        typer.echo(content)
    else:
        typer.echo(f"Score: {report.summary.score}")
        for error in report.errors:
            typer.echo(f"Notice: {error}")
        if report.summary.partial:
            typer.echo(f"Partial grade: {report.summary.reason}")

    # Exit codes
    if report.summary.score is None:
        raise typer.Exit(code=2)
    if threshold is not None and report.summary.score < threshold:
        raise typer.Exit(code=1)


@app.command("report")
def report_command(
    input: Annotated[
        Path,
        typer.Option(help="Input JSON report file."),
    ],
    format: Annotated[
        Literal["json", "markdown", "text"],
        typer.Option("--format", help="Output format."),
    ] = "markdown",
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write output to a file."),
    ] = None,
) -> None:
    """Render a report from a JSON file."""
    from testproof.models import Report
    from testproof.report import to_markdown

    report_data = json.loads(input.read_text(encoding="utf-8"))
    # Reconstruct a minimal Report for rendering
    # For markdown, we just need the summary and files
    if format == "markdown":
        # Build a simplified report object
        from testproof.models import (
            FileReport,
            Mutant,
            MutationPoint,
            RunInfo,
            Summary,
            ToolInfo,
        )

        run = RunInfo(**report_data["run"])
        summary = Summary(**report_data["summary"])
        files = []
        for f in report_data["files"]:
            mutants = []
            for m in f["mutants"]:
                point = MutationPoint(**m["point"])
                mutants.append(
                    Mutant(
                        point=point,
                        status=m["status"],
                        duration_ms=m["duration_ms"],
                        output=m["output"],
                    )
                )
            files.append(FileReport(path=f["path"], score=f["score"], mutants=tuple(mutants)))
        report = Report(
            schema_version=report_data["schema_version"],
            tool=ToolInfo(**report_data["tool"]),
            run=run,
            summary=summary,
            files=tuple(files),
            errors=tuple(report_data.get("errors", [])),
        )
        content = to_markdown(report)
    elif format == "json":
        content = json.dumps(report_data, indent=2)
    else:
        content = f"Score: {report_data['summary']['score']}"

    if output is not None:
        output.write_text(content, encoding="utf-8")
    else:
        typer.echo(content)


@app.command("repair")
def repair_command(
    repo: Annotated[
        Path,
        typer.Option(help="Repository root. Defaults to the current directory."),
    ] = Path(),
    report: Annotated[
        Path,
        typer.Option(help="Path to the JSON report from a previous grade."),
    ] = Path(".testproof/report.json"),
    test_cmd: Annotated[
        str,
        typer.Option(help="Test command to run for verification."),
    ] = "pytest -q",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Propose tests without writing them."),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write verified tests to the test file."),
    ] = False,
) -> None:
    """Repair survivors with an open source model."""
    import json as _json

    from testproof.models import Report

    report_data = _json.loads(report.read_text(encoding="utf-8"))
    # Reconstruct report
    from testproof.models import (
        FileReport,
        Mutant,
        MutationPoint,
        RunInfo,
        Summary,
        ToolInfo,
    )

    run = RunInfo(**report_data["run"])
    summary = Summary(**report_data["summary"])
    files = []
    for f in report_data["files"]:
        mutants = []
        for m in f["mutants"]:
            point = MutationPoint(**m["point"])
            mutants.append(
                Mutant(
                    point=point,
                    status=m["status"],
                    duration_ms=m["duration_ms"],
                    output=m["output"],
                )
            )
        files.append(FileReport(path=f["path"], score=f["score"], mutants=tuple(mutants)))
    rep = Report(
        schema_version=report_data["schema_version"],
        tool=ToolInfo(**report_data["tool"]),
        run=run,
        summary=summary,
        files=tuple(files),
        errors=tuple(report_data.get("errors", [])),
    )

    model = ModelClient.from_env()
    repair_engine = RepairEngine(repo=repo, test_command=test_cmd, model_client=model)

    result = repair_engine.repair(rep, dry_run=dry_run, apply=apply)

    typer.echo(f"Kept: {len(result.kept)}")
    typer.echo(f"Rejected: {len(result.rejected)}")
    for record in result.rejected:
        typer.echo(f"  Rejected {record.test_id}: {record.reason}")
    for mutant_id, test_code in result.kept:
        typer.echo(f"  Kept test for {mutant_id}:")
        typer.echo(test_code)

    model.close()


if __name__ == "__main__":
    app()
