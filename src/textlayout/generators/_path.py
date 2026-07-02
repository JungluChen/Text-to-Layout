"""Small deterministic Manhattan-path geometry helpers."""

from __future__ import annotations

from collections.abc import Sequence

from textlayout.models import Point, Polygon, rectangle


def orthogonal_path_rectangles(
    layer: str, points: Sequence[Point], width: float
) -> tuple[Polygon, ...]:
    """Render an orthogonal centerline as overlapping axis-aligned rectangles."""
    polygons: list[Polygon] = []
    half = width / 2.0
    for start, end in zip(points, points[1:], strict=False):
        x0, y0 = start
        x1, y1 = end
        if x0 == x1 and y0 != y1:
            polygons.append(rectangle(layer, x0 - half, y0 - half, x1 + half, y1 + half))
        elif y0 == y1 and x0 != x1:
            polygons.append(rectangle(layer, x0 - half, y0 - half, x1 + half, y1 + half))
        else:
            raise ValueError(f"Path segment must be non-zero and orthogonal: {start} -> {end}")
    return tuple(polygons)


def path_length(points: Sequence[Point]) -> float:
    """Return Manhattan centerline length."""
    return sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:], strict=False)
    )
