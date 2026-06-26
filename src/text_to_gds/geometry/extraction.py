"""GDS-derived superconducting layout extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.geometry.polygon import layer_regions
from text_to_gds.pdk.layers import PHYSICAL_LAYERS, layer_name


def extract_layer_features(path: str | Path) -> dict[str, Any]:
    regions = layer_regions(path)
    features: dict[str, Any] = {
        "schema": "text-to-gds.geometry-extraction.v1",
        "gds_path": str(path),
        "layers": {},
    }
    for layer, item in sorted(regions.items()):
        name = layer_name(layer)
        spec = next((p for p in PHYSICAL_LAYERS.values() if p.layer == layer), None)
        features["layers"][name] = {
            "layer": [layer[0], layer[1]],
            "role": spec.role if spec else "unknown",
            "conductive": bool(spec.conductive) if spec else False,
            "polygon_count": item.polygon_count,
            "area_database_units": item.area_um2,
        }
    return features

