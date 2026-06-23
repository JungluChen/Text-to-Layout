"""Example 03 — Transmon qubit spectrum via scqubits.

Demonstrates:
  Extracted Ej/Ec → scqubits transmon Hamiltonian → energy levels + anharmonicity
  Fails clearly if scqubits is not installed (never fabricates a spectrum).

Run: uv run python examples/03_scqubits_transmon_spectrum.py
     uv run --extra research python examples/03_scqubits_transmon_spectrum.py
"""

from __future__ import annotations

from pathlib import Path

from text_to_gds.backends import get_backend
from text_to_gds.server import compile_layout, export_hamiltonian_model

# ── 1. Check scqubits backend ─────────────────────────────────────────────────
backend = get_backend("scqubits")
av = backend.available()
print(f"scqubits backend: {'available' if av.available else 'missing'}")
print(f"  reason: {av.reason}")

if not av.available:
    print("\nInstall scqubits:")
    print("  uv run pip install scqubits")
    print("  or: uv sync --extra quantum")
    raise SystemExit(0)

# ── 2. Compile a JPA seed (carries SQUID → Ej/Ec) ───────────────────────────
print("\nCompiling LJPA seed (SQUID = tunable transmon Hamiltonian) ...")
compiled = compile_layout(
    pcell="lumped_element_jpa_seed",
    parameters={"center_frequency_ghz": 6.0, "target_bandwidth_mhz": 200.0},
    output_name="transmon_spectrum.gds",
)
print(f"  Device:     {compiled.get('info', {}).get('device_type', 'lumped_element_jpa_seed')}")

# ── 3. Export Hamiltonian model → scqubits execution ─────────────────────────
print("\nRunning scqubits transmon diagonalisation ...")
hamiltonian = export_hamiltonian_model(
    compiled["sidecar_path"],
    output_name="transmon_spectrum",
    jc_ua_per_um2=2.0,
    flux_bias_phi0=0.0,
)
print(f"  Schema: {hamiltonian.get('schema')}")
print(f"  Ej:     {hamiltonian['parameters']['ej_ghz']:.4g} GHz")
print(f"  Ec:     {hamiltonian['parameters']['ec_ghz']:.4g} GHz")
print(f"  Ej/Ec:  {hamiltonian['parameters']['ej_ghz']/hamiltonian['parameters']['ec_ghz']:.1f}")

execution = hamiltonian.get("execution", {})
print(f"\nscqubits execution: {execution.get('status', 'not run')}")
if execution.get("status") == "executed":
    levels = execution.get("energy_levels_ghz", [])
    print(f"  Engine:        {execution.get('engine')}")
    print(f"  Energy levels: {[f'{e:.3f}' for e in levels[:6]]} GHz")
    anharmonicity = levels[2] - 2 * levels[1] if len(levels) >= 3 else None
    if anharmonicity is not None:
        print(f"  Anharmonicity: {anharmonicity * 1e3:.1f} MHz")
    plot = execution.get("plot_path")
    if plot and Path(plot).exists():
        print(f"  Spectrum plot: {plot}")
else:
    print(f"  reason: {execution.get('reason', 'unknown')}")

print("\nscqubits reference: https://github.com/scqubits/scqubits")
print("Done.")
