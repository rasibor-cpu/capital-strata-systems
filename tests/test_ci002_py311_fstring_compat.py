"""CSS-CI-002: Python 3.11 rejects backslashes inside f-string expressions."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

_SHELL = Path("dashboard/enterprise_shell/shell.py")


def _fstring_expressions_with_backslash(source: str) -> list[tuple[int, str]]:
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    hits: list[tuple[int, str]] = []
    expecting_expr = False
    current: list = []
    expr_line: int | None = None

    def flush() -> None:
        nonlocal expecting_expr, current, expr_line
        if current:
            text = "".join(tok.string for tok in current)
            if "\\" in text:
                hits.append((expr_line or current[0].start[0], text))
        expecting_expr = False
        current = []
        expr_line = None

    for tok in tokens:
        if tok.type == tokenize.FSTRING_START:
            expecting_expr = True
            current = []
            expr_line = tok.start[0]
            continue
        if tok.type == tokenize.FSTRING_MIDDLE:
            flush()
            expecting_expr = True
            current = []
            expr_line = tok.start[0]
            continue
        if tok.type == tokenize.FSTRING_END:
            flush()
            continue
        if expecting_expr and tok.type not in (
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.COMMENT,
        ):
            if not current:
                expr_line = tok.start[0]
            current.append(tok)
    return hits


def test_enterprise_shell_parses_as_plain_source():
    source = _SHELL.read_text(encoding="utf-8")
    ast.parse(source)
    compile(source, str(_SHELL), "exec")
    if hasattr(tokenize, "FSTRING_START"):
        assert _fstring_expressions_with_backslash(source) == []
    assert 'aria-current="page"' in source
    assert "aria-current=\\\"" not in source
