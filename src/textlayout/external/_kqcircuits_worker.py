"""External-process geometry worker; no upstream source or physics is included.

Run in the dedicated environment documented in docs/integrations/kqcircuits.md.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import importlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    # External libraries are deliberately absent from product-core imports.
    gdstk = importlib.import_module("gdstk")
    WaveguideCoplanarStraight = importlib.import_module(
        "kqcircuits.elements.waveguide_coplanar_straight"
    ).WaveguideCoplanarStraight
    pya = importlib.import_module("kqcircuits.pya_resolver").pya

    versions = {
        name: importlib.metadata.version(name) for name in ("kqcircuits", "klayout", "gdstk")
    }
    expected_versions = {"kqcircuits": "4.9.11", "klayout": "0.30.12", "gdstk": "0.9.61"}
    if versions != expected_versions:
        raise ValueError(f"Unexpected acceptance toolchain: {versions}")
    args.out.mkdir(parents=True, exist_ok=False)
    results = []
    # Expectations are declared before execution, in micrometres. The second
    # case checks parameter mapping instead of merely reproducing defaults.
    cases = [(1000.0, 10.0, 6.0), (250.0, 20.0, 8.0)]
    if args.request:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        cases = [(request["length_um"], request["width_um"], request["gap_um"])]
    for index, (length, width, gap) in enumerate(cases):
        layout = pya.Layout()
        layout.dbu = 0.001
        cell = WaveguideCoplanarStraight.create(layout, l=length, a=width, b=gap)
        path = args.out / f"case-{index}.gds"
        cell.write(str(path))
        library = gdstk.read_gds(str(path))
        gap_layer = next(
            info for info in layout.layer_infos() if info.name == "1t1_base_metal_gap_wo_grid"
        )
        polygons = [
            p
            for c in library.top_level()
            for p in c.get_polygons()
            if (p.layer, p.datatype) == (gap_layer.layer, gap_layer.datatype)
        ]
        reference = [
            gdstk.rectangle((0, width / 2), (length, width / 2 + gap)),
            gdstk.rectangle((0, -width / 2 - gap), (length, -width / 2)),
        ]
        residual = gdstk.boolean(polygons, reference, "xor", precision=layout.dbu)
        xor_area = sum(p.area() for p in residual)
        area = sum(p.area() for p in polygons)
        # Grid-aligned rectangles have zero expected XOR at the 1 nm database
        # grid. This is an exact mask check, not an EM error tolerance.
        passed = (
            library.unit == 1e-6
            and library.precision == 1e-9
            and len(polygons) == 2
            and xor_area == 0
            and abs(area - 2 * length * gap) <= layout.dbu**2
        )
        results.append(
            {
                "length_um": length,
                "width_um": width,
                "gap_um": gap,
                "gap_layer": [gap_layer.layer, gap_layer.datatype],
                "database_grid_um": layout.dbu,
                "gds_unit_m": library.unit,
                "gds_precision_m": library.precision,
                "gap_polygon_count": len(polygons),
                "gap_area_um2": area,
                "reference_gap_area_um2": 2 * length * gap,
                "xor_area_um2": xor_area,
                "accepted_xor_area_um2": 0,
                "geometry_check_passed": passed,
                "gds_file": path.name,
                "gds_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    report = {
        "schema": "textlayout.kqcircuits-geometry-acceptance.v1",
        "scope": "straight CPW gap masks only; no EM simulation or fabrication signoff",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "versions": versions,
        "source_revision": "14483b00d20a4033971d08b99428b4ec9ace9d58",
        "dependencies": sorted(
            f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()
        ),
        "cases": results,
        "passed": all(c["geometry_check_passed"] for c in results),
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
