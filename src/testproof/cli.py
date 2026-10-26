"""Command line entry point for TestProof."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from testproof import __version__
from testproof.diff import ChangedFile, Diff, DiffError, resolve_diff

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


if __name__ == "__main__":
    app()
