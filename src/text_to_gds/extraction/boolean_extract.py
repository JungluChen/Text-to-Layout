"""Boolean geometry extraction using klayout.db."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Layer = tuple[int, int]


@dataclass
class PolygonRecord:
    """One polygon resulting from a boolean operation."""

    vertices: list[tuple[float, float]]
    area_um2: float
    bbox_um: tuple[float, float, float, float]
    layer: Layer
    source: str = "klayout.db"
    method: str = "extracted"


@dataclass
class Finding:
    """A single check result (pass/fail with detail)."""

    passed: bool
    message: str
    severity: str = "error"
    extra: dict[str, Any] = field(default_factory=dict)


def _load_region(layout: Any, layer_tuple: Layer) -> Any:
    """Build a klayout Region for all shapes on the given layer."""
    import klayout.db as kdb

    region = kdb.Region()
    for li in layout.layer_indices():
        info = layout.get_info(li)
        if (int(info.layer), int(info.datatype)) == layer_tuple:
            top = layout.top_cell()
            if top is not None:
                region.insert(top.begin_shapes_rec(li))
            else:
                for cell in layout.each_cell():
                    region.insert(cell.shapes(li))
    return region


def _region_to_records(region: Any, dbu: float, layer: Layer) -> list[PolygonRecord]:
    """Convert a klayout Region to a list of PolygonRecord."""
    records: list[PolygonRecord] = []
    for poly in region.each():
        hull = poly.hull()
        verts = [(float(pt.x) * dbu, float(pt.y) * dbu) for pt in hull.each_point()]
        area = float(poly.area()) * dbu * dbu
        bbox = poly.bbox()
        bbox_um = (
            float(bbox.left) * dbu,
            float(bbox.bottom) * dbu,
            float(bbox.right) * dbu,
            float(bbox.top) * dbu,
        )
        records.append(PolygonRecord(
            vertices=verts,
            area_um2=area,
            bbox_um=bbox_um,
            layer=layer,
        ))
    return records


def boolean_overlap(
    gds_path: str | Path,
    layer_a: Layer,
    layer_b: Layer,
) -> list[PolygonRecord]:
    """Compute layer_a AND layer_b, return overlap polygons."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    region_a = _load_region(layout, layer_a)
    region_b = _load_region(layout, layer_b)
    overlap = region_a & region_b
    return _region_to_records(overlap, dbu, layer_a)


def boolean_subtract(
    gds_path: str | Path,
    layer_base: Layer,
    layer_cut: Layer,
) -> list[PolygonRecord]:
    """Compute layer_base - layer_cut, return remaining polygons."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    region_base = _load_region(layout, layer_base)
    region_cut = _load_region(layout, layer_cut)
    result = region_base - region_cut
    return _region_to_records(result, dbu, layer_base)


def check_no_accidental_overlap(
    gds_path: str | Path,
    layer_a: Layer,
    layer_b: Layer,
    expected_regions: int,
) -> list[Finding]:
    """Verify only the expected number of overlap regions exist."""
    overlaps = boolean_overlap(gds_path, layer_a, layer_b)
    findings: list[Finding] = []
    actual = len(overlaps)
    if actual != expected_regions:
        findings.append(Finding(
            passed=False,
            message=(
                f"Expected {expected_regions} overlap region(s) between "
                f"L{layer_a[0]} and L{layer_b[0]}, found {actual}"
            ),
            severity="error",
            extra={"expected": expected_regions, "actual": actual},
        ))
    else:
        findings.append(Finding(
            passed=True,
            message=f"Overlap count matches: {actual} region(s)",
            severity="info",
        ))
    return findings
