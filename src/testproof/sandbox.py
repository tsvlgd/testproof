from __future__ import annotations

import hashlib
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class Sandbox:
    """Isolated workspace where mutants run.

    This class copies the target repository into a temporary directory.
    The host working tree is never modified.
    """

    def __init__(self, repo: Path):
        self._repo = repo.resolve()

    @contextmanager
    def create(self) -> Generator[Path, None, None]:
        # Prefer the approved /tmp/opencode area.
        root = Path("/tmp/opencode") / "testproof"
        root.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(self._repo).encode()).hexdigest()[:10]

        with tempfile.TemporaryDirectory(prefix=f"tp-{key}-", dir=str(root)) as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            shutil.copytree(
                self._repo,
                workspace,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git"),
            )
            yield workspace
