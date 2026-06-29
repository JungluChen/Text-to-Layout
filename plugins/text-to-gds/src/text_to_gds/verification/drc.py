"""Fabrication rule checks derived from GDS polygons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.geometry.polygon import layer_regions
from text_to_gds.pdk.layers import PHYSICAL_LAYERS, layer_name
from text_to_gds.pdk.rules import DEFAULT_FABRICATION_RULES


def run_drc(path: str | Path) -> dict[str, Any]:
    regions = layer_regions(path)
    rules = DEFAULT_FABRICATION_RULES
    errors: list[str] = []
    warnings: list[str] = []
    for layer, item in regions.items():
        name = layer_name(layer)
        if not PHYSICAL_LAYERS.get(name, None):
            warnings.append(f"unknown layer {layer[0]}/{layer[1]}")
            continue
        if name in {"M1", "M2", "M3"} and item.region.count() == 0:
            errors.append(f"{name} has no conductive polygons")
    if PHYSICAL_LAYERS["JJ"].layer in regions:
        for poly in regions[PHYSICAL_LAYERS["JJ"].layer].region.each():
            box = poly.bbox()
            width = abs(box.right - box.left)
            height = abs(box.top - box.bottom)
            if width <= 0 or height <= 0:
                errors.append("degenerate JJ polygon")
            if width < rules.minimum_jj_size_um or height < rules.minimum_jj_size_um:
                warnings.append("JJ bbox below nominal process size after database-unit readback")
    return {
        "schema": "text-to-gds.drc.v1",
        "gds_path": str(path),
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "checks": ["known_layers", "conductive_presence", "jj_bbox_nonzero"],
    }

