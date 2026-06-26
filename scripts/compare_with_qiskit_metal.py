"""Compare generated component concepts against local Qiskit Metal source cues."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "quantum-eda-stack" / "qiskit-metal" / "qiskit_metal"
if not REF.is_dir():
    REF = ROOT / "quantum-eda-stack" / "qiskit-metal" / "src" / "qiskit_metal"


def main() -> None:
    files = [
        REF / "qlibrary" / "qubits" / "transmon_pocket.py",
        REF / "qlibrary" / "qubits" / "transmon_cross.py",
        REF / "qlibrary" / "tlines" / "meandered.py",
    ]
    comparison = {
        "schema": "text-to-gds.reference.qiskit-metal.v1",
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
                "mentions_qcomponent": "qcomponent" in text.lower(),
                "mentions_pocket": "pocket" in text.lower(),
                "mentions_coupler": "coupl" in text.lower(),
                "mentions_pin": "pin" in text.lower(),
            }
        )
    out = ROOT / "workspace" / "artifacts" / "compare_with_qiskit_metal.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
