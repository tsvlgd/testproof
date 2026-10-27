from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def isolated_env(workspace: Path) -> dict[str, str]:
    """Return an environment that imports the sandbox copy, not the host package."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    paths = [str(workspace)]
    if (workspace / "src").is_dir():
        paths.insert(0, str(workspace / "src"))
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class Sandbox:
    """Copy the repository into a private temporary workspace."""

    def __init__(self, repo: Path):
        self._repo = repo.resolve()

    @contextmanager
    def create(self) -> Generator[Path, None, None]:
        key = hashlib.sha256(str(self._repo).encode("utf-8")).hexdigest()[:10]

        with tempfile.TemporaryDirectory(prefix=f"tp-{key}-") as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(
                self._repo,
                workspace,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".venv",
                    "__pycache__",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                    ".coverage",
                ),
            )
            yield workspace
