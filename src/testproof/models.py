"""Domain types and the report contract for a TestProof grade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MutantStatus = Literal["killed", "survived", "invalid", "timeout", "skipped"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class MutationPoint:
    """One exact source span that can be replaced by one operator."""

    id: str
    path: str
    line: int
    column: int
    end_line: int
    end_column: int
    operator: str
    original: str
    replacement: str


@dataclass(frozen=True)
class Mutant:
    """The outcome of running the test command against one planted bug."""

    point: MutationPoint
    status: MutantStatus
    duration_ms: int = 0
    output: str = ""
    suspected_equivalent: bool = False


@dataclass(frozen=True)
class FileReport:
    """Scores and mutants for one source file."""

    path: str
    score: float | None
    mutants: tuple[Mutant, ...]


@dataclass(frozen=True)
class Summary:
    """The run total. Invalid, timeout, and skipped mutants are not in the score."""

    score: float | None
    killed: int
    survived: int
    invalid: int
    timeout: int
    skipped: int
    total: int
    partial: bool
    confidence: Confidence
    reason: str = ""


@dataclass(frozen=True)
class ToolInfo:
    """Which TestProof produced the report."""

    name: str
    version: str


@dataclass(frozen=True)
class RunInfo:
    """The exact inputs needed to repeat a grade."""

    id: str
    started_at: str
    duration_ms: int
    base_ref: str | None
    head_ref: str | None
    target: str
    merge_base: str | None
    test_command: str
    language: str
    threshold: float | None
    time_budget_ms: int
    max_mutants: int
    all_files: bool


@dataclass(frozen=True)
class Report:
    """The contract shared by the CLI, the Action, the skill, and a future MCP server."""

    schema_version: str
    tool: ToolInfo
    run: RunInfo
    summary: Summary
    files: tuple[FileReport, ...]
    errors: tuple[str, ...] = field(default_factory=tuple)
