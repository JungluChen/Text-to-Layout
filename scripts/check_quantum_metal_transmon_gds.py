"""Independent check of the explicit 2 mm Quantum Metal transmon mask fixture.

This checks two charge pads and a ground-plane cutout only. It does not verify
or supply a fabrication junction, electrical model, connectivity or signoff.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


from textlayout.external.quantum_metal_mask import TransmonMaskRequest
from textlayout.external.quantum_metal_readback import check_mask


def check(path: Path) -> dict[str, object]:
    return check_mask(
        path,
        TransmonMaskRequest(
            pad_width_um=455,
            pad_height_um=90,
            pad_gap_um=30,
            pocket_width_um=650,
            pocket_height_um=650,
            chip_width_um=2000,
            chip_height_um=2000,
        ),
    )


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
