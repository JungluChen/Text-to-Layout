"""Example 04 — JPA gain sweep via JosephsonCircuits.jl harmonic balance.

Demonstrates:
  Extracted Lj + Ic → JosephsonCircuits.jl pump sweep → gain vs pump power
  The gain curve is ONLY produced by a real harmonic-balance solver.
  If JosephsonCircuits.jl is unavailable: status=skipped, no fabricated curve.

Run: uv run python examples/04_jpa_gain_josephsoncircuits.py
"""

from __future__ import annotations

from pathlib import Path

from text_to_gds.backends import get_backend
from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import compile_layout, run_simulation

# ── 1. Backend check ──────────────────────────────────────────────────────────
backend = get_backend("josephsoncircuits")
av = backend.available()
print(f"JosephsonCircuits.jl backend: {'available' if av.available else 'missing'}")
print(f"  reason: {av.reason}")
if not av.available:
    print("\nTo install:")
    print("  uv run python scripts/setup_external_tools.py")
    print("  (requires Julia — already available at .tools/julia-1.12.6/)")

# ── 2. Design intent ──────────────────────────────────────────────────────────
print("\nStep 1 — Design intent")
intent = synthesize_design_intent(
    "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth",
    inputs={
        "process": "documentation_example",
        "device": "JPA",
        "frequency_ghz": 6.0,
        "gain_db": 20.0,
        "bandwidth_mhz": 200.0,
        "jc_ua_per_um2": 2.0,
        "junction_width_um": 0.22,
        "junction_height_um": 0.22,
        "junction_count": 2,
    },
)
print(f"  Status: {intent['status']}")

# ── 3. Compile LJPA seed ──────────────────────────────────────────────────────
print("\nStep 2 — Compile LJPA seed")
compiled = compile_layout(
    pcell="lumped_element_jpa_seed",
    parameters={
        "center_frequency_ghz": 6.0,
        "target_bandwidth_mhz": 200.0,
        "target_gain_db": 20.0,
    },
    output_name="jpa_gain_example.gds",
)
print(f"  GDS:  {compiled['gds_path']}")

# ── 4. JosephsonCircuits.jl harmonic balance ──────────────────────────────────
print("\nStep 3 — JosephsonCircuits.jl harmonic balance pump sweep")
print("  (this is the ONLY valid source of JPA gain — never fabricated)")
sim = run_simulation(
    compiled["sidecar_path"],
    simulator="JosephsonCircuits.jl",
    jc_ua_per_um2=2.0,
    target_frequency_ghz=6.0,
    target_bandwidth_mhz=200.0,
    coupling_capacitance_ff=5.0,
)

adapter_status = sim.get("adapter_status", "skipped")
print(f"\n  Adapter: {sim.get('adapter', 'JosephsonCircuits.jl')}")
print(f"  Status:  {adapter_status}")

if adapter_status == "executed":
    result = sim.get("adapter_result", {})
    gain = result.get("best_peak_gain_db")
    bw = result.get("bandwidth_mhz")
    print(f"\n  ✓ REAL SOLVER RESULT:")
    print(f"    Peak gain:  {gain:.1f} dB" if gain is not None else "    Peak gain:  —")
    print(f"    Bandwidth:  {bw:.1f} MHz" if bw is not None else "    Bandwidth:  —")
    plot = sim.get("scientific_plot_path")
    if plot and Path(plot).exists():
        print(f"    Plot:       {plot}")
elif adapter_status == "skipped":
    reason = sim.get("adapter_result", {}).get("reason", "Julia not found")
    print(f"\n  ✗ SOLVER SKIPPED")
    print(f"    reason: {reason}")
    print("\n  → Run scripts/setup_external_tools.py to install JosephsonCircuits.jl")
    print("    Julia is at .tools/julia-1.12.6/bin/julia.exe")
    print("\n  The Julia script was generated at:")
    script = sim.get("adapter_result", {}).get("script_path") or sim.get("script_path")
    if script:
        print(f"    {script}")
    print("\n  Run it manually:")
    print("    .tools/julia-1.12.6/bin/julia.exe <script_path>")

print("\nJosephsonCircuits.jl: https://github.com/kpobrien/JosephsonCircuits.jl")
print("Done.")
