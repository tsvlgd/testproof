# Benchmark results

Measured on 2026-10-27. Corpus: 12 synthetic modules with weak suites and known bug
versions (see `benchmark/corpus/SOURCES.md`). Method: grade, verified repair
(templates first, model fallback), re grade, then run the repaired suite
against the known bug version. Detection before repair is by construction:
the weak suite passes on the bug version. Detection after repair is measured.

Model fallback active: True. No template rejection was
silenced: every kept test passed on the original, failed on the mutant, and
kept the full suite green.

## Per module

| Module | Before | After | Kept | Rejected | Equivalent | Templates | Model calls | Bug detected after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c_to_f | 50.00 (2 survive) | 100.00 (0 survive) | 2 | 0 | 0 | 2 | 0 | yes |
| check_password | 60.00 (2 survive) | 80.00 (1 survive) | 1 | 1 | 0 | 1 | 1 | yes |
| clamp_page | 42.86 (4 survive) | 85.71 (1 survive) | 3 | 1 | 0 | 3 | 1 | yes |
| coupon_discount | 83.33 (1 survive) | 83.33 (1 survive) | 0 | 1 | 0 | 0 | 1 | no |
| grade_band | 0.00 (3 survive) | 100.00 (0 survive) | 3 | 0 | 0 | 3 | 0 | yes |
| intervals_overlap | 50.00 (2 survive) | 100.00 (0 survive) | 2 | 0 | 0 | 2 | 0 | yes |
| last_page | 25.00 (6 survive) | 87.50 (1 survive) | 5 | 1 | 0 | 5 | 1 | yes |
| leap_year | 50.00 (4 survive) | 100.00 (0 survive) | 4 | 0 | 0 | 4 | 0 | yes |
| mask_card | 71.43 (2 survive) | 85.71 (1 survive) | 1 | 1 | 0 | 1 | 1 | yes |
| order_status | 100.00 (0 survive) | 100.00 (0 survive) | 0 | 0 | 0 | 0 | 0 | no |
| parse_seconds | 62.50 (3 survive) | 100.00 (0 survive) | 3 | 0 | 0 | 2 | 1 | yes |
| retry_delay | 100.00 (0 survive) | 100.00 (0 survive) | 0 | 0 | 0 | 0 | 0 | no |

## Aggregate

| Metric | Value |
| --- | --- |
| Modules | 12 |
| Mutants graded | 68 |
| Mutation score before repair | 57.35 percent |
| Mutation score after repair | 92.65 percent |
| Survivors killed by verified repair | 24 of 29 |
| Tests kept (all verified) | 24 |
| Model attempts | 6 |
| Known bugs detected after repair | 9 of 12 |
| Benchmark wall time | 81.8 s |

## Reproduce

```bash
uv run python benchmark/build_corpus.py
uv run python benchmark/run.py
```

Raw data: `benchmark/results/raw.json`. The renderer generates results.md from
the raw files, so numbers in this document are not hand written.
