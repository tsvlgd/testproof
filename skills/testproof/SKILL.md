---
name: testproof
description: Grade whether a test suite catches bugs with diff scoped mutation testing, then write missing tests with deterministic templates and an open source model fallback, verifying each kill. Use when tests pass but test strength is unknown, when reviewing AI written code, or before claiming a task is done.
license: MIT
compatibility: Requires git, Python 3.11 or newer, uv, and a project test command.
metadata:
 version: "0.2.0"
 author: TestProof contributors
---

# TestProof

Use this skill when a test suite is green and the question is whether it would catch a real bug. TestProof mutates only the lines a change touched, runs the project's own test command, and reports the mutants that survived. Repair runs deterministic templates first: a probe executes the target function on the original and the mutant, and only observed differences become assertions. An open source model is a fallback for survivors the templates cannot handle. A deterministic verifier keeps a test only when it passes on the original code, fails on the mutant, and leaves the full suite green.

## Install

Copy the `testproof` folder into the skills directory for your agent. The common paths are:

- Alan: open the repository as the workspace, or use the Alan skill install flow on `skills/testproof/`
- Claude Code: `~/.claude/skills/testproof/`
- Codex CLI: `~/.codex/skills/testproof/`
- Cursor: `~/.cursor/skills/testproof/`
- Gemini CLI: `~/.gemini/skills/testproof/`
- OpenCode: `~/.config/opencode/skills/testproof/`
- Cross agent: `~/.agents/skills/testproof/`

The folder name must match the `name` field. Restart the agent if it does not list the skill.

## When to use

- A pull request has green tests and high coverage, and a reviewer needs evidence of test strength.
- An agent is about to claim a coding task is done and the only evidence is a passing suite.
- A change touches a boundary, a boolean rule, an arithmetic path, or a return value.
- A team wants a CI gate that measures detection, not execution.

Do not use this skill as a substitute for running the suite, for a security review, or for a correctness proof. Mutation score is a proxy.

## Preconditions

- The working directory is a git repository with the base revision available.
- The project has a test command that runs the affected suite and exits nonzero on failure.
- The test command passes on the unmodified code. A broken baseline is not a score.
- The installed `testproof` version supports the `grade` command. If it does not, stop and report that the engine phase is not complete.

## Procedure

1. Establish the repository, the base revision, the test command, and the threshold. Prefer the values in project documentation. Do not invent a threshold.
2. Grade the diff:

```bash
testproof grade \
  --repo . \
  --base origin/main \
  --test-cmd "pytest -q" \
  --threshold 80 \
  --format json \
  --output .testproof/report.json
```

Add `--head HEAD` when the target is a committed pull request and you want to exclude uncommitted files. Omit it when the task is still in progress and the working tree is the change under test.

3. Read the JSON report, not the terminal summary. Check `summary.partial`, `summary.confidence`, `summary.invalid`, and `summary.timeout` before you interpret the score.
4. If the score is at or above the threshold, attach the report as evidence and stop. State the score and the caveat.
5. If the score is below the threshold, list the survivors with file, line, operator, original text, and replacement text. Rank boundary and boolean survivors first.
6. Run repair in dry run mode:

```bash
testproof repair \
  --repo . \
  --report .testproof/report.json \
  --test-cmd "pytest -q" \
  --dry-run
```

Repair runs deterministic templates first and does not need a model key. It reports kept tests, rejected candidates with reasons, likely equivalent mutants, and the number of model calls. The model is a fallback for survivors that templates cannot handle.

7. Inspect every proposed test. Reject a test that changes production code, has no assertion, or only asserts a value copied from the mutant.
8. Apply the verified tests:

```bash
testproof repair \
  --repo . \
  --report .testproof/report.json \
  --test-cmd "pytest -q" \
  --apply
```

9. Re grade with the same base, test command, threshold, and mutant cap.
10. Report the before score, the after score, the tests kept, the tests rejected with reasons, the likely equivalent mutants, and the survivors that remain. Attach the final report to the task.

## Evidence contract

The report is the source of truth. Every claim in the final message must come from it.

| Field | Meaning |
| --- | --- |
| `summary.score` | Killed divided by killed plus survived |
| `summary.partial` | True when the run stopped before all discovered mutants ran |
| `summary.confidence` | High, medium, or low, based on coverage of the mutant set and noise |
| `summary.invalid` | Mutants that broke parsing or compilation and were excluded |
| `summary.timeout` | Mutants that exceeded the per mutant budget |
| `files[].mutants[].status` | Killed, survived, invalid, timeout, or skipped |
| `files[].mutants[].suggested_test` | A proposed test, not yet proof |

A test counts as kept only when the report contains evidence that it passes on the original code, fails on the mutant, and leaves the full suite green.

## Guardrails

- Never edit production code to raise the score.
- Never keep a proposed test that the verifier did not confirm.
- Never hide invalid, timed out, or suspected equivalent mutants. Report the counts.
- Never lower the threshold to make a change pass. Ask the human owner.
- Never approve or merge a pull request. A human makes that decision.
- Never claim that a high score proves correctness. The correct claim is that the tests detect the planted bugs in the changed lines.
- Never send secrets, environment files, or unrelated repository content to the model. Repair prompts contain only the code under test, the tests, and the mutant.

## Failure handling

| Failure | Action |
| --- | --- |
| Not a git repository | Stop and ask for the repository root |
| Base revision missing | Fetch the base branch and retry once |
| Baseline test failure | Stop. Fix the suite before grading |
| No mutation points | Report that the changed lines had no supported operators |
| Partial score | Report the sample size and the reason. Do not present it as a complete score |
| Model key missing | Template repair still runs. Report that the model fallback is unavailable. Do not fake a test |
| Likely equivalent | Keep the survivor in the report and label it. Do not invent a test that cannot distinguish the mutant |
| Model output invalid | Record the rejection reason and continue |
| Candidate fails on the original | Reject it and record the reason |
| Candidate passes on the mutant | Reject it and record the reason |
| Time budget reached | Report the partial result and the remaining mutants |

## Final response shape

```markdown
## TestProof result

- Repository: <path>
- Base: <ref>
- Test command: <command>
- Score before: <n> percent
- Score after: <n> percent
- Threshold: <n> percent
- Status: pass or fail
- Partial: yes or no
- Confidence: high, medium, or low
- Likely equivalent: <n>
- Model calls: <n>

### Verified tests kept

| File | Line | Mutant | Test | Evidence |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | passes on original, fails on mutant, full suite green |

### Survivors remaining

| File | Line | Original | Replacement | Reason |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |

### What this means

<one paragraph tied to the report>

### What this does not mean

A high score does not prove correctness. It means the tests catch the planted bugs in the changed lines.
```
