from __future__ import annotations

import hashlib
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


class Sandbox:
    """Copy the repository into a temporary directory and yield the workspace."""

    def __init__(self, repo: Path):
        self._repo = repo.resolve()

    @contextmanager
    def create(self) -> Generator[Path, None, None]:
        root = Path("/tmp/opencode/testproof")
        root.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(self._repo).encode("utf-8")).hexdigest()[:10]

        with tempfile.TemporaryDirectory(prefix=f"tp-{key}-", dir=str(root)) as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(
                self._repo,
                workspace,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git"),
            )
            yield workspace
