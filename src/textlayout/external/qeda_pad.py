"""Decode one supported QEDA pad; not footprint or reference acceptance."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from textlayout.external.qeda_syntax import Atom, Expression, parse_footprint_syntax

_DECIMAL = re.compile(r"[+-]?[0-9]{1,4}(?:\.[0-9]{1,9})?\Z")


@dataclass(frozen=True)
class RectangularPad:
    number: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    solder_mask_margin_mm: float
    raw_sha256: str


def _bare(node: Atom | Expression) -> str:
    if not isinstance(node, Atom) or node.quoted:
        raise ValueError("expected unquoted atom")
    return node.value


def _dimension(node: Atom | Expression, *, positive: bool = False) -> float:
    value = _bare(node)
    if _DECIMAL.fullmatch(value) is None:
        raise ValueError("dimension must be bounded decimal millimetres")
    number = float(value)
    if abs(number) > 1000 or (positive and number <= 0):
        raise ValueError("dimension out of supported range")
    return number


def decode_rectangular_pad(data: bytes) -> RectangularPad:
    """Decode one unrotated F.Cu SMD rectangular pad numbered 1 or 2.

    Required fields: at, size, layers, solder_mask_margin, each exactly once.
    Unknown fields (including drill), quoted numbers, exponents, non-finite
    values and dimensions beyond +/-1000 mm fail closed with ValueError.
    Positive sizes have at most nine fractional decimal digits. This is a
    supported input domain, not a scientific error tolerance. The raw hash
    identifies these bytes only, not a solver or execution provenance chain.
    """
    children = parse_footprint_syntax(data).children
    if len(children) != 8:
        raise ValueError("pad requires four atoms and four fields")
    head = tuple(_bare(node) for node in children[:4])
    if head[0] != "pad" or head[1] not in {"1", "2"} or head[2:] != ("smd", "rect"):
        raise ValueError("unsupported pad identity/type/shape")
    fields: dict[str, tuple[Atom | Expression, ...]] = {}
    for node in children[4:]:
        if not isinstance(node, Expression) or not node.children:
            raise ValueError("expected named field")
        key = _bare(node.children[0])
        if key in fields:
            raise ValueError("duplicate pad field")
        fields[key] = node.children[1:]
    if set(fields) != {"at", "size", "layers", "solder_mask_margin"}:
        raise ValueError("unsupported or missing pad field")
    if len(fields["at"]) != 2 or len(fields["size"]) != 2:
        raise ValueError("pad position/size must have two dimensions; rotation unsupported")
    if tuple(_bare(node) for node in fields["layers"]) != ("F.Cu", "F.Mask", "F.Paste"):
        raise ValueError("unsupported pad layers")
    if len(fields["solder_mask_margin"]) != 1:
        raise ValueError("mask margin must have one dimension")
    margin = _dimension(fields["solder_mask_margin"][0])
    if margin < 0:
        raise ValueError("negative mask margin unsupported")
    return RectangularPad(
        number=int(head[1]),
        x_mm=_dimension(fields["at"][0]),
        y_mm=_dimension(fields["at"][1]),
        width_mm=_dimension(fields["size"][0], positive=True),
        height_mm=_dimension(fields["size"][1], positive=True),
        solder_mask_margin_mm=margin,
        raw_sha256=hashlib.sha256(data).hexdigest(),
    )
