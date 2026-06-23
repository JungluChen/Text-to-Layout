"""Example 01 — Full physics pipeline: Manhattan Josephson Junction.

Demonstrates:
  design_intent gate → compile (local PCell fallback) → DRC → extraction
  → JosephsonCircuits.jl harmonic balance → review committee

Run: uv run python examples/01_full_pipeline_jj.py
"""

from __future__ import annotations

import json
from pathlib import Path

from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import (
    compile_layout,
    extract_layout,
    run_drc,
    run_simulation,
)
from text_to_gds.review.committee import review_committee

# ── 1. Design-intent gate ─────────────────────────────────────────────────────
print("Step 1 — Design intent")
intent = synthesize_design_intent(
    "Generate a Manhattan Josephson junction fabrication test structure",
    inputs={
        "process": "double_angle_evaporation",
        "device": "Josephson_junction",
        "jc_ua_per_um2": 2.0,
        "junction_width_um": 0.22,
        "junction_height_um": 0.22,
    },
)
assert intent["status"] == "ready", f"Design intent failed: {intent['blockers']}"
print(f"  blockers: {intent['blockers']}  ← empty means feasible")

# ── 2. Compile → GDSII + sidecar ─────────────────────────────────────────────
print("Step 2 — Compile layout")
compiled = compile_layout(
    pcell="manhattan_josephson_junction",
    parameters={"junction_width": 0.22, "junction_height": 0.22},
    output_name="example_jj.gds",
)
print(f"  GDS:     {compiled['gds_path']}")
print(f"  Sidecar: {compiled['sidecar_path']}")
sidecar = json.loads(Path(compiled["sidecar_path"]).read_text(encoding="utf-8"))
print(f"  Device:  {sidecar['info']['device_type']}")
print(f"  JJ area: {sidecar['info']['junction_area_um2']:.4f} µm²")

# ── 3. DRC ────────────────────────────────────────────────────────────────────
print("Step 3 — DRC")
drc = run_drc(compiled["gds_path"], min_width_um=0.1)
print(f"  Status: {drc['status']}  Checked shapes: {drc['checked_shapes']}")
if drc["violations"]:
    for v in drc["violations"][:3]:
        print(f"  VIOLATION: {v['rule']} on layer {v['layer']}")

# ── 4. Extraction ─────────────────────────────────────────────────────────────
print("Step 4 — Physical parameter extraction")
extraction = extract_layout(compiled["sidecar_path"])
params = extraction.get("parameters", {})
print(f"  Ic:  {params.get('critical_current_ua', '—'):.4g} µA  [extracted from area × Jc]")
print(f"  Lj:  {params.get('josephson_inductance_ph', '—'):.4g} pH  [estimated: Lj=Φ₀/2πIc]")

# ── 5. Simulation ─────────────────────────────────────────────────────────────
print("Step 5 — JosephsonCircuits.jl harmonic balance")
sim = run_simulation(
    compiled["sidecar_path"],
    simulator="JosephsonCircuits.jl",
    jc_ua_per_um2=2.0,
    target_frequency_ghz=5.0,
    target_bandwidth_mhz=500.0,
)
adapter_status = sim.get("adapter_status", "skipped")
print(f"  Adapter status: {adapter_status}")
if adapter_status == "executed":
    print(f"  Peak gain: {sim.get('adapter_result', {}).get('best_peak_gain_db', '—')} dB")
else:
    reason = sim.get("adapter_result", {}).get("reason", "Julia not available")
    print(f"  Reason: {reason}")
    print("  → Install Julia + JosephsonCircuits.jl or run scripts/setup_external_tools.py")

# ── 6. Review committee ───────────────────────────────────────────────────────
print("Step 6 — 5-agent review committee")
evidence = {
    "gds_path": compiled["gds_path"],
    "sidecar": sidecar,
    "drc": drc,
    "extraction": extraction,
    "simulation": sim,
}
verdict = review_committee(evidence)
print(f"  Score:    {verdict['score']} / 100  (min across all reviewers)")
print(f"  Approved: {verdict['approved']}")
if verdict["blockers"]:
    print("  Blockers:")
    for b in verdict["blockers"]:
        print(f"    - [{b['severity']}] {b['message']}")

print("\nDone. Artifacts written to workspace/artifacts/")
