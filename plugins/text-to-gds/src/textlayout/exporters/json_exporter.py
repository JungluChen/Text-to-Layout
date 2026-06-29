"""JSON exporter — a lossless, machine-readable dump of the Geometry IR.

This is the canonical format for ChatGPT/tool consumption: deterministic field
order and rounded coordinates so identical geometry always serialises to an
identical string (golden-test friendly).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from textlayout.models import Geometry, Technology
from textlayout.ports.exporter import Exporter

_ROUND = 4


def _r(value: float) -> float:
    # Normalise -0.0 to 0.0 for stable output.
    return round(value, _ROUND) + 0.0


class JsonExporter(Exporter):
    """Serialises :class:`Geometry` to a stable JSON document."""

    format: ClassVar[str] = "json"
    extension: ClassVar[str] = "json"

    def render(self, geometry: Geometry, tech: Technology) -> str:
        bbox = geometry.bbox() if not geometry.is_empty else None
        doc: dict[str, Any] = {
            "schema": "textlayout.geometry.v1",
            "name": geometry.name,
            "technology": tech.name,
            "bbox_um": (
                None
                if bbox is None
                else {
                    "xmin": _r(bbox.xmin),
                    "ymin": _r(bbox.ymin),
                    "xmax": _r(bbox.xmax),
                    "ymax": _r(bbox.ymax),
                    "width": _r(bbox.width),
                    "height": _r(bbox.height),
                }
            ),
            "layers": [
                {
                    "name": layer,
                    "gds_layer": tech.layer(layer).gds_layer if tech.has_layer(layer) else None,
                    "gds_datatype": tech.layer(layer).gds_datatype if tech.has_layer(layer) else 0,
                    "polygon_count": len(geometry.on_layer(layer)),
                }
                for layer in geometry.layers()
            ],
            "polygons": [
                {
                    "layer": poly.layer,
                    "points": [[_r(x), _r(y)] for x, y in poly.points],
                }
                for poly in geometry.polygons
            ],
            "metadata": dict(geometry.metadata),
        }
        return json.dumps(doc, indent=2, sort_keys=False)
