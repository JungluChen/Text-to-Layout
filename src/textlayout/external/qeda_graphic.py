"""Strict planar drawing records; no whole-footprint acceptance."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from textlayout.external.qeda_pad import _bare, _dimension
from textlayout.external.qeda_syntax import Atom, Expression, parse_footprint_syntax


@dataclass(frozen=True)
class PlanarGraphic:
    kind: Literal['fp_line', 'fp_circle']
    layer: str
    origin_mm: tuple[float, float]  # line start or circle centre
    end_mm: tuple[float, float]  # line endpoint or point on circle
    width_mm: float
    raw_sha256: str


def decode_planar_graphic(data: bytes) -> PlanarGraphic:
    """Decode one line/circle on F.SilkS, F.Fab or F.CrtYd.

    All fields are explicit and unique. Coordinates follow the bounded decimal
    millimetre domain used for pads. Degenerate lines/circles, nonpositive widths,
    copper layers and unknown/nested fields raise ValueError. No reference,
    clearance, full-module or fabrication acceptance is implied.
    """
    children = parse_footprint_syntax(data).children
    if len(children) != 5:
        raise ValueError('graphic requires kind and four fields')
    kind = _bare(children[0])
    if kind not in {'fp_line', 'fp_circle'}:
        raise ValueError('unsupported graphic kind')
    fields: dict[str, tuple[Atom | Expression, ...]] = {}
    for child in children[1:]:
        if not isinstance(child, Expression) or not child.children:
            raise ValueError('expected named graphic field')
        key = _bare(child.children[0])
        if key in fields:
            raise ValueError('duplicate graphic field')
        fields[key] = child.children[1:]
    origin_key = 'start' if kind == 'fp_line' else 'center'
    if set(fields) != {origin_key, 'end', 'layer', 'width'}:
        raise ValueError('unknown or missing graphic field')
    if len(fields['layer']) != 1 or len(fields['width']) != 1:
        raise ValueError('layer and width require one atom each')
    layer = _bare(fields['layer'][0])
    if layer not in {'F.SilkS', 'F.Fab', 'F.CrtYd'}:
        raise ValueError('unsupported or conductive drawing layer')
    points = []
    for key in (origin_key, 'end'):
        if len(fields[key]) != 2:
            raise ValueError('point requires two coordinates')
        points.append((_dimension(fields[key][0]), _dimension(fields[key][1])))
    if points[0] == points[1]:
        raise ValueError('degenerate graphic')
    return PlanarGraphic(
        kind='fp_line' if kind == 'fp_line' else 'fp_circle', layer=layer,
        origin_mm=points[0], end_mm=points[1],
        width_mm=_dimension(fields['width'][0], positive=True),
        raw_sha256=hashlib.sha256(data).hexdigest(),
    )
