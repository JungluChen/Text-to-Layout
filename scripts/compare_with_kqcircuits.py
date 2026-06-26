"""Compare generated hierarchy/connectivity against local KQCircuits source cues."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "quantum-eda-stack" / "KQCircuits" / "klayout_package" / "python" / "kqcircuits"


def main() -> None:
    files = [
        REF / "elements" / "waveguide_composite.py",
        REF / "elements" / "airbridge.py",
        REF / "junctions" / "manhattan.py",
    ]
    comparison = {
        "schema": "text-to-gds.reference.kqcircuits.v1",
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
                "mentions_refpoints": "refpoint" in text.lower(),
                "mentions_ports": "port" in text.lower(),
                "mentions_waveguide": "waveguide" in text.lower(),
            }
        )
    out = ROOT / "workspace" / "artifacts" / "compare_with_kqcircuits.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
