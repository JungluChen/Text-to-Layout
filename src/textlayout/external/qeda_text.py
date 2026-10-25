"""Decode supported non-copper QEDA annotation records, not whole footprints."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from textlayout.external.qeda_pad import _bare, _dimension
from textlayout.external.qeda_syntax import Atom, Expression, parse_footprint_syntax


@dataclass(frozen=True)
class TextAnnotation:
    role: str
    text: str
    layer: str
    hidden: bool
    position_mm: tuple[float, float]
    font_size_mm: tuple[float, float]
    thickness_mm: float
    raw_sha256: str


def _fields(nodes: tuple[Atom | Expression, ...], required: set[str]) -> dict[str, tuple[Atom | Expression, ...]]:
    fields: dict[str, tuple[Atom | Expression, ...]] = {}
    for node in nodes:
        if not isinstance(node, Expression) or not node.children:
            raise ValueError('expected named annotation field')
        key = _bare(node.children[0])
        if key in fields or key not in required:
            raise ValueError('unknown or duplicate annotation field')
        fields[key] = node.children[1:]
    if set(fields) != required:
        raise ValueError('missing annotation field')
    return fields


def decode_text_annotation(data: bytes, *, expected_text: str) -> TextAnnotation:
    """Require explicit text identity and supported reference/value/user shape.

    Reference: visible F.SilkS; value: visible F.Fab; user: hidden F.Fab.
    Reference/user text is REF**; value is an ASCII identifier. Only zero angle
    (explicit or omitted) is supported. Dimensions follow the bounded pad mm
    domain. Every effects/font node is consumed; no unknown nesting is ignored.
    No clearance, readability, reference geometry or execution acceptance.
    """
    if expected_text != 'REF**' and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,127}', expected_text) is None:
        raise ValueError('unsupported expected text')
    nodes = parse_footprint_syntax(data).children
    if len(nodes) < 3 or _bare(nodes[0]) != 'fp_text':
        raise ValueError('expected fp_text')
    role, text = _bare(nodes[1]), _bare(nodes[2])
    if role not in {'reference', 'value', 'user'} or text != expected_text:
        raise ValueError('unsupported role or mismatched text')
    if (role in {'reference', 'user'}) != (text == 'REF**'):
        raise ValueError('unsupported role/text combination')
    # The pinned emitter places hide immediately after at, only for user text.
    rest = nodes[3:]
    hidden = role == 'user'
    if hidden:
        if len(rest) != 4 or not isinstance(rest[1], Atom) or _bare(rest[1]) != 'hide':
            raise ValueError('user text requires explicit hide after at')
        if not isinstance(rest[0], Expression) or not rest[0].children or _bare(rest[0].children[0]) != 'at':
            raise ValueError('expected at before hide')
        rest = (rest[0], *rest[2:])
    fields = _fields(rest, {'at', 'layer', 'effects'})
    layer = 'F.SilkS' if role == 'reference' else 'F.Fab'
    if len(fields['layer']) != 1 or _bare(fields['layer'][0]) != layer:
        raise ValueError('unsupported annotation layer')
    at = fields['at']
    if len(at) not in {2, 3} or (len(at) == 3 and _dimension(at[2]) != 0):
        raise ValueError('only two coordinates with optional zero angle supported')
    font = _fields(fields['effects'], {'font'})['font']
    metrics = _fields(font, {'size', 'thickness'})
    if len(metrics['size']) != 2 or len(metrics['thickness']) != 1:
        raise ValueError('invalid font metric dimensions')
    return TextAnnotation(
        role=role, text=text, layer=layer, hidden=hidden,
        position_mm=(_dimension(at[0]), _dimension(at[1])),
        font_size_mm=(_dimension(metrics['size'][0], positive=True), _dimension(metrics['size'][1], positive=True)),
        thickness_mm=_dimension(metrics['thickness'][0], positive=True),
        raw_sha256=hashlib.sha256(data).hexdigest(),
    )
