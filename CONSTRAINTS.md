# Constraints

Last reviewed: 2026-10-26 by the TestProof maintainer.

This file is the quality bar for TestProof. Read it before writing code. Do not weaken it to make a change pass.

## Floor (always enforced)

- No new suppression comments without a reason in the commit message: `# type: ignore`, `# noqa`, `# pragma: no cover`.
- No unimplemented stubs: no `raise NotImplementedError` on a shipping path, no empty `except` blocks, no placeholder functions that pretend to work.
- No skipped or deleted tests without a reason in the commit message.
- No secrets in source, fixtures, logs, or reports.
- No mutation of the working tree. Only sandbox copies.
- No model call inside measurement, classification, or scoring.
- This file does not get weakened to make a change pass.

## Enforced with numbers

| Dimension | Rule | Checked by | Runs at |
| --- | --- | --- | --- |
| Types | Zero mypy errors on `src` | `uv run mypy src` | every change |
| Lint | Zero ruff errors | `uv run ruff check .` | every change |
| Format | No formatting drift | `uv run ruff format --check .` | every change |
| Unit tests | All pass | `uv run pytest -q` | every change |
| Coverage | `src/testproof` at or above 85 percent | `uv run pytest --cov=testproof --cov-fail-under=85` | every change |
| Fixture | The weak suite passes and still documents the gap | `make fixture` | every change |
| Security | No medium, high, or critical findings | `uv run bandit -q -r src -ll` | CI |

### Enforced from the phase shown

| Dimension | Rule | Checked by | Starts at |
| --- | --- | --- | --- |
| Determinism | Two runs on the same fixture produce the same score and mutant ids | `uv run pytest tests/test_determinism.py` | Phase 1 |
| Sandbox safety | The working tree hash is unchanged after a grade | `uv run pytest tests/test_sandbox.py` | Phase 1 |
| Performance | Fixture grade completes in 60 seconds or less | `uv run pytest tests/test_performance.py` | Phase 1 |
| Self mutation | TestProof's own test suite scores at or above 70 percent | `uv run testproof grade --base HEAD~1 --test-cmd "uv run pytest -q" --threshold 70` | Phase 2 |

These are not optional. They are simply not measurable until the engine exists. Do not report them as passing before the first run.

### Why these numbers

- 85 percent coverage on `src/testproof` is high enough to force tests on the engine and low enough to allow small config branches.
- 70 percent self mutation is a starting ratchet. A suite that has never been mutated typically scores between 50 and 70. The tool should dogfood its own metric.
- 60 seconds for the fixture keeps the tight loop usable. The fixture is a small repo with a handful of mutants.

## Measured, not yet enforced

| Metric | Today | Direction |
| --- | --- | --- |
| Mutation score on the fixture | not measured | must rise from the baseline after repair |
| Bug detection rate on the benchmark | not measured | must rise after repair |
| Repair acceptance rate | not measured | must stay above 50 percent |
| Full corpus grade time | not measured | must not grow without a reason |

## Exceptions

| ID | Rule | Path | Reason | Owner | Expires |
| --- | --- | --- | --- | --- | --- |
| E1 | Coverage 85 percent | `src/testproof/adapters/js.py` | Stretch adapter, added after Phase 3 | maintainer | 2026-11-30 |
| E2 | Self mutation 70 percent | whole repo | First measured baseline, ratchet after Phase 5 | maintainer | 2026-11-30 |

An exception without an owner and an expiry date is not an exception.

## Command mapping

- `make check-fast`: ruff check, ruff format check, mypy. Target under 5 seconds.
- `make check`: fast checks plus `pytest -q`. Target under 90 seconds.
- `make check-full`: task checks plus coverage, bandit, and the fixture tests. CI adds the package build.

`make check` runs the fast checks and the unit tests.

## Guarding the bar

At review time, compare the diff against this file. Watch for:

- A threshold moved down.
- A test skipped or deleted.
- A new suppression comment.
- A stub that throws or returns a placeholder.
- A new exception row nobody discussed.
- A model call added to the measurement path.

Tightening the bar should be silent. Loosening it should be loud.
