# Glossary

**Adapter.** A module that teaches TestProof how to parse and mutate one language. The adapter finds mutation points, applies a mutation to source text, and validates the result.

**Baseline.** The test run on the unmodified code. If the baseline fails, the grade aborts. A broken suite is not a score.

**Bug detection rate.** The fraction of known bug versions that a test suite fails on. This is the real world signal that complements mutation score.

**Changed lines.** The lines a pull request adds or modifies, resolved from a git diff.

**Change set.** The files and lines between a base and a target. The target can be a commit or the working tree.

**Confidence.** A label on the report that says how complete the run was. High means all discovered mutants ran with few invalid results. Medium means partial or moderately noisy. Low means the sample is too small to trust.

**Diff scope.** The default mode that mutates only changed lines. It keeps the run fast enough for CI.

**Equivalent mutant.** A mutation that changes the source but not the behavior. Equivalent mutants survive forever and depress the score. They are marked as suspected equivalents and can be excluded with a recorded reason.

**Invalid mutant.** A mutation that produces code that cannot be parsed or compiled. It is excluded from the denominator and reported separately.

**Killed mutant.** A mutant that makes at least one test fail. The tests detected the planted bug.

**Mutant.** A copy of the code with one small change that simulates a bug.

**Mutation operator.** The rule that produces a mutant, such as changing `>=` to `>` or `and` to `or`.

**Mutation point.** The exact source location and replacement that define one possible mutant.

**Mutation score.** Killed divided by killed plus survived. The primary strength metric. It is a proxy, not proof of correctness.

**Partial score.** A score computed from a subset of discovered mutants because the time budget ran out. The report must mark it and state the reason.

**Sandbox.** A temporary copy of the repository where mutants run. The working tree is never modified.

**Survived mutant.** A mutant that leaves every test passing. The tests did not detect the planted bug.

**Test strength.** The degree to which a test suite detects bugs. Mutation score and bug detection rate are two measures of it.

**Verified repair.** A proposed test is kept only after it passes on the original code, fails on the mutant, and leaves the full suite green. The model proposes, the engine verifies.

**Working tree hash.** A hash of the repository files before and after a grade. It is used to prove that the engine did not mutate the real working tree.

**Working tree target.** The diff mode where the resolver compares the merge base to the files on disk, including staged and untracked files. JSON marks it as `WORKTREE`.
