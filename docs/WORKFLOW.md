# Workflow

This document describes how TestProof fits into Alan, GitHub CI, and a local developer loop. It is the operating manual for the demo and for real use.

## 1. The three entry points

| Entry point | Who starts it | What it does | What it proves |
| --- | --- | --- | --- |
| GitHub Action | A pull request event | Grades the diff, posts a check and a comment | The gate works without a human |
| Alan skill | An Alan agent or a human in a session | Grades, repairs, re grades, attaches an artifact | The agent workflow works end to end |
| Local CLI | A developer | Grades and repairs before pushing | The tool is usable in the tight loop |

All three use the same core and the same report schema.

## 2. GitHub Action flow

### 2.1 Trigger

```yaml
on:
  pull_request:
    branches: [main]
```

### 2.2 Steps

1. Check out the repository with full history so the base ref resolves.
2. Install `uv`.
3. Run `testproof grade` against the base branch.
4. Write `testproof.json` and `testproof.md`.
5. Post a check run with the score and the threshold.
6. Post a pull request comment with the score, the survivors, and the caveat.
7. Upload the report as an artifact.
8. Fail the job when the score is below the threshold.

### 2.3 Example workflow

```yaml
name: TestProof

on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write
  checks: write

jobs:
  testproof:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v5
      - name: Grade test strength
        run: |
          uvx testproof grade \
            --base "origin/${{ github.base_ref }}" \
            --head HEAD \
            --test-cmd "pytest -q" \
            --threshold 80 \
            --format json \
            --output testproof.json
      - name: Render markdown
        if: always()
        run: uvx testproof report --input testproof.json --format markdown --output testproof.md
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: testproof-report
          path: |
            testproof.json
            testproof.md
```

The comment step is intentionally separate. It can use `actions/github-script` to read `testproof.md` and create or update a comment. Keep the comment idempotent by searching for a marker such as `<!-- testproof-report -->` and updating the existing comment instead of creating a new one.

### 2.4 What the reviewer sees

```markdown
## TestProof: 62 percent

Threshold: 80 percent. Status: failed.

| File | Score | Killed | Survived | Invalid |
| --- | --- | --- | --- | --- |
| shop/shipping.py | 62 | 5 | 3 | 1 |

### Survivors

1. `shop/shipping.py:2` changed `>=` to `>`. No test checks an order of exactly 50.
2. `shop/shipping.py:4` changed `return 5` to `return None`. No test checks the paid path.

### What this means

The tests run every line, but three planted bugs survive. Passing tests are not the same as strong tests.

### What this does not mean

A high score does not prove correctness. It means the tests catch the planted bugs in the changed lines.
```

## 3. Alan flow

### 3.1 Where the skill lives

```text
skills/testproof/SKILL.md
```

Install it in one of these ways:

- Alan: use the skill install flow for your workspace, or copy the folder into the skills directory the Alan desktop app reads.
- Claude Code: `~/.claude/skills/testproof/`
- Codex CLI: `~/.codex/skills/testproof/`
- OpenCode: `~/.config/opencode/skills/testproof/`
- Cross agent: `~/.agents/skills/testproof/`

The skill follows the Agent Skills specification. The `name` matches the directory and the description says when to use it.

### 3.2 Skill behavior

The skill instructs the agent to:

1. Identify the repository, the base ref, the test command, and the threshold.
2. Run `testproof grade`.
3. Read the JSON report.
4. If the score passes, attach the report as an Alan test report artifact and stop.
5. If the score fails, list the survivors with file, line, original, and replacement.
6. Run `testproof repair`.
7. Keep only the tests the verifier confirms.
8. Re run `testproof grade`.
9. Attach the new report and report the before and after score.
10. State the remaining survivors and why they were not fixed.

### 3.3 Alan automation recipe

1. Open Alan.
2. Create an automation.
3. Choose the GitHub trigger. Start with "Review Requested" if available, or a pull request opened event.
4. Set the instructions:

```text
When a pull request is opened or review is requested, run the testproof skill.

1. Grade the pull request diff with the repository's test command.
2. Attach the JSON and Markdown report as a test report artifact.
3. If the score is below the threshold, repair the survivors and re grade.
4. Post the before and after score as a comment on the pull request.
5. Do not approve or merge. Leave the decision to a human.
```

5. Select the repository and the environment.
6. Save and run once manually to verify.
7. Turn it on for pull request events.

### 3.4 Artifact template

```markdown
# TestProof Report

Task: <task id>
Pull request: <number>
Base: <ref>
Head: <sha>
Test command: <command>

## Result

- Score before: <n> percent
- Score after: <n> percent
- Threshold: <n> percent
- Status: pass or fail
- Partial: yes or no
- Confidence: high, medium, or low

## Survivors fixed

| File | Line | Original | Replacement | Test added | Verified |
| --- | --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... | yes |

## Survivors remaining

| File | Line | Original | Replacement | Reason |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |

## What this means

<one paragraph>

## What this does not mean

A high mutation score does not prove correctness. It means the tests catch the planted bugs in the changed lines.
```

## 4. Local flow

### 4.1 First run

```bash
uvx testproof grade \
  --repo . \
  --base origin/main \
  --test-cmd "pytest -q" \
  --threshold 80 \
  --format json \
  --output .testproof/report.json
```

### 4.2 Read the terminal summary

```text
TestProof 0.1.0
Repository: /home/user/shop
Base: origin/main
Test command: pytest -q
Mutants: 9 discovered, 9 run, 1 invalid
Score: 62.5 percent (threshold 80) FAILED
Confidence: high

Survivors:
  shop/shipping.py:2  >= -> >    no test checks order_total == 50
  shop/shipping.py:4  return 5 -> return None    no test checks the paid path
  shop/shipping.py:7  and -> or    no test checks the member and total combination
```

### 4.3 Repair

```bash
uvx testproof repair \
  --repo . \
  --report .testproof/report.json \
  --test-cmd "pytest -q" \
  --apply
```

The tool prints a diff of the tests it added and a verification record for each one.

### 4.4 Re grade

```bash
uvx testproof grade \
  --repo . \
  --base origin/main \
  --test-cmd "pytest -q" \
  --threshold 80
```

## 5. Failure handling

| Failure | Message | Action |
| --- | --- | --- |
| No git repository | "TestProof needs a git repository" | Run from the repo root or pass `--repo` |
| No changed files | "No changed Python files against the base ref" | Check the base ref, or pass `--all` |
| Baseline test failure | "The test command fails on the unmodified code" | Fix the suite before grading |
| No mutants discovered | "No mutation points found on the changed lines" | Check the adapter and the diff scope |
| Time budget reached | "Partial score: 34 of 50 mutants run" | Increase the budget or reduce the cap |
| Missing model key | "Set MODEL_API_KEY to use repair" | Export the key or use `--dry-run` |
| Model returns invalid test | "Candidate rejected: does not parse" | Record the rejection and continue |
| Candidate passes on mutant | "Candidate rejected: does not kill the mutant" | Try the next survivor |
| Candidate fails on original | "Candidate rejected: fails on the original code" | Try the next survivor |

## 6. Why not a marketplace plugin in 24 hours

Alan marketplace plugins require a remote HTTPS MCP server. Alan does not run stdio servers yet. A remote server that executes arbitrary test suites needs hosting, sandboxing, authentication, rate limiting, and abuse protection. That is a multi day build, not a 24 hour build.

The skill plus the GitHub Action gives the same user outcome without the hosting risk. The plugin is the roadmap path once the core is stable.

## 7. Fallback if Alan is unavailable

1. Record the skill running in OpenCode or Claude Code.
2. Show the Alan automation recipe in the video as a configuration step.
3. Keep the claim precise: "the skill works across SKILL.md compatible agents, and the Alan automation wires it into the pull request flow."
4. Do not claim a live Alan integration that was not recorded.

## 8. Demo sequence

1. Open the fixture. Show the weak test and the green suite.
2. Run coverage. Show 100 percent line coverage.
3. Run TestProof. Show the score below 100 and the survivor at the boundary.
4. Run repair. Show the verified test and the rejection record.
5. Re grade. Show the score above the threshold.
6. Open the pull request. Show the check turn green.
7. Open the Alan session. Show the report artifact.
8. Show the benchmark table with the before and after.

This sequence tells the whole story in under 3 minutes.
