"""String-Aware Comment & Docstring Token Finder (`src/draftproof/core/code/base.py`).

Character-by-character state machine that tracks string literal boundaries (`'`, `"`,
`` ` ``, triple quotes) and escape sequences so comment markers (`#`, `//`, `/* */`,
`--`, `<!-- -->`) inside strings or URLs are NEVER mistaken for comments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class LanguageSyntaxSpec:
    """Comment and string delimiter specification for a programming language family."""

    name: str
    single_line_markers: Tuple[str, ...]
    block_comment_delims: Tuple[Tuple[str, str], ...]
    supports_triple_quotes: bool = False
    supports_backtick_strings: bool = False
    supports_python_docstrings: bool = False


@dataclass
class CodeSpan:
    """Contiguous span of source code classified as executable `CODE`, `COMMENT`, or `DOCSTRING`."""

    kind: str  # "CODE" | "COMMENT" | "DOCSTRING"
    text: str
    marker: str = ""
    end_marker: str = ""
    indent: str = ""


def find_line_comment_start(line: str, markers: Tuple[str, ...]) -> Optional[Tuple[int, str]]:
    """Find the index of the first single-line comment marker outside any string literal."""
    in_quote: Optional[str] = None
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]
        if in_quote is not None:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if line.startswith(in_quote, i):
                i += len(in_quote)
                in_quote = None
                continue
            i += 1
            continue

        # Check triple quotes first, then single/double/backtick quotes
        if line.startswith('"""', i) or line.startswith("'''", i):
            in_quote = line[i : i + 3]
            i += 3
            continue
        if ch in ('"', "'", "`"):
            in_quote = ch
            i += 1
            continue

        # Check comment markers outside strings
        for marker in markers:
            if line.startswith(marker, i):
                # Guard against http:// or https:// when marker is //
                if marker == "//" and i > 0 and line[i - 1] == ":":
                    continue
                # Guard against shebang #!/usr/bin/env
                if marker == "#" and i == 0 and line.startswith("#!"):
                    return None
                return i, marker

        i += 1
    return None


def tokenize_code_spans(source: str, spec: LanguageSyntaxSpec) -> List[CodeSpan]:
    """Tokenize `source` into ordered `CodeSpan` items whose concatenation equals `source`."""
    spans: List[CodeSpan] = []
    lines = source.splitlines(keepends=True)
    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i]
        stripped_leading = line.lstrip(" \t")
        indent = line[: len(line) - len(stripped_leading)]

        # 1. Check Python standalone triple-quoted docstring (not preceded by `=` on the line)
        if spec.supports_python_docstrings and (
            stripped_leading.startswith('"""') or stripped_leading.startswith("'''")
        ):
            quote_delim = stripped_leading[:3]
            rest_after_open = stripped_leading[3:]
            if quote_delim in rest_after_open:
                # Single-line docstring
                close_pos = rest_after_open.find(quote_delim)
                full_doc_line = line
                spans.append(
                    CodeSpan(
                        kind="DOCSTRING",
                        text=full_doc_line,
                        marker=quote_delim,
                        end_marker=quote_delim,
                        indent=indent,
                    )
                )
                i += 1
                continue
            else:
                # Multi-line docstring
                doc_lines = [line]
                i += 1
                while i < num_lines:
                    doc_lines.append(lines[i])
                    if quote_delim in lines[i]:
                        i += 1
                        break
                    i += 1
                spans.append(
                    CodeSpan(
                        kind="DOCSTRING",
                        text="".join(doc_lines),
                        marker=quote_delim,
                        end_marker=quote_delim,
                        indent=indent,
                    )
                )
                continue

        # 2. Check block comments (/* ... */, <!-- ... -->) starting at line start
        matched_block = False
        for b_open, b_close in spec.block_comment_delims:
            if stripped_leading.startswith(b_open):
                rest_after_open = stripped_leading[len(b_open) :]
                if b_close in rest_after_open:
                    spans.append(
                        CodeSpan(
                            kind="COMMENT",
                            text=line,
                            marker=b_open,
                            end_marker=b_close,
                            indent=indent,
                        )
                    )
                    i += 1
                    matched_block = True
                    break
                else:
                    block_lines = [line]
                    i += 1
                    while i < num_lines:
                        block_lines.append(lines[i])
                        if b_close in lines[i]:
                            i += 1
                            break
                        i += 1
                    spans.append(
                        CodeSpan(
                            kind="COMMENT",
                            text="".join(block_lines),
                            marker=b_open,
                            end_marker=b_close,
                            indent=indent,
                        )
                    )
                    matched_block = True
                    break
        if matched_block:
            continue

        # 3. Check single-line or trailing comment outside string literals
        hit = find_line_comment_start(line, spec.single_line_markers)
        if hit is not None:
            pos, marker = hit
            if pos > 0:
                spans.append(CodeSpan(kind="CODE", text=line[:pos]))
            spans.append(
                CodeSpan(
                    kind="COMMENT",
                    text=line[pos:],
                    marker=marker,
                    end_marker="",
                    indent=indent if pos == len(indent) else "",
                )
            )
            i += 1
            continue

        spans.append(CodeSpan(kind="CODE", text=line))
        i += 1

    return spans
