"""Guarded FastHenry preparation for a future spiral-inductor generator."""

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
                    "FastHenry input is not generated until a deterministic SpiralInductor "
                    "generator provides a continuous centerline, cross-section, and two ports."
                ),
                "component": raw.get("component"),
            }
        )
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
