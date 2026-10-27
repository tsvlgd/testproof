# Repair Prompt

Repair is template first. The model prompt is used only when the deterministic probe cannot find an input that distinguishes the original code from the mutant, or when the caller passes `--force-model`.

## Goal

Write one test that:

1. Passes on the original code.
2. Fails on the mutated code.
3. Passes when added to the full suite.
4. Uses the existing test framework and imports.
5. Contains at least one assertion.
6. Does not modify production code.

## Reasoning structure

The prompt asks the model to work in three steps before writing code:

1. Read the mutation. Compare the original token with the replacement token.
2. Find the distinguishing input. Prefer a boundary value, an empty or negative value, a single condition, or a value that exercises the changed constant.
3. Write the test. Use the existing framework and imports.

A worked example is included: a `>=` to `>` shipping fee mutation is killed by `shipping_fee(50) == 0`.

## Mutation hints

The prompt includes a short hint for the operator family:

| Operator | Hint |
| --- | --- |
| comparison | Find the exact boundary where the original and the mutant disagree |
| boolean | Find an input where only one part of the condition is true |
| arithmetic | Find an input where the two operations produce different results |
| return | Reach the return statement and show that the original does not return None |
| constant | Reach the changed constant and show the original result |

## Deterministic feedback

When templates fail, the prompt includes the probe note and every template rejection reason. This tells the model what was already tried and why it failed. The model does not see a hidden score and cannot mark its own test as kept.

## Input format

- File path
- Line number and operator family
- Original and replacement token
- Mutated line
- Enclosing function source
- Existing tests
- Deterministic probe feedback when available

## Output contract

The model returns exactly one fenced Python code block with the complete test and its imports. Extension code strips fences, keeps the first test function, and rejects a response with no test function.

## Verification

The verifier is unchanged and is the only authority on whether a test is kept:

1. Write the candidate to a temporary test file in the sandbox.
2. Run the test command on the original code. It must pass.
3. Apply the mutant. Run the test command. It must fail.
4. Restore the original. Run the full suite. It must pass.
5. Keep only if all three hold.

A rejected test is recorded with a reason. A passing model response is not evidence until the verifier confirms it.
