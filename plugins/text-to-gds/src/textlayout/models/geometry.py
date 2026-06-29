"""Pure geometry domain entities — the *Geometry IR*.

These are deliberately plain, immutable ``dataclass`` value objects with **zero
dependencies** (no pydantic, no gdsfactory, no numpy). They are the lingua franca
between the geometry engine (which produces them) and the exporters/validators
(which consume them). Keeping them dependency-free is what lets the same IR be
exported to GDS, SVG, or JSON without coupling the domain to any vendor library.

Coordinates are expressed in **micrometres (µm)** as ``float``. Exporters are
responsible for converting to database units (e.g. nanometres for GDSII).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Point = tuple[float, float]
"""A 2-D coordinate ``(x, y)`` in micrometres."""


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """An axis-aligned bounding box in micrometres."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)

    def merge(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min(self.xmin, other.xmin),
            min(self.ymin, other.ymin),
            max(self.xmax, other.xmax),
            max(self.ymax, other.ymax),
        )

    @classmethod
    def from_points(cls, points: Iterable[Point]) -> BoundingBox:
        pts = list(points)
        if not pts:
            raise ValueError("Cannot build a bounding box from zero points")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return cls(min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True, slots=True)
class Polygon:
    """A closed polygon assigned to a named layer.

    ``points`` is the ordered vertex list; it must not repeat the first point at
    the end (the polygon is implicitly closed).
    """

    layer: str
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError(
                f"Polygon on layer {self.layer!r} needs >= 3 vertices, got {len(self.points)}"
            )

    @property
    def bbox(self) -> BoundingBox:
        return BoundingBox.from_points(self.points)


@dataclass(frozen=True, slots=True)
class Port:
    """An electrical/connection port, used for routing and EM port assignment.

    ``orientation`` is in degrees (0 = +x/east, 90 = +y/north, 180 = west,
    270 = south), matching gdsfactory's convention.
    """

    name: str
    center: Point
    width: float
    orientation: float
    layer: str


@dataclass(frozen=True, slots=True)
class Geometry:
    """An immutable collection of layered polygons — the output of a generator."""

    name: str
    polygons: tuple[Polygon, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    ports: tuple[Port, ...] = ()

    @property
    def is_empty(self) -> bool:
        return len(self.polygons) == 0

    def layers(self) -> tuple[str, ...]:
        """Distinct layer names, sorted for deterministic output."""
        return tuple(sorted({p.layer for p in self.polygons}))

    def on_layer(self, layer: str) -> tuple[Polygon, ...]:
        return tuple(p for p in self.polygons if p.layer == layer)

    def bbox(self) -> BoundingBox:
        if self.is_empty:
            raise ValueError(f"Geometry {self.name!r} is empty; no bounding box")
        box = self.polygons[0].bbox
        for poly in self.polygons[1:]:
            box = box.merge(poly.bbox)
        return box

    def area_on(self, layer: str) -> float:
        """Sum of polygon areas on ``layer`` (shoelace formula)."""
        return sum(_shoelace_area(p.points) for p in self.on_layer(layer))


def rectangle(layer: str, x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """Convenience constructor for an axis-aligned rectangle polygon."""
    xlo, xhi = sorted((x0, x1))
    ylo, yhi = sorted((y0, y1))
    return Polygon(
        layer=layer,
        points=((xlo, ylo), (xhi, ylo), (xhi, yhi), (xlo, yhi)),
    )


def _shoelace_area(points: Sequence[Point]) -> float:
    n = len(points)
    acc = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        acc += x0 * y1 - x1 * y0
    return abs(acc) / 2.0
