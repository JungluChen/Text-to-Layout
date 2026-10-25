"""Compose strict QEDA records; structural decoding is not tool acceptance."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from textlayout.external.qeda_graphic import PlanarGraphic, decode_planar_graphic
from textlayout.external.qeda_model import ModelReference, decode_model_reference
from textlayout.external.qeda_pad import RectangularPad, _bare, decode_rectangular_pad
from textlayout.external.qeda_syntax import Expression, parse_footprint_syntax
from textlayout.external.qeda_text import TextAnnotation, decode_text_annotation


@dataclass(frozen=True)
class FootprintModule:
    name: str
    pads: tuple[RectangularPad, ...]
    graphics: tuple[PlanarGraphic, ...]
    annotations: tuple[TextAnnotation, ...]
    model: ModelReference
    raw_sha256: str


def _child_bytes(data: bytes) -> list[bytes]:
    """Locate direct child lists after the caller validated complete syntax."""
    depth = 0
    quoted = escaped = False
    start = 0
    result = []
    for index, byte in enumerate(data):
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte == 40:
            depth += 1
            if depth == 2:
                start = index
        elif byte == 41:
            if depth == 2:
                result.append(data[start:index + 1])
            depth -= 1
    return result


def decode_footprint_module(data: bytes, *, expected_name: str) -> FootprintModule:
    """Decode the audited two-pad QEDA module dialect, consuming every child.

    Require F.Cu/smd, unique pads 1/2, one annotation per supported role, one
    matching model, and supported non-copper graphics. Graphics may vary in count;
    no shape/reference, clearance, VRML or execution acceptance is implied.
    Component hashes cover exact original slices; module hash covers all bytes.
    """
    if re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,127}', expected_name) is None:
        raise ValueError('unsupported expected module name')
    nodes = parse_footprint_syntax(data).children
    if len(nodes) < 2 or _bare(nodes[0]) != 'module' or _bare(nodes[1]) != expected_name:
        raise ValueError('module identity mismatch')
    children = nodes[2:]
    if any(not isinstance(node, Expression) for node in children):
        raise ValueError('unexpected module atom')
    raw_children = _child_bytes(data)
    if len(raw_children) != len(children):
        raise ValueError('child span mismatch')
    pads = []
    graphics = []
    annotations = []
    models = []
    metadata: set[str] = set()
    for node, raw in zip(children, raw_children, strict=True):
        if not isinstance(node, Expression) or not node.children or parse_footprint_syntax(raw) != node:
            raise ValueError('invalid child span')
        kind = _bare(node.children[0])
        if kind in {'layer', 'attr'}:
            expected = 'F.Cu' if kind == 'layer' else 'smd'
            if kind in metadata or len(node.children) != 2 or _bare(node.children[1]) != expected:
                raise ValueError('unsupported or duplicate module metadata')
            metadata.add(kind)
        elif kind == 'pad':
            pads.append(decode_rectangular_pad(raw))
        elif kind in {'fp_line', 'fp_circle'}:
            graphics.append(decode_planar_graphic(raw))
        elif kind == 'fp_text':
            if len(node.children) < 2:
                raise ValueError('missing text role')
            expected_text = expected_name if _bare(node.children[1]) == 'value' else 'REF**'
            annotations.append(decode_text_annotation(raw, expected_text=expected_text))
        elif kind == 'model':
            models.append(decode_model_reference(raw, expected_basename=expected_name + '.wrl'))
        else:
            raise ValueError('unsupported module child')
    if metadata != {'layer', 'attr'} or sorted(p.number for p in pads) != [1, 2]:
        raise ValueError('missing metadata or duplicate/missing pad identity')
    if sorted(a.role for a in annotations) != ['reference', 'user', 'value'] or len(models) != 1:
        raise ValueError('missing or duplicate annotation/model identity')
    return FootprintModule(
        name=expected_name, pads=tuple(pads), graphics=tuple(graphics),
        annotations=tuple(annotations), model=models[0],
        raw_sha256=hashlib.sha256(data).hexdigest(),
    )
