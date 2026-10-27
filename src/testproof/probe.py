"""Probe a target function in a separate interpreter.

The probe is used to find inputs that make the original code and a mutant
produce different results. It never imports the project into the TestProof
process, so a broken module or a module with side effects cannot corrupt a
repair run.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from testproof.sandbox import isolated_env


@dataclass(frozen=True)
class ProbeOutcome:
    """One function call and its result."""

    ok: bool
    value_repr: str | None = None
    error: str | None = None


_PROBE_SCRIPT = """\
import ast
import importlib
import json
import sys

request = json.load(open(".testproof_probe.json", encoding="utf-8"))
for path in reversed(request["paths"]):
    sys.path.insert(0, path)

try:
    module = importlib.import_module(request["module"])
    function = getattr(module, request["func"])
except Exception as exc:
    print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
    raise SystemExit(0)

results = []
for case in request["cases"]:
    try:
        args = [ast.literal_eval(item) for item in case]
    except Exception as exc:
        results.append({"ok": False, "error": f"bad case: {type(exc).__name__}: {exc}"})
        continue
    try:
        value = function(*args)
    except Exception as exc:
        results.append({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})
        continue
    try:
        literal = ast.literal_eval(repr(value))
    except Exception:
        results.append({"ok": False, "error": "unrepresentable"})
        continue
    results.append({"ok": True, "value": repr(literal)})

print(json.dumps({"results": results}))
"""


def module_for(repo: Path, file_path: str) -> tuple[str, Path] | None:
    """Return the importable module name and import root for a source file."""
    repo = repo.resolve()
    path = Path(file_path)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(repo)
        except ValueError:
            return None

    import_root = repo
    if path.parts and path.parts[0] == "src" and (repo / "src").is_dir():
        import_root = repo / "src"
        path = Path(*path.parts[1:])

    if path.suffix != ".py":
        return None
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts), import_root


def probe_cases(
    workspace: Path,
    module: str,
    func_name: str,
    cases: list[tuple[Any, ...]],
    *,
    timeout_seconds: int = 20,
) -> tuple[list[ProbeOutcome] | None, str | None]:
    """Run ``func_name`` for every case in ``workspace``.

    Returns the outcomes and an error string. The error string is set when the
    module cannot be imported or the probe interpreter cannot be started.
    """
    if not cases:
        return [], None

    request_cases: list[list[str]] = []
    for case in cases:
        rendered: list[str] = []
        valid = True
        for value in case:
            try:
                text = repr(value)
                if ast.literal_eval(text) != value:
                    raise ValueError
            except (SyntaxError, ValueError, TypeError):
                valid = False
                break
            rendered.append(text)
        if valid:
            request_cases.append(rendered)

    if not request_cases:
        return [], None

    request_path = workspace / ".testproof_probe.json"
    script_path = workspace / ".testproof_probe.py"
    request = {
        "paths": [str(workspace / "src"), str(workspace)]
        if (workspace / "src").is_dir()
        else [str(workspace)],
        "module": module,
        "func": func_name,
        "cases": request_cases,
    }

    try:
        request_path.write_text(json.dumps(request), encoding="utf-8")
        script_path.write_text(_PROBE_SCRIPT, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=workspace,
            env=isolated_env(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"probe failed: {exc}"
    finally:
        request_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)

    payload: dict[str, Any] | None = None
    for line in reversed(completed.stdout.strip().splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break

    if payload is None:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else ""
        return None, f"probe returned no JSON: {detail[:200]}"
    if "error" in payload:
        return None, str(payload["error"])

    outcomes: list[ProbeOutcome] = []
    for item in payload.get("results", []):
        outcomes.append(
            ProbeOutcome(
                ok=bool(item.get("ok")),
                value_repr=item.get("value"),
                error=item.get("error"),
            )
        )
    return outcomes, None
