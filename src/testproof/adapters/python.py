"""A Python adapter that splices one operator using AST source positions."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from typing import Any

from testproof.models import MutationPoint

_COMPARISONS: dict[type[ast.cmpop], tuple[str, str]] = {
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
}
_ARITHMETIC: dict[type[ast.operator], tuple[str, str]] = {
    ast.Add: ("+", "-"),
    ast.Sub: ("-", "+"),
    ast.Mult: ("*", "/"),
    ast.Div: ("/", "*"),
}
_INT_CONSTANTS: dict[int, int] = {0: 1, 1: 0}
_BOOL_CONSTANTS: dict[bool, bool] = {True: False, False: True}
_IGNORED_ANCESTORS = (
    ast.JoinedStr,
    ast.FormattedValue,
    ast.AnnAssign,
    ast.Import,
    ast.ImportFrom,
)


@dataclass(frozen=True)
class _Candidate:
    line: int
    column: int
    end_line: int
    end_column: int
    operator: str
    original: str
    replacement: str


class PythonAdapter:
    """Discover rule based mutants in Python source.

    Mutations are text splices at AST spans. The rest of the file stays byte
    for byte identical, which keeps diffs small and source based tests stable.
    """

    language = "python"
    file_extensions = (".py",)

    def discover(
        self,
        path: str,
        source: str,
        changed_lines: set[int] | None,
    ) -> list[MutationPoint]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        candidates: list[_Candidate] = []
        for node in ast.walk(tree):
            candidates.extend(self._candidates(node, source, tree))

        ordered = sorted(
            candidates,
            key=lambda item: (item.line, item.column, item.operator, item.original),
        )
        points: list[MutationPoint] = []
        seen: set[tuple[object, ...]] = set()
        for candidate in ordered:
            if changed_lines is not None and candidate.line not in changed_lines:
                continue
            identity = (
                candidate.line,
                candidate.column,
                candidate.end_line,
                candidate.end_column,
                candidate.operator,
                candidate.replacement,
            )
            if identity in seen:
                continue
            seen.add(identity)
            points.append(
                MutationPoint(
                    id=_point_id(path, candidate),
                    path=path,
                    line=candidate.line,
                    column=candidate.column,
                    end_line=candidate.end_line,
                    end_column=candidate.end_column,
                    operator=candidate.operator,
                    original=candidate.original,
                    replacement=candidate.replacement,
                )
            )
        return points

    def apply(self, source: str, point: MutationPoint) -> str:
        lines = source.splitlines(keepends=True)
        if point.line < 1 or point.end_line > len(lines):
            msg = f"Mutation {point.id} is outside {point.path}"
            raise ValueError(msg)
        start = _offset(lines, point.line, point.column)
        end = _offset(lines, point.end_line, point.end_column)
        current = source[start:end]
        if current != point.original:
            msg = (
                f"Mutation {point.id} expected {point.original!r} at "
                f"{point.path}:{point.line}, found {current!r}"
            )
            raise ValueError(msg)
        return source[:start] + point.replacement + source[end:]

    def validate(self, source: str) -> bool:
        try:
            ast.parse(source)
        except SyntaxError:
            return False
        return True

    def _candidates(
        self,
        node: ast.AST,
        source: str,
        tree: ast.AST,
    ) -> list[_Candidate]:
        if isinstance(node, ast.Compare):
            return self._compare_candidates(node, source)
        if isinstance(node, ast.BoolOp):
            return self._bool_candidates(node, source)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return self._not_candidates(node, source)
        if isinstance(node, ast.BinOp):
            return self._arithmetic_candidates(node, source)
        if isinstance(node, ast.Return) and node.value is not None:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return []
            return [_span(node.value, source, "return", _segment(source, node.value), "None")]
        if isinstance(node, ast.Constant):
            return self._constant_candidates(node, source, tree)
        return []

    def _compare_candidates(self, node: ast.Compare, source: str) -> list[_Candidate]:
        found: list[_Candidate] = []
        for op_node, comparator in zip(node.ops, node.comparators, strict=True):
            pair = _COMPARISONS.get(type(op_node))
            if pair is None:
                continue
            original, replacement = pair
            left = node.left if not found else node.comparators[len(found) - 1]
            column = _find_operator_between(source, left, comparator, original)
            if column is None:
                continue
            line = _line_for_column(source, column)
            found.append(
                _Candidate(
                    line=line,
                    column=column - _line_offset(source, line),
                    end_line=line,
                    end_column=column - _line_offset(source, line) + len(original),
                    operator="comparison",
                    original=original,
                    replacement=replacement,
                )
            )
        return found

    def _bool_candidates(self, node: ast.BoolOp, source: str) -> list[_Candidate]:
        original = "and" if isinstance(node.op, ast.And) else "or"
        replacement = "or" if original == "and" else "and"
        found: list[_Candidate] = []
        for value in node.values[1:]:
            prefix = source.splitlines()[value.lineno - 1][: value.col_offset]
            token = f" {original} "
            column = prefix.rfind(token)
            if column < 0:
                continue
            found.append(
                _Candidate(
                    line=value.lineno,
                    column=column + 1,
                    end_line=value.lineno,
                    end_column=column + 1 + len(original),
                    operator="boolean",
                    original=original,
                    replacement=replacement,
                )
            )
        return found

    def _not_candidates(self, node: ast.UnaryOp, source: str) -> list[_Candidate]:
        """Target the ``not `` keyword, replacing it with nothing."""
        # The UnaryOp spans the whole expression: ``not member``
        # We want only the ``not `` prefix, leaving ``member``
        full_segment = _segment(source, node)
        if not full_segment.startswith("not "):
            return []
        return [
            _Candidate(
                line=node.lineno,
                column=node.col_offset,
                end_line=node.lineno,
                end_column=node.col_offset + 4,
                operator="boolean",
                original="not ",
                replacement="",
            )
        ]

    def _arithmetic_candidates(self, node: ast.BinOp, source: str) -> list[_Candidate]:
        pair = _ARITHMETIC.get(type(node.op))
        if pair is None:
            return []
        original, replacement = pair
        if _is_equivalent_arithmetic(node):
            return []
        column = _find_operator_between(source, node.left, node.right, original)
        if column is None:
            return []
        line = _line_for_column(source, column)
        col_in_line = column - _line_offset(source, line)
        return [
            _Candidate(
                line=line,
                column=col_in_line,
                end_line=line,
                end_column=col_in_line + len(original),
                operator="arithmetic",
                original=original,
                replacement=replacement,
            )
        ]

    def _constant_candidates(
        self,
        node: ast.Constant,
        source: str,
        tree: ast.AST,
    ) -> list[_Candidate]:
        value = node.value
        replacement_value: int | bool | None
        if type(value) is bool:
            replacement_value = _BOOL_CONSTANTS.get(value)
        elif type(value) is int:
            replacement_value = _INT_CONSTANTS.get(value)
        else:
            return []
        if replacement_value is None:
            return []
        if _has_ancestor(node, tree, _IGNORED_ANCESTORS):
            return []
        if _is_default_value(node, tree):
            return []
        if _is_docstring(node, tree):
            return []
        segment = _segment(source, node)
        if segment.startswith(("'", '"')):
            return []
        replacement = repr(replacement_value)
        if segment == replacement:
            return []
        return [_span(node, source, "constant", segment, replacement)]


def _find_operator_between(
    source: str,
    left: ast.AST,
    right: ast.AST,
    token: str,
) -> int | None:
    """Return the absolute offset in ``source`` of ``token`` between ``left`` and ``right``."""

    lines = source.splitlines(keepends=True)

    left_end_lineno = getattr(left, "end_lineno", None) or getattr(left, "lineno", None)
    left_end_col_offset = getattr(left, "end_col_offset", None) or 0
    right_lineno = getattr(right, "lineno", None)
    right_col_offset = getattr(right, "col_offset", None)

    if not isinstance(left_end_lineno, int):
        return None
    if not isinstance(right_lineno, int):
        return None
    if not isinstance(right_col_offset, int):
        return None
    if not isinstance(left_end_col_offset, int):
        return None

    left_end = _offset(lines, left_end_lineno, left_end_col_offset)
    right_start = _offset(lines, right_lineno, right_col_offset)
    window = source[left_end:right_start]
    index = window.find(token)
    if index < 0:
        return None
    return left_end + index


def _line_for_column(source: str, absolute: int) -> int:
    """Turn an absolute byte offset into a 1 based line number."""
    return source[:absolute].count("\n") + 1


def _line_offset(source: str, line: int) -> int:
    """The absolute byte offset of the start of ``line``."""
    lines = source.splitlines(keepends=True)
    return sum(len(item) for item in lines[: line - 1])


def _is_equivalent_arithmetic(node: ast.BinOp) -> bool:
    right = node.right
    if not isinstance(right, ast.Constant) or isinstance(right.value, bool):
        return False
    if not isinstance(right.value, int):
        return False
    if isinstance(node.op, (ast.Add, ast.Sub)) and right.value == 0:
        return True
    return isinstance(node.op, (ast.Mult, ast.Div)) and right.value == 1


def _is_docstring(node: ast.Constant, tree: ast.AST) -> bool:
    parent = _parent(node, tree)
    if not isinstance(parent, ast.Expr):
        return False
    owner = _parent(parent, tree)
    if not isinstance(owner, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    return bool(owner.body) and owner.body[0] is parent


def _is_default_value(node: ast.AST, tree: ast.AST) -> bool:
    """Return whether ``node`` is a function parameter default."""
    parent = _parent(node, tree)
    if not isinstance(parent, ast.arguments):
        return False
    return node in parent.defaults or node in parent.kw_defaults


def _has_ancestor(
    node: ast.AST,
    tree: ast.AST,
    kinds: tuple[type[ast.AST], ...],
) -> bool:
    current: ast.AST | None = node
    while current is not None:
        current = _parent(current, tree)
        if isinstance(current, kinds):
            return True
    return False


def _parent(node: ast.AST, tree: ast.AST) -> ast.AST | None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if child is node:
                return parent
    return None


def _segment(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        msg = "Python node has no source span"
        raise ValueError(msg)
    return segment


def _span(
    node: ast.AST,
    source: str,
    operator: str,
    original: str,
    replacement: str,
) -> _Candidate:
    segment = _segment(source, node)
    if segment != original and operator != "boolean":
        original = segment

    # Using Any to suppress mypy errors regarding AST node attributes.

    n: Any = node

    return _Candidate(
        line=n.lineno,
        column=n.col_offset,
        end_line=getattr(n, "end_lineno", n.lineno) or n.lineno,
        end_column=getattr(n, "end_col_offset", n.col_offset) or n.col_offset,
        operator=operator,
        original=original,
        replacement=replacement,
    )


def _offset(lines: list[str], line: int, column: int) -> int:
    return sum(len(item) for item in lines[: line - 1]) + column


def _point_id(path: str, candidate: _Candidate) -> str:
    raw = (
        f"{path}:{candidate.line}:{candidate.column}:{candidate.operator}:"
        f"{candidate.original}:{candidate.replacement}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
