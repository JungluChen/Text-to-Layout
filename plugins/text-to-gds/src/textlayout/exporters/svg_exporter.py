"""SVG exporter — a human-viewable preview of the Geometry IR.

Pure string building (no matplotlib, no cairo). Used by the future ``/preview``
endpoint so ChatGPT can show the user what was generated. The y-axis is flipped
to match SVG's screen coordinates (y grows downward).
"""

from __future__ import annotations

from typing import ClassVar

from textlayout.models import Geometry, Technology
from textlayout.ports.exporter import Exporter

_MARGIN_FRAC = 0.05
_FALLBACK_COLOR = "#888888"


class SvgExporter(Exporter):
    """Renders :class:`Geometry` to a standalone SVG string."""

    format: ClassVar[str] = "svg"
    extension: ClassVar[str] = "svg"

    def __init__(self, *, max_dimension_px: float = 800.0) -> None:
        self._max_px = max_dimension_px

    def render(self, geometry: Geometry, tech: Technology) -> str:
        if geometry.is_empty:
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
                'viewBox="0 0 100 100"></svg>'
            )

        bbox = geometry.bbox()
        margin = _MARGIN_FRAC * max(bbox.width, bbox.height, 1.0)
        vb_x = bbox.xmin - margin
        vb_y = bbox.ymin - margin
        vb_w = bbox.width + 2 * margin
        vb_h = bbox.height + 2 * margin

        scale = self._max_px / max(vb_w, vb_h)
        px_w = round(vb_w * scale, 2)
        px_h = round(vb_h * scale, 2)

        # Flip y: screen_y = (vb_y + vb_h) - (y - vb_y) = vb_y + vb_h + vb_y - y.
        y_flip = 2 * vb_y + vb_h

        parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{px_w}" height="{px_h}" '
            f'viewBox="{_n(vb_x)} {_n(vb_y)} {_n(vb_w)} {_n(vb_h)}">',
            f'<rect x="{_n(vb_x)}" y="{_n(vb_y)}" width="{_n(vb_w)}" height="{_n(vb_h)}" '
            'fill="white"/>',
        ]
        for poly in geometry.polygons:
            color = (
                tech.layer(poly.layer).color if tech.has_layer(poly.layer) else _FALLBACK_COLOR
            )
            pts = " ".join(f"{_n(x)},{_n(y_flip - y)}" for x, y in poly.points)
            parts.append(
                f'<polygon points="{pts}" fill="{color}" fill-opacity="0.6" '
                f'stroke="{color}" stroke-width="{_n(max(vb_w, vb_h) * 0.002)}"/>'
            )
        parts.append("</svg>")
        return "".join(parts)


def _n(value: float) -> str:
    """Format a number compactly and deterministically."""
    return f"{round(value, 4):g}"
