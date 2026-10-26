# Methodology

This is the operating method for TestProof. It explains how the product is built, how the numbers are kept honest, and where a human stays in control.

## 1. Contract first

Write the report schema, the adapter protocol, and the command surface before the engine. Every later integration reads the same contract:

- The CLI writes the JSON report.
- The GitHub Action reads the JSON report.
- The skill reads the JSON report.
- The future MCP server returns the JSON report.

If an integration needs a new field, the schema version changes. Terminal output is never the contract.

## 2. Trust ladder

Build and prove the product in this order:

1. Deterministic measurement. Mutant discovery, sandbox execution, classification, and score. This must work before any model is called.
2. Verified repair. The model proposes a test. The engine confirms the kill.
3. Evidence. The benchmark measures mutation score and real bug detection before and after repair.
4. Integration. The skill, the GitHub Action, and the Alan workflow use the same engine.

Do not skip a rung. A repair loop on top of an unreliable score is a demo, not a product.

## 3. Build loop

Each phase follows the same cycle:

1. Restate the goal and the acceptance criteria.
2. Write the failing test for the next behavior.
3. Implement the smallest change that passes.
4. Run `make check`.
5. Stop at the checkpoint. Review the diff against `CONSTRAINTS.md`.
6. Cut scope at the cut line if the budget is gone. Never lower the quality bar.
7. Commit with a conventional message. Start the next phase.

A phase is done only when its acceptance command runs and its output is pasted into the checkpoint note.

## 4. Measurement rules

- The score is killed divided by killed plus survived.
- Invalid, timed out, and skipped mutants are excluded from the denominator and reported separately.
- The baseline test run must pass. A broken suite is not a score.
- The same repository, diff, test command, adapter version, and seed must produce the same mutant ids and score.
- A partial run is marked as partial, with the reason and the number of mutants that did not run.
- No model call happens in discovery, execution, classification, or scoring.

The score is a proxy for detection. It is not proof of correctness. The benchmark must also measure real bug detection.

## 5. Repair rules

A proposed test is kept only when all of these are true:

1. It passes on the original code.
2. It fails on the mutant.
3. The full suite passes on the original code with the new test.
4. It contains at least one assertion.
5. It does not modify production code.

Reject a test that has no assertion, that only copies the mutant output, or that couples itself to a private helper. Record every rejection with a reason. The acceptance rate is part of the evidence, not a number to hide.

The model proposes. The verifier decides. A human reviews the diff before merge.

## 6. Review protocol

At each checkpoint, compare the diff against the quality bar. Look for:

- A threshold moved down.
- A test skipped or deleted.
- A new suppression comment without a reason.
- A stub that throws or returns a placeholder.
- A model call in the measurement path.
- A report field that exists in one surface and not another.
- A claim that the score proves correctness.

Tightening the bar should be quiet. Loosening it should be loud.

## 7. Falsification

A claim is not accepted because the demo looked good. The eval defines what would prove it wrong:

- Mutation score does not rise by at least 10 points on average.
- Bug detection does not rise by at least 10 points on average.
- Repair acceptance is below 30 percent.
- False kill rate is above 30 percent.
- Flake rate is above 5 percent.
- Runtime exceeds the CI budget on more than half the modules.

If the claim fails, report the negative result. A clear failure is better evidence than a hidden one.

## 8. Roles

- The human owns the threshold, the scope cuts, and the merge decision.
- The agent proposes code, tests, and explanations.
- The deterministic engine decides the status of a mutant.
- The verifier decides whether a proposed test is kept.
- CI and the benchmark provide the evidence.

This division is the product. It is also the reason the score can be trusted.

## 9. Why this fits Alan

Alan already runs checks on a change and returns evidence. TestProof adds the missing strength check without asking for a new workflow. The skill tells an Alan agent when to grade and how to read survivors. The GitHub Action gives the same gate to teams that do not use Alan. The marketplace plugin is a later step because it needs a hosted remote MCP server.

The order is deliberate: prove the engine, prove the repair, then widen the integration surface.
