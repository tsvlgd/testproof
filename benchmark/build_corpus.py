"""Build the benchmark corpus.

Each module is a small, realistic Python function set with a deliberately weak
test suite and a known bug version. The weak suite passes on the original code
and also passes on the bug version, which is the property that makes bug
detection measurable: the suite does not notice the bug before repair.

Modules are synthetic, written for this benchmark from common defect patterns
(boundary drift, boolean inversion, cap regression, unit mixups). No external
code is copied. See benchmark/corpus/SOURCES.md.

Layout:

    benchmark/corpus/<id>/<id>.py          original, correctly implemented
    benchmark/corpus/<id>/tests/test_<id>.py   weak suite
    benchmark/bugs/<id>/<id>.py            the known bug version

Run:

    uv run python benchmark/build_corpus.py
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ModuleSpec:
    """One corpus module: source, weak suite, and its seeded bug."""

    module_id: str
    summary: str
    source: str
    weak_tests: str
    bug_edits: tuple[tuple[str, str], ...]


def _spec(
    module_id: str,
    summary: str,
    source: str,
    weak_tests: str,
    *bug_edits: tuple[str, str],
) -> ModuleSpec:
    return ModuleSpec(
        module_id=module_id,
        summary=summary,
        source=source.strip("\n") + "\n",
        weak_tests=weak_tests.strip("\n") + "\n",
        bug_edits=tuple(bug_edits),
    )


SPECS: list[ModuleSpec] = [
    _spec(
        "coupon_discount",
        "Percentage discount with a storefront cap; boundary and cap mutants.",
        '''
def apply_discount(price: float, pct: float) -> float:
    """Apply a percentage discount, capped at the storefront maximum."""
    scaled = pct if pct < 50 else 50
    return round(price * (1 - scaled / 100), 2)
''',
        """
from coupon_discount import apply_discount


def test_small_discount():
    assert apply_discount(100.0, 10.0) == 90.0


def test_no_discount():
    assert apply_discount(40.0, 0.0) == 40.0
""",
        ("pct if pct < 50 else 50", "pct if pct < 70 else 70"),
    ),
    _spec(
        "leap_year",
        "Gregorian leap rule; century branch mutants.",
        '''
def is_leap_year(year: int) -> bool:
    """Leap year by the Gregorian rule."""
    if year % 100 == 0:
        return year % 400 == 0
    return year % 4 == 0
''',
        """
from leap_year import is_leap_year


def test_regular_leap():
    assert is_leap_year(2024) is True


def test_regular_common():
    assert is_leap_year(2023) is False
""",
        ("return year % 400 == 0", "return year % 400 != 0"),
    ),
    _spec(
        "mask_card",
        "Mask all but the last digits of a payment card; constant guard drift.",
        '''
def mask_card(number: str) -> str:
    """Mask all but the last digits of a payment card."""
    digits = number.replace(" ", "")
    visible = 4
    if len(digits) <= visible:
        return "*" * len(digits)
    return "*" * (len(digits) - visible) + digits[-visible:]
''',
        """
from mask_card import mask_card


def test_long_card_is_masked():
    masked = mask_card("1234 5678 9012 3456")
    assert masked.endswith("3456")
    assert masked[:5] == "*****"


def test_short_card_is_hidden():
    assert mask_card("123") == "***"
""",
        ("    visible = 4\n", "    visible = 5\n"),
    ),
    _spec(
        "retry_delay",
        "Exponential backoff with a hard cap; cap and exponent mutants.",
        '''
def retry_delay(base_seconds: float, attempt: int) -> float:
    """Exponential backoff with a hard cap."""
    raw = base_seconds * 2 ** (attempt - 1)
    return min(raw, 30.0)
''',
        """
from retry_delay import retry_delay


def test_first_attempt_is_base():
    assert retry_delay(1.0, 1) == 1.0


def test_second_attempt_doubles():
    assert retry_delay(1.0, 2) == 2.0
""",
        ("    return min(raw, 30.0)", "    return min(raw, 3.0)"),
    ),
    _spec(
        "check_password",
        "Length plus digit plus uppercase policy; boolean ladder mutants.",
        '''
def check_password(password: str) -> bool:
    """Policy: at least eight characters with a digit and an uppercase letter."""
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return has_digit and has_upper
''',
        """
from check_password import check_password


def test_accepts_good_password():
    assert check_password("Passw0rd99") is True


def test_rejects_short():
    assert check_password("aB1") is False
""",
        ("    return has_digit and has_upper", "    return has_upper"),
    ),
    _spec(
        "clamp_page",
        "Clamp a requested page into the valid range; comparison mutants.",
        '''
def clamp_page(page: int, page_count: int) -> int:
    """Clamp a requested page into the valid range."""
    if page < 1:
        return 1
    if page > page_count:
        return page_count
    return page
''',
        """
from clamp_page import clamp_page


def test_inside_range():
    assert clamp_page(3, 10) == 3


def test_negative_page_returns_first():
    assert clamp_page(-2, 10) == 1
""",
        ("        return page_count\n", "        return page_count + 1\n"),
    ),
    _spec(
        "order_status",
        "Map a status code to a label; string branch mutants.",
        '''
def order_status(code: int) -> str:
    """Map a numeric status code to a shipping label."""
    if code == 1:
        return "open"
    if code == 2:
        return "paid"
    if code == 3:
        return "shipped"
    return "unknown"
''',
        """
from order_status import order_status


def test_open():
    assert order_status(1) == "open"


def test_unknown():
    assert order_status(9) == "unknown"
""",
        ('        return "paid"', '        return "unpaid"'),
    ),
    _spec(
        "parse_seconds",
        "Parse 90s, 5m, 2h style durations; unit constants.",
        '''
def parse_seconds(spec: str) -> int:
    """Parse a duration like 30s, 5m, or 2h into seconds."""
    if spec.endswith("s"):
        return int(spec[:-1])
    if spec.endswith("m"):
        return int(spec[:-1]) * 60
    if spec.endswith("h"):
        return int(spec[:-1]) * 3600
    raise ValueError(f"unknown unit in {spec!r}")
''',
        """
from parse_seconds import parse_seconds


def test_seconds():
    assert parse_seconds("45s") == 45


def test_minutes():
    assert parse_seconds("3m") == 180
""",
        ("        return int(spec[:-1]) * 3600", "        return int(spec[:-1]) * 360"),
    ),
    _spec(
        "grade_band",
        "Letter bands for scores; band boundary drift.",
        '''
def grade_band(score: int) -> str:
    """Return the letter band for a score out of 100."""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "F"
''',
        """
from grade_band import grade_band


def test_fail_band():
    assert grade_band(30) == "F"


def test_top_band():
    assert grade_band(95) == "A"
""",
        ("    if score >= 75:", "    if score >= 85:"),
    ),
    _spec(
        "intervals_overlap",
        "Half open range overlap; endpoint comparison quirk.",
        '''
def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """True when two half open ranges share any point."""
    return a_start < b_end and b_start < a_end
''',
        """
from intervals_overlap import intervals_overlap


def test_disjoint():
    assert intervals_overlap(0, 2, 5, 8) is False


def test_contained():
    assert intervals_overlap(0, 10, 2, 4) is True
""",
        (
            "return a_start < b_end and b_start < a_end",
            "return a_start <= b_end and b_start < a_end",
        ),
    ),
    _spec(
        "last_page",
        "Final page of a listing; ceil division and zero boundary.",
        '''
def last_page(item_count: int, page_size: int) -> int:
    """Return the number of the final page for a listing."""
    if item_count <= 0:
        return 1
    return (item_count + page_size - 1) // page_size
''',
        """
from last_page import last_page


def test_partial_last_page():
    assert last_page(31, 10) == 4


def test_small_listing():
    assert last_page(7, 10) == 1
""",
        (
            "    return (item_count + page_size - 1) // page_size",
            "    return (item_count + page_size) // page_size",
        ),
    ),
    _spec(
        "c_to_f",
        "Celsius to Fahrenheit conversion; scale factor mutants.",
        '''
def c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32
''',
        """
from c_to_f import c_to_f


def test_freezing():
    assert c_to_f(0.0) == 32.0
""",
        ("    return celsius * 9 / 5 + 32", "    return celsius * 9 // 5 + 32"),
    ),
]


def _check_source_parses(text: str, label: str) -> None:
    try:
        ast.parse(text)
    except SyntaxError as exc:
        raise ValueError(f"{label} does not parse: {exc}") from exc


def _load_module(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_weak_suite(module_path: Path, tests_path: Path, name: str) -> None:
    """Run a weak suite in process. Every test function must pass."""
    _load_module(module_path, name)
    tests_module = _load_module(tests_path, f"{name}_tests")
    ran = 0
    for attr in dir(tests_module):
        if attr.startswith("test_"):
            getattr(tests_module, attr)()
            ran += 1
    if ran == 0:
        raise ValueError(f"{tests_path} defines no tests")
    del sys.modules[name]
    del sys.modules[f"{name}_tests"]


def build(bug_root: Path, corpus_root: Path) -> list[dict[str, object]]:
    """Write the corpus, validate it, and return its records."""
    corpus_root.mkdir(parents=True, exist_ok=True)
    bug_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for spec in SPECS:
        bug_source = spec.source
        for old, new in spec.bug_edits:
            if bug_source.count(old) != 1:
                raise ValueError(
                    f"bug edit for {spec.module_id} does not apply exactly once: {old!r}"
                )
            bug_source = bug_source.replace(old, new, 1)
        if bug_source == spec.source:
            raise ValueError(f"bug edit for {spec.module_id} produced an identical module")

        _check_source_parses(spec.source, f"{spec.module_id} source")
        _check_source_parses(bug_source, f"{spec.module_id} bug version")
        _check_source_parses(spec.weak_tests, f"{spec.module_id} weak tests")

        module_dir = corpus_root / spec.module_id
        (module_dir / "tests").mkdir(parents=True, exist_ok=True)
        (module_dir / f"{spec.module_id}.py").write_text(spec.source, encoding="utf-8")
        (module_dir / "tests" / f"test_{spec.module_id}.py").write_text(
            spec.weak_tests, encoding="utf-8"
        )
        bug_dir = bug_root / spec.module_id
        bug_dir.mkdir(parents=True, exist_ok=True)
        (bug_dir / f"{spec.module_id}.py").write_text(bug_source, encoding="utf-8")

        weak_ok = _weak_suite_passes(
            module_dir / f"{spec.module_id}.py", module_dir / "tests" / f"test_{spec.module_id}.py"
        )
        bug_left_undetected = _bug_suite_passes(
            bug_dir / f"{spec.module_id}.py", module_dir / "tests" / f"test_{spec.module_id}.py"
        )

        records.append(
            {
                "module_id": spec.module_id,
                "summary": spec.summary,
                "weak_tests_count": count_tests(spec.weak_tests),
                "weak_suite_passes_original": weak_ok,
                "weak_suite_passes_bug": bug_left_undetected,
            }
        )
    write_sources_md(corpus_root, records)
    return records


def _weak_suite_passes(module_path: Path, tests_path: Path) -> bool:
    """Run a weak suite in process. Every test function must pass."""
    name = module_path.stem
    try:
        _run_weak_suite(module_path, tests_path, name)
    except Exception:
        return False
    return True


def _bug_suite_passes(bug_module_path: Path, tests_path: Path) -> bool:
    """True when the weak suite misses the bug, which is the required property."""
    name = bug_module_path.stem
    try:
        _run_weak_suite(bug_module_path, tests_path, name)
    except Exception:
        return False
    return True


def count_tests(text: str) -> int:
    """Count test functions in a suite."""
    return len(re.findall(r"^\s*def test_\w+\s*\(", text, re.MULTILINE))


def write_sources_md(corpus_root: Path, records: list[dict[str, object]]) -> None:
    """Write the provenance and purpose record for the corpus."""
    lines = [
        "# Benchmark corpus",
        "",
        "Synthetic modules written for this benchmark from common defect patterns.",
        "No external code is copied, so there are no third party license terms to",
        "record. The weak suites are deliberately shallow: they pass on the",
        "original module and on the known bug version, which is what makes bug",
        "detection measurable before and after repair.",
        "",
        "| Module | Pattern focus | Weak tests |",
        "| --- | --- | --- |",
    ]
    for rec in records:
        lines.append(f"| {rec['module_id']} | {rec['summary']} | {rec['weak_tests_count']} |")
    lines += [
        "",
        "Each module has a known bug version in `benchmark/bugs/`. The bug derives",
        "from a single seeded edit that the weak suite does not catch. Regenerate",
        "with `uv run python benchmark/build_corpus.py` and it revalidates that",
        "every weak suite passes on the original and on the bug version.",
        "",
    ]
    (corpus_root / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    records = build(ROOT / "bugs", ROOT / "corpus")
    for rec in records:
        status_ok = bool(rec["weak_suite_passes_original"]) and bool(rec["weak_suite_passes_bug"])
        flag = "ok" if status_ok else "BROKEN"
        print(f"{rec['module_id']}: {flag} ({rec['weak_tests_count']} weak tests)")
    broken = [
        rec
        for rec in records
        if not (rec["weak_suite_passes_original"] and rec["weak_suite_passes_bug"])
    ]
    if broken:
        print(f"validation failed for {len(broken)} modules")
        return 1
    print(f"corpus built and validated: {len(records)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
