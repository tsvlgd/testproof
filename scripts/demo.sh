#!/usr/bin/env bash
# TestProof demo: grade, repair, regrade on the weak fixture.
# Run this in a terminal while recording. Each step prints what to show.
set -euo pipefail

STEP=0
step() {
  STEP=$((STEP + 1))
  echo ""
  echo "=============================================="
  echo "  STEP $STEP: $1"
  echo "=============================================="
  echo ""
  sleep 2
}

# Use the installed CLI if available, fall back to uv run.
if command -v testproof >/dev/null 2>&1; then
  TP="testproof"
else
  TP="uv run testproof"
fi

# Clean working copy so the demo does not dirty the repo.
WORKDIR=/tmp/testproof-demo
rm -rf "$WORKDIR"
cp -a fixtures/shop "$WORKDIR"

# Isolate from any model config so templates are proven without a key.
export HOME=/tmp/testproof-demo-home
mkdir -p "$HOME"
unset MODEL_API_KEY MODEL_NAME MODEL_MAX_TOKENS || true

step "Show the weak test suite"
echo "The tests pass. Line coverage would be full. Watch what TestProof finds."
echo ""
cat "$WORKDIR/test_shipping.py"
echo ""
sleep 4

step "Grade the fixture"
$TP grade \
  --repo "$WORKDIR" \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output "$WORKDIR/report.json"
echo ""
echo "Score is about 83 percent. One survivor: the free shipping boundary at 50."
sleep 3

step "Repair in dry run (no writes, no model key)"
$TP repair \
  --repo "$WORKDIR" \
  --report "$WORKDIR/report.json" \
  --test-cmd "python -m pytest -q" \
  --dry-run
echo ""
echo "Templates found the boundary. Kept 1, model attempts 0."
sleep 3

step "Apply the verified test"
$TP repair \
  --repo "$WORKDIR" \
  --report "$WORKDIR/report.json" \
  --test-cmd "python -m pytest -q" \
  --apply
echo ""
echo "The engine kept this test only because it passed on the original and failed on the mutant."
sleep 3

step "Show the applied test"
echo "The new test is in the suite:"
echo ""
grep -A3 "test_repair" "$WORKDIR/test_shipping.py" || true
echo ""
sleep 3

step "Re grade"
$TP grade \
  --repo "$WORKDIR" \
  --all \
  --test-cmd "python -m pytest -q" \
  --format json \
  --output "$WORKDIR/fixed.json"
echo ""
echo "Score is now 100 percent. Zero survivors."
sleep 3

step "Summary"
echo "Fixture: 83.33 to 100 percent."
echo "1 test kept. 0 model calls. 0 rejected."
echo "The engine proves every test before keeping it."
echo ""
echo "Done."
