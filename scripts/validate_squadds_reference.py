"""Fetch pinned WM1 paper assets and validate all original GDS top variants.

Only source data is downloaded; no notebook or upstream code is executed.
GDS and exports stay in ignored local directories. This checks mask geometry,
not reproduction of the paper's measured electrical performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from textlayout.verification.reference_gds import roundtrip_reference_gds

DB_REV = "0e25705f54c343fb96571ff15b6fd8375ca899aa"
GDS_REV = "5329ff178980c16a299caa4804a2e5251e326833"
ASSETS = {
    "measured_device_database.json": {
        "url": f"https://huggingface.co/datasets/SQuADDS/SQuADDS_DB/resolve/{DB_REV}/measured_device_database.json",
        "sha256": "898a27f0eadaf687129a7bb85971f891c967515764dc7d27f684e669edea1069",
        "revision": DB_REV,
        "license": "MIT (SQuADDS_DB dataset card)",
    },
    "wm1.gds": {
        "url": f"https://raw.githubusercontent.com/LFL-Lab/design_schema_WM1/{GDS_REV}/assets/wm1.gds",
        "sha256": "a327c3064e16864fb9ea8e19a766eaa2c852d57ac7e0b8d5fb97c7a3d4839a5f",
        "revision": GDS_REV,
        "license": "No license file found in this pinned design repository; local reference only",
    },
}
TOPS = ("TOP", "TOP$1", "TOP$2", "TOP$3")


def verified_asset(name: str, cache: Path, *, offline: bool) -> Path:
    asset = ASSETS[name]
    path = cache / name
    if path.exists():
        payload = path.read_bytes()
    elif offline:
        raise ValueError(f"Missing cached asset {path}; run once without --offline")
    else:
        with urlopen(asset["url"], timeout=60) as response:  # noqa: S310
            payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise ValueError(f"Reference asset exceeds the 1 MiB download limit: {name}")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != asset["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {name}: expected {asset['sha256']}, got {digest}")
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".download")
        temporary.write_bytes(payload)
        temporary.replace(path)
    return path


def validate(cache: Path, out: Path, *, offline: bool) -> dict:
    import klayout.db as kdb

    measured = verified_asset("measured_device_database.json", cache, offline=offline)
    gds = verified_asset("wm1.gds", cache, offline=offline)
    records = json.loads(measured.read_text())
    wm1 = next(row for row in records if row["contrib_info"]["name"] == "WM1")
    values = wm1["measured_results"][0]["H_params"][0]
    if set(values) != {f"qubit_{i}" for i in range(1, 7)}:
        raise ValueError("WM1 measurement population differs from the six-device protocol")
    layout = kdb.Layout()
    layout.read(str(gds))
    if {cell.name for cell in layout.top_cells()} != set(TOPS):
        raise ValueError("WM1 top-cell population differs from the four-variant protocol")
    out.mkdir(parents=True, exist_ok=True)
    comparisons = []
    for index, cell in enumerate(TOPS):
        folder = out / f"variant_{index}"
        result = roundtrip_reference_gds(gds, folder / "output.gds", cell=cell)
        (folder / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
        comparisons.append(result)
    return {
        "schema": "textlayout.squadds-reference.v1",
        "sources": ASSETS,
        "paper": "https://doi.org/10.22331/q-2024-09-09-1465",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "comparison_code_sha256": hashlib.sha256(
            Path(sys.modules[roundtrip_reference_gds.__module__].__file__).read_bytes()).hexdigest(),
        "mask_geometry_passed": all(row["geometry_equivalent"] for row in comparisons),
        "variants_evaluated": len(comparisons),
        "variants": comparisons,
        "measurement_source": "Published SQuADDS WM1 records, not measurements made by this project",
        "measured_device_count": len(values),
        "published_measurements": values,
        "process": {key: wm1[key] for key in ("foundry", "substrate", "materials", "fabrication_recipe")},
        "device_to_top_variant_mapping": None,
        "electrical_reproduction_status": "NOT_EVALUATED",
        "electrical_error_percent": None,
        "remaining_requirements": [
            "Identify the fabricated top variant and match each measured device to its geometry",
            "Specify the physical stack, ports, junction model and boundary conditions",
            "Run converged open-source field extraction and pair every prediction with its measurement",
        ],
        "scope": "Original mask import/export equivalence for every published GDS top variant; "
                 "no regenerated prompt geometry or electrical parity claim",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".tools/squadds_reference"))
    parser.add_argument("--out", type=Path, default=Path("out/squadds_reference"))
    parser.add_argument("--offline", action="store_true", help="Require hash-verified cached data")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        result = validate(args.cache, args.out, offline=args.offline)
    except (OSError, ValueError, RuntimeError, KeyError, StopIteration) as exc:
        result = {"mask_geometry_passed": False, "error": str(exc),
                  "electrical_reproduction_status": "NOT_EVALUATED"}
    report = args.out / "results.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result.get(key) for key in (
        "mask_geometry_passed", "variants_evaluated", "measured_device_count",
        "electrical_reproduction_status", "error")}, indent=2))
    print(f"Full evidence: {report}")
    return 0 if result["mask_geometry_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
