"""Five runnable zero-to-one Text-to-GDS demonstrations.

Run all demos:
    py -3 -m uv run python examples/zero_to_one_demos.py all

Run one demo:
    py -3 -m uv run python examples/zero_to_one_demos.py cpw
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from text_to_gds.server import (
    compile_layout,
    export_openems_project,
    extract_layout,
    run_design_workflow,
    run_drc,
    run_simulation,
)


def _summary(name: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {name} ===")
    print(json.dumps(payload, indent=2, default=str))


def demo_junction() -> dict[str, Any]:
    """Prompt-equivalent parameters -> JJ GDS -> DRC -> Ic/Lj simulation."""
    layout = compile_layout(
        pcell="manhattan_josephson_junction",
        parameters={"junction_width": 0.22, "junction_height": 0.22},
        output_name="demo_01_junction.gds",
    )
    drc = run_drc(layout["gds_path"], min_width_um=0.1)
    simulation = run_simulation(layout["sidecar_path"], jc_ua_per_um2=2.0)
    return {
        "gds": layout["gds_path"],
        "layout_png": layout["screenshot_path"],
        "drc_status": drc["status"],
        "critical_current_ua": simulation["critical_current_ua"],
        "josephson_inductance_ph": simulation["josephson_inductance_ph"],
    }


def demo_calibration_array() -> dict[str, Any]:
    """Area sweep -> 16-device calibration-array GDS -> expected Ic endpoints."""
    layout = compile_layout(
        pcell="jj_ic_calibration_array",
        parameters={
            "junction_count": 16,
            "min_area_um2": 0.04,
            "max_area_um2": 0.20,
            "jc_ua_per_um2": 2.0,
        },
        output_name="demo_02_jj_calibration_array.gds",
    )
    extracted = extract_layout(layout["sidecar_path"])
    sidecar = json.loads(Path(layout["sidecar_path"]).read_text(encoding="utf-8"))
    junctions = sidecar["info"]["junctions"]
    return {
        "gds": layout["gds_path"],
        "layout_png": layout["screenshot_path"],
        "extraction": extracted["result_path"],
        "junction_count": len(junctions),
        "first_expected_ic_ua": junctions[0]["expected_ic_ua"],
        "last_expected_ic_ua": junctions[-1]["expected_ic_ua"],
    }


def demo_cpw() -> dict[str, Any]:
    """6 GHz target -> lambda/4 CPW GDS -> DRC -> openEMS handoff."""
    layout = compile_layout(
        pcell="cpw_quarter_wave_resonator",
        parameters={
            "target_frequency_ghz": 6.0,
            "effective_permittivity": 6.2,
            "trace_width": 10.0,
            "gap": 6.0,
        },
        output_name="demo_03_cpw_resonator.gds",
    )
    drc = run_drc(layout["gds_path"], min_width_um=0.1)
    extracted = extract_layout(layout["sidecar_path"])
    em = export_openems_project(layout["sidecar_path"], output_name="demo_03_cpw", run=False)
    return {
        "gds": layout["gds_path"],
        "layout_png": layout["screenshot_path"],
        "extraction": extracted["result_path"],
        "drc_status": drc["status"],
        "openems_status": em["status"],
        "openems_script": em["script_path"],
    }


def demo_via_chain() -> dict[str, Any]:
    """100-stage process monitor -> GDS -> topology and resistance metadata."""
    layout = compile_layout(
        pcell="via_chain_monitor",
        parameters={"stage_count": 100},
        output_name="demo_04_via_chain.gds",
    )
    drc = run_drc(layout["gds_path"], min_width_um=0.1)
    extracted = extract_layout(layout["sidecar_path"])
    sidecar = json.loads(Path(layout["sidecar_path"]).read_text(encoding="utf-8"))
    parameters = sidecar["info"]
    return {
        "gds": layout["gds_path"],
        "layout_png": layout["screenshot_path"],
        "extraction": extracted["result_path"],
        "drc_status": drc["status"],
        "stage_count": parameters["stage_count"],
        "estimated_total_resistance_ohm": parameters["estimated_total_resistance_ohm"],
        "open_chain_detected": parameters["open_chain_detected"],
    }


def demo_jpa_workflow() -> dict[str, Any]:
    """Natural-language device target -> complete local LJPA artifact workflow."""
    result = run_design_workflow(
        "Design a 6 GHz LJPA with 20 dB gain and 500 MHz bandwidth",
        output_name="demo_05_ljpa.gds",
        jc_ua_per_um2=2.0,
        simulator="mock_jj",
    )
    return {
        "gds": result["compile"]["gds_path"],
        "layout_png": result["compile"]["screenshot_path"],
        "drc_status": result["drc"]["status"],
        "workbench": result["workbench"]["html_path"],
        "simulation": result["simulation"]["result_path"],
    }


DEMOS: dict[str, Callable[[], dict[str, Any]]] = {
    "junction": demo_junction,
    "calibration-array": demo_calibration_array,
    "cpw": demo_cpw,
    "via-chain": demo_via_chain,
    "jpa": demo_jpa_workflow,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=["all", *DEMOS], nargs="?", default="all")
    args = parser.parse_args()
    selected = DEMOS.items() if args.demo == "all" else [(args.demo, DEMOS[args.demo])]
    for name, function in selected:
        _summary(name, function())


if __name__ == "__main__":
    main()
