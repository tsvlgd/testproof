# Orientation

This is the shortest path from "I have no idea what this repo is" to "I know what exists, what is next, and why Alan is involved." Read this before the deeper design docs.

## What TestProof is

TestProof is an open source test strength gate for AI written code. A passing test suite proves that the code ran. It does not prove that the tests would notice if the code were wrong. TestProof plants small bugs, called mutants, in the lines a change touched. It runs the project's own test command against each mutant in a sandbox. A test suite that fails on a mutant killed it. A suite that still passes let it survive. The mutation score is killed divided by killed plus survived.

The second half is repair. An open source model proposes one test for each survivor. A deterministic verifier keeps a test only if it passes on the original code, fails on the mutant, and leaves the full suite green. The model proposes. The engine verifies.

The product has four surfaces:

| Surface | Purpose |
| --- | --- |
| `testproof` CLI | Grade a repository and repair survivors. This is the core. |
| `skills/testproof/SKILL.md` | Teach Alan and other agents when and how to run the loop. |
| GitHub Action | Gate a pull request on test strength. |
| Report artifact | JSON and Markdown evidence for a pull request or an Alan task. |

Python ships first. JavaScript and TypeScript are a stretch goal. Frameworks are handled by the project's own test command, not by a framework integration.

## Why Alan is part of this

OpenFire is Alan's hackathon. The event page says: build an open source tool for people using Alan AI, with Alan and open models. Alan is the platform and the demo surface, not a runtime dependency of the core engine. The CLI works without Alan. Alan is how a user finds the tool, runs it inside an agent session, and attaches the result as evidence.

The event gives participants the Alan AI $10 Individual plan for $0 during the promotional period with the code `ALANOPENFIRE2026`. The Individual feature tier adds cloud sessions and sandboxes, the code index and context graph, and personal skills. The free tier is local only. Those paid features matter for the demo because the skill runs in a cloud session and the report is attached to the task.

The Pro, Pro+, and Max labels on the pricing page are usage plans. The Individual label is the feature tier. If you paid for a usage plan, check the plan page and confirm that the promo reduced the $10 feature tier to $0. The event does not require a paid usage plan.

The demo sequence is the reason for the setup:

1. An Alan agent opens a pull request with green tests.
2. The agent loads the TestProof skill.
3. The skill runs `testproof grade` on the changed lines.
4. The report shows a score below the threshold and lists the survivors.
5. The skill runs `testproof repair` with an open source model.
6. The verifier keeps only the tests that kill a mutant and leave the suite green.
7. The skill re grades and attaches the new report to the Alan task.
8. A human reviews the diff. The agent does not approve or merge.

## What the event allows

The public event page states these rules:

| Rule | Meaning for this project |
| --- | --- |
| Solo | One builder. Do not submit a team entry. |
| Open source repo | The GitHub repository must be public and open source. MIT is the current license. |
| Alan + open models | The product must use Alan and open source models. The repair path must not depend on a frontier model API. |
| No frontier models | Do not build the core product around a closed frontier model. Use an open model provider for repair. |
| X account needed | The submission includes an X post with a 1 to 3 minute demo. |
| Working link | The project must be usable, not only a source dump. The public repo and a working quickstart are the minimum. |
| Public GitHub repo | The code must be public. |
| $20 open source model credits | Use them for the repair path. Ask the Discord which provider and key format. |

The safe boundaries for the build:

- Allowed: Alan, open source models, open source libraries, your own code, public repositories with compatible licenses, GitHub, and X.
- Not allowed: a team entry, a closed source submission, a product that does not use Alan, or a demo whose core value depends on a frontier model.
- Out of scope for 24 hours: a hosted marketplace plugin, a remote MCP server, a web upload product, and full repository mutation by default.

If a rule is unclear, ask in the OpenFire Discord before spending build time. The event page is the authority, not this summary.

## What exists today

Phase 0 is complete. The Phase 1 deterministic engine is implemented and its local acceptance gates pass. Phase 2 reporting and CI gating, Phase 3 verified repair, and the Alan workflow remain planned.

| Area | Status | Where |
| --- | --- | --- |
| Product and architecture docs | Complete draft | `docs/BLUEPRINT.md` |
| Phase plan and cut lines | Complete | `docs/BUILD_PLAN.md` |
| Research and positioning | Complete | `docs/CROSS_RESEARCH.md` |
| Evaluation design | Complete | `docs/EVAL.md` |
| Build and evidence method | Complete | `docs/METHODOLOGY.md` |
| Alan, CI, and local flows | Complete draft | `docs/WORKFLOW.md` |
| Agent skill | Drafted | `skills/testproof/SKILL.md` |
| Weak demonstration fixture | Working | `fixtures/shop/` |
| CLI version, diff, and grade commands | Working | `src/testproof/cli.py` |
| Diff resolver | Working, worktree and commit modes | `src/testproof/diff.py` |
| Unit tests | 68 passing at Phase 1 checkpoint | `tests/` |
| CI | Lint, types, tests, coverage, security, build | `.github/workflows/ci.yml` |
| Mutation engine | Implemented and fixture verified | `src/testproof/engine.py` |
| Sandbox and test runner | Implemented and tested | `src/testproof/sandbox.py`, `src/testproof/runner.py` |
| Score and JSON report | Implemented | `src/testproof/models.py`, `src/testproof/report.py` |
| Markdown report and threshold | Not built | Phase 2 |
| GitHub Action | Not built | Phase 2 |
| Model client and verifier | Not built | Phase 3 |
| Benchmark and demo video | Not built | Phase 5 |
| Static report viewer | Not built | Phase 5, optional |
| Remote MCP server and marketplace plugin | Roadmap | After the hackathon |

The project has a local commit history and a private GitHub repository at `https://github.com/tsvlgd/testproof`. The private setting reflects the user's current preference. Change it to public only if a release or event submission requires it.

## Phase map

| Phase | Goal | Main output | Gate | Status |
| --- | --- | --- | --- | --- |
| 0 Foundation | A repo that runs, a weak fixture, and a diff resolver | CLI, diff resolver, tests, fixture, CI | `make check` green | Complete after the diff fix |
| 1 Deterministic engine | Grade Python changes and produce a reproducible score | Adapter, sandbox, runner, engine, score, JSON | Same input, same score | Local acceptance gates pass; ready for checkpoint commit |
| 2 Report and CI gate | Turn the score into a pull request gate | Markdown, threshold, exit codes, GitHub Action | Pull request fails below threshold | Planned |
| 3 Verified repair | Let an open model write missing tests and prove each kill | Model client, prompt, verifier, apply | Score rises with verified tests | Planned |
| 4 Alan skill and workflow | Make the tool usable in a real Alan session | Skill, automation recipe, artifact, recording | Skill runs end to end | Planned |
| 5 Benchmark and demo | Prove the tool works beyond the fixture | Corpus, metrics, results, video | Before and after are measurable | Planned |
| 6 Hardening and submission | A fresh clone works and the submission is complete | Errors, release, public repo, X post | Fresh clone works | Planned |

The build plan assumes a 31 hour window from Monday 1 PM IST to Tuesday 8 PM IST. If the clock is already behind, use the cut lines in `docs/BUILD_PLAN.md`. Do not lower the quality bar. The first cut is usually the optional viewer, the second is the second language adapter, and the third is the marketplace plugin.

## Repository map

| Path | What it is | Read it when |
| --- | --- | --- |
| `README.md` | Short product summary and status | First |
| `docs/ORIENTATION.md` | This map | Second |
| `CONSTRAINTS.md` | The quality bar with numbers | Before writing code |
| `docs/BLUEPRINT.md` | Product judgment, architecture, data model, decisions, risks | Before changing the design |
| `docs/BUILD_PLAN.md` | Phase goals, acceptance commands, checkpoints, cut lines | Before starting a phase |
| `docs/METHODOLOGY.md` | Build loop, measurement rules, repair rules, review protocol | Before measuring or repairing |
| `docs/EVAL.md` | Benchmark design and falsification criteria | Before claiming the tool works |
| `docs/WORKFLOW.md` | Alan, GitHub, and local flows | Before wiring an integration |
| `docs/CROSS_RESEARCH.md` | Evidence and competitive positioning | Before the pitch |
| `docs/GLOSSARY.md` | Terms used across the docs | When a word is unclear |
| `docs/INIT_PROMPT.md` | Paste ready prompt for a fresh coding session | When starting a new agent session |
| `AGENTS.md` | Rules for agents working in this repo | Before any agent edit |
| `skills/testproof/SKILL.md` | The portable skill | Before the Alan demo |
| `src/testproof/cli.py` | Command line entry point | Before adding a command |
| `src/testproof/diff.py` | Change set resolver | Before grading a diff |
| `fixtures/shop/` | Deliberately weak suite | Before the first demo |
| `diagrams/` | Mermaid sources and Excalidraw canvas | Before the architecture walkthrough |
| `.github/workflows/` | CI and the manual diff preview | Before the pull request gate |

## The diff command, corrected

The first version of the diff command had a semantics bug. It always compared two commits. The command `testproof diff --base HEAD~1` ran the equivalent of `git diff HEAD~1...HEAD`, so it showed the last commit and ignored the working tree. That is why it reported only `README.md` while `git status` showed `app/main.py`, `compose.yaml`, `CLAUDE.md`, and `CODEBASE_AUDIT.md`.

The corrected behavior is:

| Command | What it compares | When to use |
| --- | --- | --- |
| `testproof diff` | `HEAD` to the working tree, including staged and untracked files | Local check before a commit. This is the closest to `git status`. |
| `testproof diff --base HEAD~1` | The merge base of `HEAD~1` and `HEAD` to the working tree | Everything since the previous commit, including that commit and local edits. |
| `testproof diff --base origin/main --head HEAD` | The merge base of `origin/main` and `HEAD` to `HEAD` | The committed pull request diff used by CI. |

The output now names both sides:

```text
Base: HEAD
Target: working tree
Changed files: 4
  added     CLAUDE.md  lines 1-145
  added     CODEBASE_AUDIT.md  lines 1-60
  modified  app/main.py  lines 33-37
  modified  compose.yaml  lines 17
Changed lines: 211
```

In JSON, the worktree target is the string `WORKTREE`. A commit target is the revision name.

The tool is not a replacement for `git status`. `git status` shows the state of the working tree. TestProof resolves a change set from a base to a target. The base decides what belongs in that change set. Use `HEAD` for uncommitted work, `HEAD~1` for the last commit plus uncommitted work, and `origin/main` with `--head HEAD` for a pull request.

The resolver also includes untracked text files, respects `.gitignore`, skips binary and oversized files from line ranges, and uses the merge base so a branch does not inherit unrelated commits from main.

## Current state and next step

Phase 0 is complete. Phase 1's local acceptance gates now pass:

```text
68 tests passing
87.93 percent coverage
make check-full green
fixture grade: 8 killed, 1 survived, 88.9 percent
repeated fixture runs: same score and mutant IDs
```

The fixture acceptance command is:

```bash
uv run testproof grade --repo fixtures/shop --all --test-cmd "uv run pytest -q" --format json
```

`fixtures/shop` is a tiny example repository containing shipping code and deliberately weak tests. It has no Git history of its own, so `--all` asks the engine to grade every supported Python file there instead of asking Git for changed lines. For a normal Git repository, omit `--all`: TestProof resolves the Git diff and grades only changed Python lines by default. `--all` can also be used explicitly for a full repository audit, but that can be slow and is never the default.

The known survivor is the boundary mutation `>=` to `>` on `shipping.py:6`. That means the existing tests miss the exact free shipping threshold. It is useful fixture evidence, not proof that TestProof catches every real bug.

Next is Phase 2: Markdown reporting, threshold handling and exit codes, and the GitHub Actions pull request gate. Then Phase 3 builds verified repair with an open model, followed by completing the agent workflow, benchmark, and release work. See `docs/BUILD_PLAN.md` for the gates and checkpoints.

## Reading order

1. `README.md`
2. `docs/ORIENTATION.md`
3. `CONSTRAINTS.md`
4. `docs/BLUEPRINT.md`
5. `docs/BUILD_PLAN.md`
6. `docs/METHODOLOGY.md`
7. `docs/EVAL.md`
8. `docs/WORKFLOW.md`
9. `docs/CROSS_RESEARCH.md`
10. `skills/testproof/SKILL.md`
11. `docs/INIT_PROMPT.md`

Do not read all of it in one sitting. Read the first four, then start Phase 1 with the init prompt. Use the rest as reference when a specific question comes up.

## Pitch

If someone asks what you built, say:

> TestProof is an open source test strength gate for AI written code. It mutates only the lines a pull request changed, runs the project's own tests, and reports the bugs the suite misses. An open source model writes the missing tests, and a deterministic verifier keeps only the tests that pass on the original code and fail on the mutant. It ships as a CLI, an Alan skill, and a GitHub Action, and every surface reads the same report.

Do not say:

> TestProof proves your code is correct.

A high mutation score is evidence that the tests catch planted bugs in the changed lines. It is not proof of correctness. The report says this, and the pitch should say it too.
