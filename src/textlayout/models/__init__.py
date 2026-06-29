"""Domain entities (pure value objects, dependency-free)."""

from __future__ import annotations

from textlayout.models.geometry import (
    BoundingBox,
    Geometry,
    Point,
    Polygon,
    Port,
    rectangle,
)
from textlayout.models.technology import LayerInfo, Technology

__all__ = [
    "BoundingBox",
    "Geometry",
    "LayerInfo",
    "Point",
    "Polygon",
    "Port",
    "Technology",
    "rectangle",
]
