"""Independent check of the explicit 2 mm Quantum Metal transmon mask fixture.

This checks two charge pads and a ground-plane cutout only. It does not verify
or supply a fabrication junction, electrical model, connectivity or signoff.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path

import klayout.db as kdb


from textlayout.external.quantum_metal_mask import TransmonMaskRequest


def check_mask(path: Path, request: TransmonMaskRequest) -> dict[str, object]:
    """Fail closed on empty exports, wrong layers, scale or polygon geometry."""
    layout = kdb.Layout()
    layout.read(str(path))
    tops = list(layout.top_cells())
    report: dict[str, object] = {
        "schema": "textlayout.quantum-metal-transmon-mask.v1",
        "scope": "charge-pad and ground-pocket mask only",
        "request": request.model_dump(),
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reader": "KLayout",
        "reader_version": importlib.metadata.version("klayout"),
        "database_grid_um": layout.dbu,
        "top_cell_count": len(tops),
        "geometry_verified": False,
        "junction_verified": False,
        "electrical_validation": "NOT_EVALUATED",
        "limitations": ["No fabrication junction supplied", "No electrical solver executed"],
    }
    if len(tops) != 1 or layout.dbu != 0.001:
        report["failure_reason"] = "Expected one top cell and a 1 nm database grid"
        return report
    # Explicit integer-nanometre rectangle reference, independent of upstream
    # QComponent/gdstk construction. Exact XOR is required on this fixed grid.
    nm = {k: round(v * 1000) for k, v in request.model_dump().items()}
    w, h, gap = nm["pad_width_um"], nm["pad_height_um"], nm["pad_gap_um"]
    pads = kdb.Region(kdb.Box(-w // 2, gap // 2, w // 2, gap // 2 + h))
    pads += kdb.Region(kdb.Box(-w // 2, -gap // 2 - h, w // 2, -gap // 2))
    cw, ch = nm["chip_width_um"], nm["chip_height_um"]
    pw, ph = nm["pocket_width_um"], nm["pocket_height_um"]
    ground = kdb.Region(kdb.Box(-cw // 2, -ch // 2, cw // 2, ch // 2))
    ground -= kdb.Region(kdb.Box(-pw // 2, -ph // 2, pw // 2, ph // 2))
    expected = {(1, 10): pads, (1, 0): ground}
    actual = {}
    for layer in layout.layer_indexes():
        region = kdb.Region(tops[0].begin_shapes_rec(layer))
        if not region.is_empty():
            info = layout.get_info(layer)
            actual[(info.layer, info.datatype)] = region
    layer_match = set(actual) == set(expected)
    comparisons = []
    for key, reference in expected.items():
        region = actual.get(key, kdb.Region())
        xor = (region ^ reference).area()
        comparisons.append(
            {
                "layer": key[0],
                "datatype": key[1],
                "xor_area_nm2": xor,
                "accepted_xor_area_nm2": 0,
                "actual_area_um2": region.merged().area() * 1e-6,
                "reference_area_um2": reference.area() * 1e-6,
            }
        )
    report["actual_layers"] = sorted([list(key) for key in actual])
    report["layer_map_match"] = layer_match
    report["comparisons"] = comparisons
    report["geometry_verified"] = layer_match and all(c["xor_area_nm2"] == 0 for c in comparisons)
    if not report["geometry_verified"]:
        report["failure_reason"] = "Export differs from declared mask geometry or layer mapping"
    return report
