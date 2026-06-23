"""Example 02 — CPW resonator via KQCircuits backend + openEMS S-parameters.

Demonstrates:
  KQCircuits backend → CPW quarter-wave resonator layout
  → openEMS FDTD → Touchstone .s2p → RF validation

Backend priority: KQCircuits (primary) → gdsfactory PCell (fallback)
Solver: openEMS FDTD (primary) → status=skipped if not available

Run: uv run python examples/02_kqcircuits_cpw_resonator.py
"""

from __future__ import annotations

import json
from pathlib import Path

from text_to_gds.backends import get_backend
from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import compile_layout, export_openems_project, extract_layout, run_drc

# ── 1. Check backend availability ─────────────────────────────────────────────
print("Backend availability:")
for name in ["kqcircuits", "gdsfactory", "openems"]:
    backend = get_backend(name)
    av = backend.available()
    mark = "OK" if av.available else "--"
    print(f"  [{mark}] {name}: {av.reason}")

# ── 2. Design intent ──────────────────────────────────────────────────────────
print("\nStep 1 — Design intent")
intent = synthesize_design_intent(
    "Design a 6 GHz CPW quarter-wave resonator with 10 MHz bandwidth",
    inputs={
        "process": "documentation_example",
        "device": "CPW_resonator",
        "frequency_ghz": 6.0,
        "bandwidth_mhz": 10.0,
        "center_width_um": 10.0,
        "gap_um": 6.0,
        "epsilon_r": 11.45,
        "substrate_thickness_um": 254.0,
        "impedance_tolerance_ohm": 5.0,
    },
)
print(f"  Status: {intent['status']}  Blockers: {intent['blockers']}")

# ── 3. Layout via KQCircuits → gdsfactory fallback ───────────────────────────
print("\nStep 2 — Layout generation")
kqc = get_backend("kqcircuits")
if kqc.available().available:
    print("  Using KQCircuits (primary superconducting backend)")
    result = kqc.generate(
        {"device": "cpw_quarter_wave_resonator",
         "center_width_um": 10.0, "gap_um": 6.0,
         "frequency_ghz": 6.0, "epsilon_r": 11.45},
        output_dir="workspace/artifacts/cpw_resonator_kqc",
    )
    print(f"  Status: {result['status']}")
    gds_path = result.get("gds_path") or result.get("output", {}).get("gds_path")
else:
    print("  KQCircuits not available — falling back to gdsfactory PCell")
    compiled = compile_layout(
        pcell="cpw_quarter_wave_resonator",
        parameters={"target_frequency_ghz": 6.0, "trace_width": 10.0, "gap": 6.0},
        output_name="cpw_resonator.gds",
    )
    gds_path = compiled["gds_path"]
    sidecar_path = compiled["sidecar_path"]
    print(f"  GDS: {gds_path}")

# ── 4. DRC ────────────────────────────────────────────────────────────────────
print("\nStep 3 — DRC")
if gds_path:
    drc = run_drc(gds_path, min_width_um=0.5)
    print(f"  Status: {drc['status']}  Shapes: {drc['checked_shapes']}")

# ── 5. openEMS FDTD ───────────────────────────────────────────────────────────
print("\nStep 4 — openEMS FDTD (RF S-parameters)")
if "sidecar_path" in locals():
    openems = export_openems_project(sidecar_path, output_name="cpw_resonator", run=True)
    print(f"  openEMS status: {openems.get('status', 'unknown')}")
    if openems.get("status") == "executed":
        tp = openems.get("touchstone_path")
        print(f"  Touchstone: {tp}")
        print("  → Parse with scikit-rf: import skrf; nw = skrf.Network(touchstone_path)")
    else:
        reason = openems.get("reason", "openEMS not available")
        print(f"  Reason: {reason}")
        print("  → openEMS binary at .tools/openEMS-*/openEMS/openEMS.exe is auto-discovered")
        print("    Set TEXT_TO_GDS_RUN_EXTERNAL=1 and run tests/test_research_execution.py")
else:
    print("  Skipped — no sidecar path (KQCircuits path was used)")

print("\nKQCircuits reference: https://github.com/iqm-finland/KQCircuits")
print("openEMS reference:    https://github.com/thliebig/openEMS")
print("\nDone.")
