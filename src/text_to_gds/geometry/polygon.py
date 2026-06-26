"""Polygon loading helpers backed by KLayout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import klayout.db as kdb


@dataclass(frozen=True)
class LayerRegion:
    layer: tuple[int, int]
    region: kdb.Region

    @property
    def polygon_count(self) -> int:
        return int(self.region.count())

    @property
    def area_um2(self) -> float:
        return float(sum(poly.area() for poly in self.region.each()))


def load_layout(path: str | Path) -> tuple[kdb.Layout, kdb.Cell]:
    layout = kdb.Layout()
    layout.read(str(path))
    top = layout.top_cell()
    if top is None:
        raise ValueError(f"GDS has no top cell: {path}")
    return layout, top


def layer_regions(path: str | Path) -> dict[tuple[int, int], LayerRegion]:
    layout, top = load_layout(path)
    regions: dict[tuple[int, int], LayerRegion] = {}
    for layer_index in layout.layer_indexes():
        info = layout.get_info(layer_index)
        # Materialise explicitly from the recursive shape iterator. Building a
        # Region directly from ``begin_shapes_rec`` leaves it deferred against
        # the iterator; for a layer holding a *single* polygon ``.merged()`` then
        # evaluates to empty, which silently dropped every single-polygon layer
        # (e.g. a lone via). Inserting each shape with its transform forces an
        # independent, correct region.
        region = kdb.Region()
        shape_iter = top.begin_shapes_rec(layer_index)
        while not shape_iter.at_end():
            shape = shape_iter.shape()
            poly = None
            if shape.is_box():
                poly = kdb.Polygon(shape.box)
            elif shape.is_path():
                poly = shape.path.polygon()
            elif shape.is_polygon() or shape.is_simple_polygon():
                poly = shape.polygon
            if poly is not None:
                region.insert(poly.transformed(shape_iter.trans()))
            shape_iter.next()
        region.merge()
        if not region.is_empty():
            regions[(info.layer, info.datatype)] = LayerRegion((info.layer, info.datatype), region)
    return regions


def summarize_layers(path: str | Path) -> dict[str, Any]:
    return {
        f"{layer[0]}/{layer[1]}": {
            "polygon_count": item.polygon_count,
            "area_um2_database_units": item.area_um2,
        }
        for layer, item in sorted(layer_regions(path).items())
    }

