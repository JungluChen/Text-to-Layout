"""Bounded QEDA footprint syntax reader; no geometry or solver acceptance.

This intentionally supports a narrow S-expression dialect, not all KiCad files.
Numbers remain atoms; semantic validation belongs to a separate assessment.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_BYTES = 1_048_576
MAX_NODES = 20_000
MAX_DEPTH = 32
MAX_ATOM_CHARS = 4096
_WHITESPACE = " \t\r\n"


@dataclass(frozen=True)
class Atom:
    value: str
    quoted: bool = False


@dataclass(frozen=True)
class Expression:
    children: tuple[Atom | Expression, ...]


def parse_footprint_syntax(data: bytes) -> Expression:
    """Read exactly one list, raising ValueError on syntax/resource violations.

    No imports of QEDA, file writes, subprocesses or network access. Quoted
    strings allow only escaped quote/backslash; all other escapes fail closed.
    Quotedness is preserved so consumers need not confuse names with numbers.
    """
    if len(data) > MAX_BYTES:
        raise ValueError("footprint exceeds byte limit")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("footprint must be UTF-8") from exc
    stack: list[list[Atom | Expression]] = []
    root: Expression | None = None
    nodes = 0
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char in _WHITESPACE:
            pos += 1
            continue
        if root is not None:
            raise ValueError("trailing content after root")
        if char == "(":
            nodes += 1
            if nodes > MAX_NODES or len(stack) >= MAX_DEPTH:
                raise ValueError("footprint node/depth limit exceeded")
            stack.append([])
            pos += 1
            continue
        if char == ")":
            if not stack:
                raise ValueError("unmatched closing parenthesis")
            expression = Expression(tuple(stack.pop()))
            if stack:
                stack[-1].append(expression)
            else:
                root = expression
            pos += 1
            continue
        if not stack:
            raise ValueError("atom outside root")
        nodes += 1
        if nodes > MAX_NODES:
            raise ValueError("footprint node limit exceeded")
        quoted = char == '"'
        if quoted:
            pos += 1
        value: list[str] = []
        closed = False
        while pos < len(text):
            char = text[pos]
            if quoted and char == '"':
                pos += 1
                closed = True
                if pos < len(text) and text[pos] not in _WHITESPACE + "()":
                    raise ValueError("missing separator after string")
                break
            if not quoted and char in _WHITESPACE + "()":
                break
            if ord(char) < 32 or ord(char) == 127:
                raise ValueError("control character in atom")
            if char == "\\":
                if not quoted or pos + 1 >= len(text) or text[pos + 1] not in '\\"':
                    raise ValueError("unsupported escape")
                pos += 1
                char = text[pos]
            elif not quoted and (char == '"' or char.isspace()):
                raise ValueError("invalid bare atom")
            value.append(char)
            if len(value) > MAX_ATOM_CHARS:
                raise ValueError("footprint atom limit exceeded")
            pos += 1
        if quoted and not closed:
            raise ValueError("unterminated string")
        stack[-1].append(Atom("".join(value), quoted))
    if stack or root is None:
        raise ValueError("missing or unclosed root")
    return root
