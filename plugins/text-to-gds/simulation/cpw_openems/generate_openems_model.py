"""Guarded openEMS model preparation for a CPW Layout DSL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path, default=Path("simulation/cpw_openems/work"))
    args = parser.parse_args()
    raw = json.loads(args.layout.read_text(encoding="utf-8"))
    if raw.get("component") != "CPW":
        print(json.dumps({"status": "failed", "reason": "Layout component must be CPW."}))
        return 1
    metadata = raw.get("metadata", {})
    if not metadata.get("explicit_ground_reference_ports"):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "readiness_level": 1,
                    "reason": "Explicit RF and ground-reference ports are required before openEMS input preparation.",
                }
            )
        )
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    config = {
        "status": "input_files_prepared",
        "solver": "openEMS",
        "readiness_level": 2,
        "layout": raw,
        "required_outputs": ["Touchstone .s2p", "port impedance", "effective permittivity"],
        "warning": "A solver result is not present; mesh, port calibration, and convergence remain required.",
    }
    target = args.out / "openems_model.json"
    target.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "input_files_prepared", "file": str(target)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
