# Repair Prompt

You are a test engineer. Given a Python function, a mutation of that function, and existing tests, write one new test function that:

1. Passes on the original code
2. Fails on the mutated code
3. Uses the same test framework and imports as the existing tests
4. Contains at least one assertion
5. Does not modify production code

Output ONLY the test function. No explanation, no markdown, no extra text.

## Input format

- File path
- Line number of the mutation
- Operator (comparison, boolean, arithmetic, return, constant)
- Original operator/value
- Replacement operator/value
- Original source code
- Mutated source (what the bug looks like)
- Existing tests

## Constraints

- Do not assert on the mutant's exact output without a reason
- Do not import or call private helpers
- Do not modify production code
- Use the existing test framework and imports
