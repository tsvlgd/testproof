# Demo Session

This is the Phase 4 recorded session. It runs the skill on a copy of `fixtures/shop`, shows the survivor, repairs it with deterministic templates, and re grades. The model is deliberately unavailable so the transcript proves that repair does not depend on a model key.

Total wall time: about 15 seconds for all four commands. The full session fits under the 2 minute Phase 4 limit.

## Setup

```bash
rm -rf /tmp/testproof-demo
cp -a fixtures/shop /tmp/testproof-demo

# Use a temporary home directory so no model config is found.
export HOME=/tmp/testproof-demo-home
mkdir -p "$HOME"
unset MODEL_API_KEY MODEL_NAME MODEL_MAX_TOKENS
```

The fixture is a tiny shop with deliberately weak tests. It has full line coverage and still misses the free shipping boundary.

## 1. Grade

```bash
uv run testproof grade \
  --repo /tmp/testproof-demo \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output /tmp/testproof-demo-report.json
```

Result:

```json
{
  "summary": {
    "killed": 5,
    "survived": 1,
    "invalid": 0,
    "timeout": 0,
    "skipped": 0,
    "total": 6,
    "score": 83.33333333333334,
    "partial": false,
    "confidence": "high",
    "reason": ""
  }
}
```

The survivor is `shipping.py:6`, comparison `>=` becomes `>`. The existing tests check 100 and 10, but not the exact free shipping threshold at 50.

## 2. Repair in dry run mode

```bash
uv run testproof repair \
  --repo /tmp/testproof-demo \
  --report /tmp/testproof-demo-report.json \
  --test-cmd "python -m pytest -q" \
  --dry-run
```

Output:

```text
Model unavailable: MODEL_API_KEY environment variable is required, or create ...
Model: unavailable
Kept: 1
Likely equivalent: 0
Rejected: 0
Deterministic template hits: 1
Model attempts: 0
  Kept test for a6af6dda17ba:
from shipping import shipping_fee


def test_repair_a6af6dda17ba_1():
    # Mutation at shipping.py:6: comparison >= becomes >.
    assert shipping_fee(50, False) == 0
```

The model line is a notice, not a failure. The template path found the boundary, ran the original and the mutant in an isolated interpreter, and produced the expected value from the original code. No model was called.

The probe passes `False` for the `member` parameter because it fills every argument for the case. The call is equivalent to `shipping_fee(50)`.

## 3. Apply

```bash
uv run testproof repair \
  --repo /tmp/testproof-demo \
  --report /tmp/testproof-demo-report.json \
  --test-cmd "python -m pytest -q" \
  --apply
```

The verifier confirmed all three conditions before the test was written:

1. The test passes on the original code.
2. The test fails on the mutant.
3. The full suite passes on the original code with the new test.

The applied file now contains one new test and one copy of the existing import:

```python
"""A deliberately weak test suite used by the TestProof demo."""

from shipping import shipping_fee


def test_free_shipping() -> None:
    assert shipping_fee(100) == 0


def test_paid_shipping() -> None:
    assert shipping_fee(10) == 5


def test_repair_a6af6dda17ba_1():
    # Mutation at shipping.py:6: comparison >= becomes >.
    assert shipping_fee(50, False) == 0
```

## 4. Re grade

```bash
uv run testproof grade \
  --repo /tmp/testproof-demo \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output /tmp/testproof-demo-fixed-report.json
```

Result:

```json
{
  "summary": {
    "killed": 6,
    "survived": 0,
    "invalid": 0,
    "timeout": 0,
    "skipped": 0,
    "total": 6,
    "score": 100.0,
    "partial": false,
    "confidence": "high",
    "reason": ""
  }
}
```

Score before: 83.33 percent. Score after: 100 percent. The survivor count went from 1 to 0.

## Artifact

This is the Markdown artifact to attach to the Alan task.

```markdown
# TestProof Report

Task: demo session
Pull request: none
Base: none, full fixture audit
Head: working tree
Test command: python -m pytest -q

## Result

- Score before: 83.33 percent
- Score after: 100 percent
- Threshold: 80 percent
- Status: pass
- Partial: no
- Confidence: high
- Likely equivalent: 0
- Model calls: 0

## Survivors fixed

| File | Line | Original | Replacement | Test added | Verified |
| --- | --- | --- | --- | --- | --- |
| shipping.py | 6 | >= | > | assert shipping_fee(50, False) == 0 | yes |

## Rejected candidates

| Mutant | Reason | Model called |
| --- | --- | --- |
| none | none | no |

## Survivors remaining

| File | Line | Original | Replacement | Reason |
| --- | --- | --- | --- | --- |
| none | none | none | none | none |

## What this means

The test suite caught 6 of 6 planted bugs in the fixture after repair. The new test was verified by the engine, not accepted on the model's word.

## What this does not mean

A high mutation score does not prove correctness. It means the tests catch the planted bugs in the changed lines. The fixture is a demonstration, not a benchmark.
```

## What this session proves

- The skill can grade, repair, and re grade without a model key.
- The repair path produces a test with a reason for its expected value.
- The verifier writes only tests that pass on the original, fail on the mutant, and keep the suite green.
- The report artifact carries the before and after score and the remaining survivors.

## What this session does not prove

- One fixture is not a corpus. Phase 5 measures the same flow on multiple modules with known bugs.
- The template path covers common operator shapes. The model fallback is measured separately in `docs/MODEL_BENCHMARK.md`.
- The fixture has no Git history. The demo uses `--all`; a normal repository uses a diff base.

The commands and outputs above are from a real run on 2026-10-27. The reports are in `/tmp/testproof-demo-report.json` and `/tmp/testproof-demo-fixed-report.json`.
