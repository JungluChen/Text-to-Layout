"""Compare generated port/component concepts against local gdsfactory source cues."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "quantum-eda-stack" / "gdsfactory" / "gdsfactory"


def main() -> None:
    files = [
        REF / "component.py",
        REF / "port.py",
        REF / "routing" / "route_bundle.py",
        REF / "get_netlist.py",
    ]
    comparison = {
        "schema": "text-to-gds.reference.gdsfactory.v1",
        "reference_root": str(REF),
        "available": REF.is_dir(),
        "features": [],
    }
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
        comparison["features"].append(
            {
                "path": str(path),
                "exists": path.is_file(),
                "mentions_component": "component" in text.lower(),
                "mentions_port": "port" in text.lower(),
                "mentions_netlist": "netlist" in text.lower(),
                "mentions_route": "route" in text.lower(),
            }
        )
    out = ROOT / "workspace" / "artifacts" / "compare_with_gdsfactory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
