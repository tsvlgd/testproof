# Shop Fixture

This fixture is the opening demonstration for TestProof.

`shipping.py` contains a boundary at 50 and a membership rule. `test_shipping.py` has full line coverage but misses both the exact boundary and the membership path.

Run it from this directory:

```bash
python -m pytest -q
python -m pytest --cov=. --cov-report=term-missing
```

The tests pass and line coverage is 100 percent. TestProof should still find survivors on the changed lines. That gap is the product.
