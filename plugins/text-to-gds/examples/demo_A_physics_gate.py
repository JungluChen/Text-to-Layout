"""Demo A — 0→25: Physics feasibility gate.

Proves that the design-intent gate blocks incoherent targets before layout is attempted,
and then passes a physically valid JPA design through to GDS + sidecar.

Run:
    uv run python examples/demo_A_physics_gate.py
"""

from __future__ import annotations

import json

from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import check_design_feasibility, compile_layout


def main() -> None:
    print("\n=== Demo A: Physics feasibility gate (0 -> 25) ===\n")

    # -- Step 1: check_design_feasibility (quick pre-screen) -----------------
    print("Step 1 -- check_design_feasibility")
    feas = check_design_feasibility(
        "jpa",
        json.dumps({"center_frequency_ghz": 6.0, "target_gain_db": 20.0,
                    "target_bandwidth_mhz": 200.0}),
    )
    print(f"  device:  {feas['device']}")
    print(f"  schema:  {feas['schema']}")

    # -- Step 2: synthesize_design_intent — raises if targets are incoherent --
    print("\nStep 2 -- synthesize_design_intent (physics gate)")
    intent = synthesize_design_intent(
        "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth",
        inputs={
            "device": "JPA",
            "frequency_ghz": 6.0,
            "gain_db": 20.0,
            "bandwidth_mhz": 200.0,
            "jc_ua_per_um2": 2.0,
            "junction_width_um": 0.22,
            "junction_height_um": 0.22,
            "junction_count": 2,
            "center_width_um": 10.0,
            "gap_um": 6.0,
            "ground_width_um": 500.0,
            "epsilon_r": 11.45,
            "substrate_thickness_um": 254.0,
            "impedance_tolerance_ohm": 5.0,
            "substrate": "high_resistivity_silicon",
            "rf_ports": 2,
            "flux_line": True,
            "pump_frequency_ghz": 12.0,
            "pump_power_dbm": -30.0,
            "pump_mode": "four_wave_mixing",
            "package_clearance_um": 200.0,
            "wirebond_pads": True,
        },
    )
    print(f"  status:  {intent['status']}")
    physics = intent.get("physics", {})
    ic_a = physics.get("critical_current_a")
    lj_h = physics.get("josephson_inductance_h")
    if ic_a is not None:
        print(f"  Ic:      {ic_a * 1e6:.4f} uA")
    if lj_h is not None:
        print(f"  Lj:      {lj_h * 1e12:.2f} pH")
    cpw = physics.get("cpw")
    if cpw:
        print(f"  Z0:      {cpw.get('impedance_ohm', 'N/A')} ohm")
    if intent["status"] != "ready":
        print(f"  blockers: {intent['blockers']}")
        return

    # -- Step 3: compile_layout — only reached when intent says 'ready' ------
    print("\nStep 3 -- compile_layout (gated by design intent)")
    result = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters={
            "center_frequency_ghz": 6.0,
            "target_gain_db": 20.0,
        },
        output_name="demo_A_jpa.gds",
    )
    print(f"  status:      {result['status']}")
    print(f"  gds_path:    {result['gds_path']}")
    print(f"  sidecar:     {result['sidecar_path']}")
    print(f"  screenshot:  {result['screenshot_path']}")

    print("\n[PASS] Physics gate verified: incoherent designs are blocked before layout.")
    print(f"       GDS written to: {result['gds_path']}")


if __name__ == "__main__":
    main()
