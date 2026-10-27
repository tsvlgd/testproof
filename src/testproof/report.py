from __future__ import annotations

import json
from dataclasses import asdict

from testproof.models import Report


def to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True)


def to_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append("# TestProof Report")
    lines.append("")
    score_str = f"{report.summary.score:.1f}%" if report.summary.score is not None else "N/A"
    lines.append(f"**Score**: {score_str}")
    lines.append(f"**Threshold**: {report.run.threshold}")
    lines.append(f"**Status**: {'pass' if _passes(report) else 'fail'}")
    lines.append(f"**Partial**: {'yes' if report.summary.partial else 'no'}")
    lines.append(f"**Confidence**: {report.summary.confidence}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("| --- | --- |")
    lines.append(f"| Killed | {report.summary.killed} |")
    lines.append(f"| Survived | {report.summary.survived} |")
    lines.append(f"| Invalid | {report.summary.invalid} |")
    lines.append(f"| Timeout | {report.summary.timeout} |")
    lines.append(f"| Skipped | {report.summary.skipped} |")
    lines.append(f"| Total | {report.summary.total} |")
    lines.append("")

    if report.files:
        lines.append("## Files")
        lines.append("")
        lines.append("| File | Score | Killed | Survived | Invalid |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in report.files:
            killed = sum(1 for m in f.mutants if m.status == "killed")
            survived = sum(1 for m in f.mutants if m.status == "survived")
            invalid = sum(1 for m in f.mutants if m.status == "invalid")
            score_str = f"{f.score:.1f}%" if f.score is not None else "N/A"
            lines.append(f"| {f.path} | {score_str} | {killed} | {survived} | {invalid} |")
        lines.append("")

    survivors = [(f.path, m) for f in report.files for m in f.mutants if m.status == "survived"]
    if survivors:
        lines.append("## Survivors")
        lines.append("")
        for path, m in survivors:
            lines.append(
                f"- `{path}:{m.point.line}` changed `{m.point.original}` to "
                f"`{m.point.replacement}`. No test checks this case."
            )
        lines.append("")

    lines.append("## What this means")
    lines.append("")
    lines.append(
        "The tests run every line, but some planted bugs survive. "
        "Passing tests are not the same as strong tests."
    )
    lines.append("")
    lines.append("## What this does not mean")
    lines.append("")
    lines.append(
        "A high mutation score does not prove correctness. "
        "It means the tests catch the planted bugs in the changed lines."
    )
    lines.append("")

    if report.summary.partial:
        lines.append("## Partial run")
        lines.append("")
        lines.append(f"**Reason**: {report.summary.reason}")
        lines.append("")

    if report.errors:
        lines.append("## Errors")
        lines.append("")
        for err in report.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def _passes(report: Report) -> bool:
    if report.run.threshold is None:
        return True
    if report.summary.score is None:
        return False
    return report.summary.score >= report.run.threshold
