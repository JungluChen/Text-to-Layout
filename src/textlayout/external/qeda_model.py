"""Validate the pinned generator's model record, without opening its VRML file."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal

from textlayout.external.qeda_pad import _bare
from textlayout.external.qeda_syntax import Expression, parse_footprint_syntax

_BASENAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,127}\.wrl\Z')
_NUMBER = re.compile(r'[+-]?[0-9]{1,4}(?:\.[0-9]{1,9})?\Z')


@dataclass(frozen=True)
class ModelReference:
    basename: str
    scale: tuple[float, float, float]  # dimensionless; not a unit conversion claim
    zero_translation: bool
    zero_rotation: bool
    raw_sha256: str


def decode_model_reference(data: bytes, *, expected_basename: str) -> ModelReference:
    """Require explicit basename and pinned zero/0.3937/zero transform record.

    No filesystem or network access. Basenames are restricted ASCII names, not
    paths; unknown/duplicate fields, nesting and changed transforms reject with
    ValueError. Decimal equality avoids accepting changes through float rounding.
    This is record identity only: VRML existence, units and geometry are untested.
    """
    if _BASENAME.fullmatch(expected_basename) is None:
        raise ValueError('unsupported expected model basename')
    nodes = parse_footprint_syntax(data).children
    if len(nodes) != 5 or _bare(nodes[0]) != 'model':
        raise ValueError('model requires basename and three transform fields')
    if _bare(nodes[1]) != expected_basename:
        raise ValueError('model basename does not match explicit expectation')
    seen: set[str] = set()
    for node in nodes[2:]:
        if not isinstance(node, Expression) or len(node.children) != 2:
            raise ValueError('transform requires exactly one xyz list')
        key = _bare(node.children[0])
        if key not in {'at', 'scale', 'rotate'} or key in seen:
            raise ValueError('unknown or duplicate transform')
        seen.add(key)
        xyz = node.children[1]
        if not isinstance(xyz, Expression) or len(xyz.children) != 4:
            raise ValueError('xyz requires exactly three numbers')
        if _bare(xyz.children[0]) != 'xyz':
            raise ValueError('expected xyz')
        expected = Decimal('0.3937') if key == 'scale' else Decimal(0)
        for atom in xyz.children[1:]:
            value = _bare(atom)
            if _NUMBER.fullmatch(value) is None or Decimal(value) != expected:
                raise ValueError('unsupported transform value')
    return ModelReference(
        basename=expected_basename, scale=(0.3937, 0.3937, 0.3937),
        zero_translation=True, zero_rotation=True,
        raw_sha256=hashlib.sha256(data).hexdigest(),
    )
