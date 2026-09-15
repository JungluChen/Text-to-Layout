"""Round-trip a real reference GDS through gdsfactory and independently compare every layer.

Example: python scripts/validate_reference_gds.py source.gds --cell TOP --out out/reference
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textlayout.verification.reference_gds import roundtrip_reference_gds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--cell", help="Required when the source has multiple top cells")
    parser.add_argument("--out", type=Path, default=Path("out/reference"))
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    try:
        result = roundtrip_reference_gds(args.reference, args.out / "output.gds", cell=args.cell)
    except (OSError, ValueError, RuntimeError) as exc:
        result = {"geometry_equivalent": False, "error": str(exc)}
    (args.out / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["geometry_equivalent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
