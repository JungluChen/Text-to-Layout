"""Example 05 — Inspect all backend availability and provenance requirements.

Shows which of the 9 external backends are available on this machine,
and demonstrates the value_record() provenance contract.

Run: uv run python examples/05_backend_status_and_provenance.py
"""

from __future__ import annotations

from text_to_gds.backends import BACKEND_CLASSES, list_backends
from text_to_gds.backends.base import validate_value_records, value_record
from text_to_gds.tool_discovery import tool_paths

# ── 1. Binary tools discovered in .tools/ ─────────────────────────────────────
print("Binary tools discovered in .tools/")
print("-" * 50)
tools = tool_paths()
for name, path in tools.summary().items():
    status = f"found: {path}" if path else "not found"
    print(f"  {name:<12} {status}")

# ── 2. All 9 backend statuses ─────────────────────────────────────────────────
print("\nBackend registry (9 backends)")
print("-" * 50)
backends = list_backends()
for b in backends:
    av = b["availability"]
    mark = "OK" if av["available"] else "--"
    ver = f" (v{av['version']})" if av.get("version") else ""
    print(f"  [{mark}] {b['name']:<22} {b['role']}{ver}")
    if not av["available"]:
        print(f"         reason: {av['reason']}")

# ── 3. Provenance contract demonstration ──────────────────────────────────────
print("\nProvenance contract — every reported value must carry:")
print("-" * 50)
print("  {value, unit, source, method, confidence}")
print()

good_record = value_record(
    value=6.01,
    unit="GHz",
    source="JosephsonCircuits.jl",
    method="harmonic-balance pump sweep",
    confidence=0.9,
    artifact="workspace/artifacts/jpa.jl",
)
print(f"  VALID record: {good_record}")

bad_records = {
    "resonance_frequency": {
        "value": 6.0,
        "unit": "GHz",
        "source": "LLM",        # ← invalid
        "method": "estimated",
        "confidence": 0.5,
    }
}
errors = validate_value_records(bad_records)
print(f"\n  INVALID record errors: {errors}")

print("\nRule: source='LLM' → immediate review failure.")
print("Rule: analytical formula → method_label='estimated', confidence≤0.7")
print("Rule: real solver output → method_label='simulated', must cite output_file")
print()

# ── 4. What each backend is for ───────────────────────────────────────────────
print("Backend → physics question mapping")
print("-" * 50)
roles = [
    ("kqcircuits",         "CPW feedlines, resonators, airbridges, JJ-compatible superconducting layouts"),
    ("qiskit_metal",       "Transmon qubits, CPW routing, couplers, launch pads"),
    ("gdsfactory",         "GDS boolean ops, layer remapping, polygon export — glue only"),
    ("josephsoncircuits",  "JPA/JTWPA gain, pump sweep, harmonic balance — ONLY valid gain source"),
    ("scqubits",           "Transmon/fluxonium energy spectrum, anharmonicity, Hamiltonian plots"),
    ("openems",            "RF S-parameters, CPW Z0, Touchstone .s2p — FDTD driven-modal"),
    ("palace",             "Eigenmode f0, Q factor, cavity modes — 3D FEM"),
    ("elmer",              "Electrostatic capacitance, IDC coupling — when FastCap unavailable"),
    ("pyepr",              "Energy participation ratios — post-processing after eigenmode solve"),
]
for name, role in roles:
    print(f"  {name:<22} {role}")

print("\nDone.")
