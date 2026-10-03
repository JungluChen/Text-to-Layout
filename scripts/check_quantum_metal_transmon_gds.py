"""Independent check of the explicit 2 mm Quantum Metal transmon mask fixture.

This checks two charge pads and a ground-plane cutout only. It does not verify
or supply a fabrication junction, electrical model, connectivity or signoff.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import klayout.db as kdb


def check(path: Path) -> dict[str, object]:
    """Fail closed on empty exports, wrong layers, scale or polygon geometry."""
    layout = kdb.Layout()
    layout.read(str(path))
    tops = list(layout.top_cells())
    report: dict[str, object] = {
        "schema": "textlayout.quantum-metal-transmon-mask.v1",
        "scope": "fixed 2 mm chip, 455 x 90 um pads, 30 um gap, 650 um pocket; mask only",
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
    pads = kdb.Region(kdb.Box(-227500, 15000, 227500, 105000))
    pads += kdb.Region(kdb.Box(-227500, -105000, 227500, -15000))
    ground = kdb.Region(kdb.Box(-1000000, -1000000, 1000000, 1000000))
    ground -= kdb.Region(kdb.Box(-325000, -325000, 325000, 325000))
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gds", type=Path)
    parser.add_argument(
        "--out", type=Path, required=True, help="New report path; never overwrite evidence"
    )
    args = parser.parse_args()
    report = check(args.gds)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["geometry_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
