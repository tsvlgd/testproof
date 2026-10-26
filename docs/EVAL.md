# Evaluation Design

This document defines how TestProof proves that it works. It follows the eval engineering discipline: one clear task, independent evidence, a verifier that cannot be gamed, and a report that states what the numbers do and do not mean.

## 1. The claim under test

Claim: TestProof raises the strength of an existing test suite, measured by mutation score and by real bug detection, without breaking the suite or modifying production code.

This claim has two parts. A high mutation score alone is not enough. The 2026 ISSTA study shows that mutation score can stop being a reliable indicator when the code under test may already be buggy. So the evaluation measures both mutation score and real bug detection.

## 2. What is measured

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Mutation score before | Killed divided by killed plus survived, on the original test suite | The baseline strength |
| Mutation score after | The same formula after verified repair | The primary effect |
| Bug detection before | Fraction of known bug versions that the original suite fails on | Real world validity |
| Bug detection after | The same fraction after repair | Real world validity of the repair |
| Repair acceptance rate | Kept tests divided by proposed tests | Whether the model is useful or noisy |
| False kill rate | Tests that fail on the original code, divided by proposed tests | Whether the verifier rejects bad tests |
| Runtime | Wall clock seconds per module and per run | Whether the tool is usable in CI |
| Partial rate | Runs that hit the time budget, divided by runs | Whether the budget is realistic |
| Flake rate | Runs with a different score on the same input, divided by repeated runs | Determinism |

## 3. Corpus design

The corpus has two sets.

### 3.1 Set A: bug free code with weak tests

Purpose: measure mutation score improvement.

Each module has:

- A Python module with functions that contain boundaries, booleans, arithmetic, and returns.
- A weak test file that has high line coverage but misses boundary and logic cases.
- A known set of mutation points.

Target size: 10 to 15 modules. Keep each module under 80 lines so a full mutate run fits the time budget.

### 3.2 Set B: code with known bugs

Purpose: measure real bug detection.

Each module has:

- A correct version.
- One or more buggy versions, each with a single realistic bug.
- A test file.

The test suite should pass on the correct version and fail on the buggy version, if the tests are strong enough.

Target size: 10 to 15 bugs across the same modules.

### 3.3 Source of the corpus

Options, in order of preference:

1. Small public Python utility repositories with permissive licenses and existing tests.
2. Synthetic modules written for the benchmark, with realistic boundaries and logic.
3. A mix of both.

Do not copy code with an unclear license. Record the source and the license for every module in `benchmark/corpus/SOURCES.md`.

## 4. Conditions

Run each module under these conditions:

| Arm | Test suite | Repair |
| --- | --- | --- |
| A0 | Original weak tests | No |
| A1 | Original weak tests plus verified repair | Yes |
| A2 | Human written strong tests, if available | No |

A2 is the upper bound. A1 is the product. A0 is the baseline.

If A2 is not available, report A0 and A1 only and say so.

## 5. Metrics and formulas

```text
mutation_score = killed / (killed + survived)
bug_detection  = bugs_detected / bugs_total
repair_acceptance = kept_tests / proposed_tests
false_kill_rate = tests_failing_on_original / proposed_tests
flake_rate = runs_with_different_score / repeated_runs
```

Excluded from the mutation score denominator:

- Invalid mutants.
- Timed out mutants.
- Skipped mutants.
- Suspected equivalent mutants, but only when the report marks them and the run records the exclusion.

Always report the excluded counts next to the score. A score without its denominator is not evidence.

## 6. Verifier and guardrails

A proposed test is kept only if all of these are true:

1. It passes on the original code.
2. It fails on the mutant.
3. The full suite passes on the original code with the new test.
4. It contains at least one assertion.
5. It does not modify production code.
6. It does not assert on a hardcoded output that only the mutant produces.
7. It does not import or call a private helper in a way that couples the test to the implementation.

The verifier records the evidence for each condition:

```json
{
  "test_id": "t-001",
  "mutant_id": "m-001",
  "passes_on_original": true,
  "fails_on_mutant": true,
  "full_suite_passes": true,
  "has_assertion": true,
  "touches_production_code": false,
  "decision": "kept",
  "reason": "killed mutant m-001 and passed the full suite"
}
```

A rejected test is not deleted silently. It is recorded with a reason so the acceptance rate is honest.

## 7. Run protocol

1. Freeze the corpus and record the git commit.
2. Run A0 three times on each module. Record the score and the flake rate.
3. Run A1 three times on each module. Record the score, the acceptance rate, the false kill rate, and the runtime.
4. Run the bug detection set on A0 and A1.
5. Store the raw JSON reports in `benchmark/runs/`.
6. Generate `benchmark/results.md` from the raw reports, not by hand.
7. Review every kept test manually. Record any test that looks overfit.

## 8. Reporting template

```markdown
# Benchmark Results

Commit: <sha>
Date: <date>
Corpus: <n> modules, <m> bugs
Model: <provider and model>
Time budget: <seconds>
Mutant cap: <n>

| Arm | Mutation score | Bug detection | Repair acceptance | False kill | Runtime |
| --- | --- | --- | --- | --- | --- |
| A0 weak tests | 58% | 40% | not applicable | not applicable | 12s |
| A1 verified repair | 86% | 80% | 62% | 9% | 74s |
| A2 human tests | 91% | 90% | not applicable | not applicable | 14s |

## What this means

The repair raises the mutation score by 28 points and the bug detection rate by 40 points. It does not reach the human baseline. Two modules hit the time budget and are marked partial.

## What this does not mean

A high mutation score does not prove correctness. The score is a proxy. The bug detection set is the stronger signal.
```

The numbers in the template are placeholders. Replace them with the real run.

## 9. Threats to validity

| Threat | Effect | Mitigation |
| --- | --- | --- |
| Small corpus | Results may not generalize | Report the corpus size and the selection method. Do not claim generality |
| Synthetic bugs | Bugs may be easier than real bugs | Include at least five bugs from real commits or real issues |
| Model overfits the mutant | The test kills the mutant but is not a good test | Human review every kept test. Require a pass on the original and a full suite run |
| Equivalent mutants | Score is depressed by unfixable survivors | Mark suspected equivalents and report the excluded count |
| Time budget | Partial runs bias the score | Report partial rate and confidence next to the score |
| Test order dependence | Flaky results | Run the full suite on the original after each kept test. Use a fixed seed |
| Prompt leakage | The model sees the existing tests and copies them | Include the tests in the prompt only when needed. Record the prompt version |
| Selection bias | Easy modules are overrepresented | Document how modules were chosen. Include at least three modules with tricky boundaries |

## 10. Acceptance criteria for the eval

The eval is complete when:

1. The corpus has at least 10 modules and at least 10 known bugs.
2. A0 and A1 are run three times each.
3. The raw reports are committed.
4. The results table is generated from the raw reports.
5. Every kept test is reviewed and the review is recorded.
6. The reporting template includes the caveat about mutation score.
7. The README links to the results.

## 11. What would falsify the claim

The claim is false if any of these hold after the run:

- Mutation score does not rise by at least 10 points on average.
- Bug detection does not rise by at least 10 points on average.
- Repair acceptance is below 30 percent.
- False kill rate is above 30 percent.
- Flake rate is above 5 percent.
- Runtime exceeds the CI budget on more than half the modules.

If the claim is falsified, report it honestly. A negative result with a clear explanation is better than a demo that hides the failure.
