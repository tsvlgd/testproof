"""Performance guard for the small end to end fixture grade."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from testproof.engine import MutationEngine

FIXTURE = Path(__file__).parents[1] / "fixtures" / "shop"


def test_fixture_grade_completes_within_sixty_seconds() -> None:
    engine = MutationEngine(
        repo=FIXTURE,
        test_command=f"{sys.executable} -m pytest -q",
    )
    started = time.monotonic()

    report = engine.grade(
        target="WORKTREE",
        base_ref=None,
        head_ref=None,
        merge_base=None,
        changed_files=[("shipping.py", None)],
        all_files=True,
    )

    elapsed = time.monotonic() - started
    assert report.summary.total > 0
    assert elapsed <= 60
