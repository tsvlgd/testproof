# TestProof Project Rules

This file applies only to the TestProof project in this directory. It does not apply to any other project.

## What this project is

TestProof is an open source test strength gate for AI written code. It grades whether a test suite actually catches bugs using mutation testing, then uses an open source model to write the missing tests and verifies every proposed test by re running the mutant. It ships as a command line tool, an agent skill, and a GitHub Action.

## Read before writing code

1. `docs/ORIENTATION.md`
2. `CONSTRAINTS.md`
3. `docs/BLUEPRINT.md`
4. `docs/METHODOLOGY.md`
5. `docs/BUILD_PLAN.md`
6. `docs/EVAL.md`
7. `docs/WORKFLOW.md`
8. `skills/testproof/SKILL.md`

## Stack

- Python 3.11 or newer
- `uv` for environment and dependency management
- `typer` and `rich` for the CLI
- `pydantic` v2 for the report schema
- `httpx` for the open model client
- `pytest` and `pytest-cov` for tests
- `ruff` for lint and format
- `mypy` for types
- GitHub Actions for CI
- Optional: `fastmcp` for the MCP server stretch goal

## Commands

```bash
uv sync
uv run pytest -q
uv run pytest --cov=testproof --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run testproof --version
make check
make check-full
```

## Non negotiables

- The mutation engine is deterministic. No model call happens in measurement, classification, or scoring.
- The unit of work is a repository, a diff, and a project test command. Never a single uploaded file.
- Never mutate the working tree. Every mutant runs in an isolated sandbox.
- Every mutant run has a timeout. A hung test is a timeout, not a kill.
- A proposed test is kept only if it passes on the original code and fails on the mutant. The model proposes, the engine verifies.
- No unimplemented stubs. No skipped tests. No weakened constraints.
- No secrets in source, logs, reports, or test fixtures.
- strictly follow the docs/*.md (make sure they correlate and consistent and update with plans and disucssion and changes ) and follow them strictly and if there's any architectural and feature changes have got then make sure to update them on the fly but always follow and keep them consistent with build plan and status (state and steps).
- Every phase ends with a runnable command, tests, and a checkpoint note.
- Commit after each phase or if there's important checkpoint of major change or refactor or feature additions within a phase comes in that aslo to be commited or pushed don't wait for the phase to be completed or pusehd with a conventional commit message.

## Project structure

Target structure after Phase 3. Phase 0 ships the files that exist today: the CLI, the diff resolver, the tests, the fixture, the skill, the docs, and CI.

```text
testproof/
├── AGENTS.md
├── CONSTRAINTS.md
├── README.md
├── pyproject.toml
├── Makefile
├── docs/
│   ├── ORIENTATION.md
│   ├── BLUEPRINT.md
│   ├── BUILD_PLAN.md
│   ├── CROSS_RESEARCH.md
│   ├── EVAL.md
│   ├── METHODOLOGY.md
│   ├── WORKFLOW.md
│   ├── GLOSSARY.md
│   └── INIT_PROMPT.md
├── diagrams/
│   ├── architecture.mmd
│   ├── sequence.mmd
│   ├── states.mmd
│   ├── phases.mmd
│   └── testproof.excalidraw
├── scripts/
│   └── make_excalidraw.py
├── skills/
│   └── testproof/
│       └── SKILL.md
├── src/
│   └── testproof/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── diff.py
│       ├── engine.py
│       ├── models.py
│       ├── report.py
│       ├── repair.py
│       ├── runner.py
│       ├── sandbox.py
│       └── adapters/
│           ├── __init__.py
│           ├── base.py
│           └── python.py
├── tests/
├── fixtures/
│   └── shop/
└── .github/
    └── workflows/
        ├── ci.yml
        └── testproof.yml
```

## Definition of done for a phase

- The phase acceptance command runs and produces the expected output.
- New behavior has a failing test first, then a passing test.
- `make check` is green.
- The checkpoint note in `docs/BUILD_PLAN.md` is updated with the result.
- The diff is reviewed before the next phase starts.

## Working with the agent

- Restate the phase goal and acceptance criteria before editing.
- Ask one question at a time when a requirement is ambiguous.
- Prefer small, reviewable commits.
- Do not touch files outside this project.
- Do not claim a phase is done without running the command.
- If a phase runs over budget, cut scope according to the cut line. Do not lower quality.
