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
        if not ((x0 == x1 and y0 != y1) or (y0 == y1 and x0 != x1)):
            raise ValueError(f"Path segment must be non-zero and orthogonal: {start} -> {end}")
        # Sort the centerline endpoints BEFORE expanding them. Expanding first
        # shortens a reversed segment and disconnects its corner joins.
        polygons.append(rectangle(layer, min(x0, x1) - half, min(y0, y1) - half,
                                  max(x0, x1) + half, max(y0, y1) + half))
    return tuple(polygons)


def path_length(points: Sequence[Point]) -> float:
    """Return Manhattan centerline length."""
    return sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:], strict=False)
    )
