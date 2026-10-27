# Benchmark corpus

Synthetic modules written for this benchmark from common defect patterns.
No external code is copied, so there are no third party license terms to
record. The weak suites are deliberately shallow: they pass on the
original module and on the known bug version, which is what makes bug
detection measurable before and after repair.

| Module | Pattern focus | Weak tests |
| --- | --- | --- |
| coupon_discount | Percentage discount with a storefront cap; boundary and cap mutants. | 2 |
| leap_year | Gregorian leap rule; century branch mutants. | 2 |
| mask_card | Mask all but the last digits of a payment card; constant guard drift. | 2 |
| retry_delay | Exponential backoff with a hard cap; cap and exponent mutants. | 2 |
| check_password | Length plus digit plus uppercase policy; boolean ladder mutants. | 2 |
| clamp_page | Clamp a requested page into the valid range; comparison mutants. | 2 |
| order_status | Map a status code to a label; string branch mutants. | 2 |
| parse_seconds | Parse 90s, 5m, 2h style durations; unit constants. | 2 |
| grade_band | Letter bands for scores; band boundary drift. | 2 |
| intervals_overlap | Half open range overlap; endpoint comparison quirk. | 2 |
| last_page | Final page of a listing; ceil division and zero boundary. | 2 |
| c_to_f | Celsius to Fahrenheit conversion; scale factor mutants. | 1 |

Each module has a known bug version in `benchmark/bugs/`. The bug derives
from a single seeded edit that the weak suite does not catch. Regenerate
with `uv run python benchmark/build_corpus.py` and it revalidates that
every weak suite passes on the original and on the bug version.
