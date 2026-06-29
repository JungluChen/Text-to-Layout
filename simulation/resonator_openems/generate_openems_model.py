"""Guarded openEMS preparation for a future quarter-wave resonator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args()
    raw = json.loads(args.layout.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": "blocked",
                "readiness_level": 0,
                "reason": (
                    "openEMS input is not generated until a benchmark-ready resonator "
                    "topology defines coupling, open/short boundaries, RF ports, and ground reference."
                ),
                "component": raw.get("component"),
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
