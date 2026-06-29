"""Runnable Text-to-GDS demos from 0 to 100.

Run all demos:
    py -3 -m uv run python examples/zero_to_one_demos.py all

Run one demo:
    py -3 -m uv run python examples/zero_to_one_demos.py 40
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from text_to_gds.server import (
    compare_measurement_engine,
    compile_layout,
    extract_layout,
    extract_physics_graph_artifact,
    generate_solver_inputs_from_physics_graph,
    list_em_solvers,
    list_pcells,
    list_process_design_kits,
    run_axion_search_jpa_final_test,
    run_drc,
    run_inverse_design_jpa,
    run_simulation,
)

ARTIFACTS = Path("workspace") / "artifacts"


def _summary(name: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {name} ===")
    print(json.dumps(payload, indent=2, default=str))


def demo_00_capability_index() -> dict[str, Any]:
    """0/100: list local PCells, process kits, and EM solvers."""
    return {
        "pcells": list_pcells()["pcells"],
        "process_design_kits": [
            kit["process_id"] for kit in list_process_design_kits()["process_design_kits"]
        ],
        "em_solvers": [solver["name"] for solver in list_em_solvers()["solvers"]],
    }


def demo_20_junction_physics_graph() -> dict[str, Any]:
    """20/100: JJ GDS -> DRC -> extraction.json -> physics_graph.json."""
    layout = compile_layout(
        pcell="manhattan_josephson_junction",
        parameters={"junction_width": 0.22, "junction_height": 0.22},
        output_name="demo_20_junction.gds",
    )
    drc = run_drc(layout["gds_path"], min_width_um=0.1)
    extraction = extract_layout(layout["sidecar_path"], jc_ua_per_um2=2.0)
    graph = extract_physics_graph_artifact(
        layout["sidecar_path"],
        output_name="demo_20_junction",
        jc_ua_per_um2=2.0,
        specific_capacitance_ff_per_um2=45.0,
    )
    simulation = run_simulation(layout["sidecar_path"], jc_ua_per_um2=2.0)
    return {
        "gds": layout["gds_path"],
        "layout_png": layout["screenshot_path"],
        "drc_status": drc["status"],
        "extraction": extraction["result_path"],
        "physics_graph": graph["result_path"],
        "critical_current_ua": simulation["critical_current_ua"],
        "josephson_inductance_ph": simulation["josephson_inductance_ph"],
    }


def demo_40_cpw_solver_inputs() -> dict[str, Any]:
    """40/100: CPW resonator GDS -> physics graph -> openEMS/Elmer/Palace inputs."""
    layout = compile_layout(
        pcell="cpw_quarter_wave_resonator",
        parameters={
            "target_frequency_ghz": 6.0,
            "effective_permittivity": 6.2,
            "trace_width": 10.0,
            "gap": 6.0,
        },
        output_name="demo_40_cpw_resonator.gds",
    )
    graph = extract_physics_graph_artifact(layout["sidecar_path"], output_name="demo_40_cpw")
    solver_inputs = generate_solver_inputs_from_physics_graph(
        graph["result_path"],
        output_name="demo_40_solver_inputs",
    )
    return {
        "gds": layout["gds_path"],
        "physics_graph": graph["result_path"],
        "openems": solver_inputs["openems"],
        "elmer": solver_inputs["elmer"],
        "palace": solver_inputs["palace"],
    }


def demo_60_inverse_design() -> dict[str, Any]:
    """60/100: optimizer regenerates a GDS for every JPA candidate."""
    result = run_inverse_design_jpa(
        "I need 6 GHz JPA, 20 dB gain, 200 MHz bandwidth",
        output_name="demo_60_inverse_jpa",
        iterations=5,
        algorithm="cma-es",
    )
    return {
        "report": result["report_path"],
        "candidate_count": result["candidate_count"],
        "best_candidate": result["best_candidate"],
    }


def demo_80_measurement_comparison() -> dict[str, Any]:
    """80/100: VNA-like CSV -> fit -> simulation-vs-measurement process correction."""
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    measurement_path = ARTIFACTS / "demo_80_measurement.csv"
    with measurement_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frequency_ghz", "gain_db"])
        writer.writeheader()
        for frequency, gain in [
            (5.80, 10.0),
            (5.90, 18.0),
            (6.00, 20.0),
            (6.10, 17.0),
            (6.20, 9.0),
        ]:
            writer.writerow({"frequency_ghz": frequency, "gain_db": gain})
    simulation_path = ARTIFACTS / "demo_80_simulation.json"
    simulation_path.write_text(
        json.dumps(
            {
                "measurement_prediction": {
                    "center_frequency_ghz": 6.2,
                    "peak_gain_db": 19.0,
                    "bandwidth_3db_mhz": 120.0,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return compare_measurement_engine(
        str(measurement_path.resolve()),
        simulation_path=str(simulation_path.resolve()),
        output_name="demo_80_measurement_comparison.json",
        fit_kind="jpa_gain",
    )


def demo_100_axion_jpa() -> dict[str, Any]:
    """100/100: final flux-tunable axion-search JPA bundle."""
    result = run_axion_search_jpa_final_test(output_name="demo_100_axion_jpa")
    return {
        "report": result["report_path"],
        "gds": result["outputs"]["gds"],
        "physics_graph": result["outputs"]["physics_graph"],
        "em_result": result["outputs"]["em_result"],
        "gain_map_h5": result["outputs"]["gain_map_h5"],
        "repair_suggestions": result["outputs"]["repair_suggestions"],
    }


DEMOS: dict[str, Callable[[], dict[str, Any]]] = {
    "0": demo_00_capability_index,
    "20": demo_20_junction_physics_graph,
    "40": demo_40_cpw_solver_inputs,
    "60": demo_60_inverse_design,
    "80": demo_80_measurement_comparison,
    "100": demo_100_axion_jpa,
}

ALIASES = {
    "capabilities": "0",
    "junction": "20",
    "cpw": "40",
    "inverse": "60",
    "measurement": "80",
    "axion": "100",
}


def main() -> None:
    choices = ["all", *DEMOS, *ALIASES]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=choices, nargs="?", default="all")
    args = parser.parse_args()
    selected_key = ALIASES.get(args.demo, args.demo)
    selected = DEMOS.items() if selected_key == "all" else [(selected_key, DEMOS[selected_key])]
    for name, function in selected:
        _summary(f"{name}/100", function())


if __name__ == "__main__":
    main()
