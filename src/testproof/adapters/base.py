"""The seam between the engine and one programming language."""

from __future__ import annotations

from typing import Protocol

from testproof.models import MutationPoint


class LanguageAdapter(Protocol):
    """Find mutation points in one language and splice them into source text."""

    language: str
    file_extensions: tuple[str, ...]

    def discover(
        self,
        path: str,
        source: str,
        changed_lines: set[int] | None,
    ) -> list[MutationPoint]:
        """Return mutation points. ``None`` means every line is in scope."""

    def apply(self, source: str, point: MutationPoint) -> str:
        """Return source with exactly one mutation spliced in."""

    def validate(self, source: str) -> bool:
        """Return whether the mutated source can be parsed."""
