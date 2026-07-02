"""PNG raster preview via matplotlib (thread-safe OO API, no pyplot global state).

Used for the README benchmark gallery so readers see an actual image. Imported
lazily so the core/JSON/SVG paths never pay the matplotlib import cost.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import ClassVar

from textlayout.errors import ExportError
from textlayout.models import Geometry, Technology
from textlayout.ports.exporter import Exporter

_FALLBACK_COLOR = "#888888"

# Pin PNG metadata so the only run-to-run variation is matplotlib's own
# rasteriser version. By default matplotlib stamps a "Software: Matplotlib
# <version>" chunk; fixing it keeps the committed previews stable as long as the
# matplotlib version is held. (See docs/artifact_policy.md.)
_PNG_METADATA = {"Software": "textlayout"}


class PngExporter(Exporter):
    """Renders the Geometry IR to a PNG image."""

    format: ClassVar[str] = "png"
    extension: ClassVar[str] = "png"
    binary: ClassVar[bool] = True

    def __init__(self, *, dpi: int = 150) -> None:
        self._dpi = dpi

    def render(self, geometry: Geometry, tech: Technology) -> str:
        raise ExportError("PNG is a binary format; use write() or render_bytes().")

    def render_bytes(self, geometry: Geometry, tech: Technology) -> bytes:
        buf = io.BytesIO()
        self._figure(geometry, tech).savefig(
            buf, format="png", dpi=self._dpi, bbox_inches="tight", metadata=_PNG_METADATA
        )
        return buf.getvalue()

    def write(self, geometry: Geometry, tech: Technology, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self._figure(geometry, tech).savefig(
            out, dpi=self._dpi, bbox_inches="tight", metadata=_PNG_METADATA
        )
        return out

    def _figure(self, geometry: Geometry, tech: Technology):  # type: ignore[no-untyped-def]
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.patches import Polygon as MplPolygon

        fig = Figure(figsize=(6, 6))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        for poly in geometry.polygons:
            color = tech.layer(poly.layer).color if tech.has_layer(poly.layer) else _FALLBACK_COLOR
            ax.add_patch(
                MplPolygon(
                    list(poly.points),
                    closed=True,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.6,
                    linewidth=0.3,
                )
            )
        if not geometry.is_empty:
            box = geometry.bbox()
            m = 0.05 * max(box.width, box.height, 1.0)
            ax.set_xlim(box.xmin - m, box.xmax + m)
            ax.set_ylim(box.ymin - m, box.ymax + m)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"{geometry.name}  ({tech.name})", fontsize=9)
        return fig
