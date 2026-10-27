# TestProof

TestProof grades whether a test suite actually catches bugs. It runs mutation testing on the lines a pull request changed, reports the bugs the tests miss, and uses an open source model to write the missing tests. A deterministic engine keeps a proposed test only when it passes on the original code and fails on the mutant.

One line: passing tests are not the same as strong tests.

New here? Read `docs/ORIENTATION.md` first. It explains the product, why Alan is involved, what the event allows, what exists today, the phase map, and the corrected diff command.

## Why this exists

AI agents now write code and tests in the same pass. The tests pass, coverage looks healthy, and a human approves. But a passing test only proves that the code ran. It does not prove that the test would notice if the code were wrong.

The research is clear:

- Meta used LLM guided mutation testing in production and reported that privacy engineers accepted 73 percent of the generated tests.
- Google generated almost 17 million mutants across 760,000 code changes and surfaced 2 million during review.
- A 2026 study of LLM generated tests found that a simple prompt reached a 53 percent mutation score, and that generated tests often miss boundaries.

The problem is real. The tool space is crowded. TestProof competes on the workflow, not on a new mutation algorithm:

1. Diff scoped grading that fits a normal CI budget.
2. Verified repair. The model proposes, the engine proves the kill.
3. One report contract across the CLI, a skill, a GitHub Action, and Alan.
4. Honest reporting of partial scores, invalid mutants, and suspected equivalents.

Read `docs/BLUEPRINT.md` for the full judgment, architecture, and risk analysis.

## How it works

```text
pull request diff
      |
      v
diff resolver  ->  Python adapter  ->  sandbox  ->  project test command
                                                        |
                                                        v
                                          killed, survived, invalid, timeout
                                                        |
                                                        v
                                               score and report
                                                        |
                                                        v
                                     open source model proposes a test
                                                        |
                                                        v
                                  verifier: pass on original, fail on mutant
                                                        |
                                                        v
                                            keep the test or reject it
```

The mutation engine is deterministic. No model call happens in discovery, execution, classification, or scoring. The model only proposes tests, and the verifier decides what is kept.

## What ships

| Surface | Purpose | Status |
| --- | --- | --- |
| `testproof` CLI | Grade changed code and emit a JSON report | Phase 1 deterministic engine |
| `skills/testproof/SKILL.md` | Teach an agent when and how to run the loop | Drafted |
| GitHub Action | Gate a pull request on test strength | Planned for Phase 2 |
| Report schema | Shared contract for every surface | Specified |
| Static report viewer | Demo surface for the hackathon video | Planned for Phase 5 |
| Remote MCP server | Alan marketplace plugin | Roadmap |

The current repository contains the Phase 0 foundation and the Phase 1 deterministic Python engine: packaging, Git diff resolution, mutation adapter, isolated sandbox, bounded test runner, scoring, JSON reports, and acceptance tests. Markdown reports, threshold gating, and the GitHub Action are next in Phase 2. Verified repair with an open model is planned for Phase 3. This status is explicit so nobody mistakes the engine for a finished repair product.

## Quick start

```bash
uv sync
uv run testproof --version
uv run pytest -q
make check
```

Try the diff resolver on any git repository:

```bash
# Uncommitted work, including staged and untracked files
uv run testproof diff --repo /path/to/repo

# Everything since the previous commit, including the working tree
uv run testproof diff --base HEAD~1 --repo /path/to/repo

# Committed pull request diff only
uv run testproof diff --base origin/main --head HEAD --repo /path/to/repo
```

`testproof diff` is not a `git status` clone. It resolves a change set from a base to a target, and the base decides what is included. The output names both sides so the comparison is explicit. In JSON, the working tree target is the string `WORKTREE`.

The demonstration fixture is intentionally weak. Its tests pass with full line coverage and still miss the boundary at 50. It is not its own Git repository, so use `--all` to grade its Python files. In normal Git repositories, grading stays diff scoped by default.

```bash
cd fixtures/shop
python -m pytest -q
python -m pytest --cov=. --cov-report=term-missing

cd ../..
uv run testproof grade --repo fixtures/shop --all --test-cmd "uv run pytest -q" --format json
```

## Repository layout

```text
testproof/
├── AGENTS.md                 Rules for agents working in this repo
├── CONSTRAINTS.md            The quality bar with numbers
├── README.md
├── pyproject.toml
├── Makefile
├── docs/
│   ├── BLUEPRINT.md          End to end product and system design
│   ├── BUILD_PLAN.md         Phase plan, checkpoints, and cut lines
│   ├── CROSS_RESEARCH.md     Evidence and competitive analysis
│   ├── EVAL.md               Benchmark and evaluation design
│   ├── METHODOLOGY.md        Build and evidence method
│   ├── WORKFLOW.md           Alan, CI, and local flows
│   ├── GLOSSARY.md           Domain terms
│   └── INIT_PROMPT.md        Paste ready coding session prompt
├── diagrams/                 Mermaid sources and Excalidraw canvas
├── skills/testproof/         Portable agent skill
├── src/testproof/            CLI and diff resolver
├── tests/                    Unit tests
├── fixtures/shop/            Deliberately weak demo suite
└── .github/workflows/        CI and a manual TestProof preview
```

## Design principles

- Measure deterministically. A score must be reproducible.
- Mutate only what changed. Full repository runs are opt in.
- Never touch the working tree. Every mutant runs in a sandbox.
- Cap the work and keep a time budget. Report a partial score honestly.
- Let the model propose. Let the engine verify.
- Treat the report as the contract. Every integration reads the same schema.
- Say what the score does not prove. A high score is evidence, not correctness.

## Build status

| Phase | Output | Gate |
| --- | --- | --- |
| 0 Foundation | Repo, CLI, diff resolver, fixture, CI | Complete |
| 1 Deterministic engine | Mutation, sandbox, runner, score, JSON | Complete at Phase 1 checkpoint |
| 2 Report and CI gate | Markdown, threshold, GitHub Action | Pull request fails below threshold |
| 3 Verified repair | Model client, verifier, apply | Score rises with verified tests |
| 4 Alan skill | Skill, automation recipe, artifact | Runs in a real session |
| 5 Benchmark and demo | Corpus, metrics, README, video | Before and after are measurable |
| 6 Hardening | Errors, license, release, submission | Fresh clone works |

Phase 0 and Phase 1 are complete at the current checkpoint. `make check-full` passes with 68 tests and 87.93 percent coverage. The fixture grade is reproducible: 8 mutants are killed, 1 boundary mutant survives, for a score of 88.9 percent. Phase 2, the Markdown report and CI threshold gate, is next.

The full gate for each phase is in `docs/BUILD_PLAN.md`.

## Documentation

- `docs/ORIENTATION.md` for the plain language map of the product, the event rules, and the current phase.
- `docs/BLUEPRINT.md` for requirements, architecture, ADRs, and risks.
- `docs/METHODOLOGY.md` for the build and evidence method.
- `docs/BUILD_PLAN.md` for the hour by hour plan and checkpoints.
- `docs/CROSS_RESEARCH.md` for the evidence and the caveats.
- `docs/EVAL.md` for the benchmark and the falsifiable claims.
- `docs/WORKFLOW.md` for the Alan, CI, and local flows.
- `docs/INIT_PROMPT.md` for the prompt that starts the coding session.

## License

MIT. See `LICENSE`.
