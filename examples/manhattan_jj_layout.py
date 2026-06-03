from __future__ import annotations

from text_to_gds.server import compile_layout, run_drc, run_simulation


def main() -> None:
    compiled = compile_layout(
        pcell="manhattan_josephson_junction",
        parameters={
            "junction_width": 0.22,
            "junction_height": 0.22,
            "lead_width": 1.0,
            "lead_length": 6.0,
        },
        output_name="example_manhattan_jj.gds",
    )
    drc = run_drc(compiled["gds_path"])
    simulation = run_simulation(compiled["sidecar_path"], jc_ua_per_um2=2.0)

    print(compiled)
    print({"drc_status": drc["status"], "report_path": drc["report_path"]})
    print(
        {
            "critical_current_ua": simulation["critical_current_ua"],
            "josephson_inductance_ph": simulation["josephson_inductance_ph"],
            "result_path": simulation["result_path"],
        }
    )


if __name__ == "__main__":
    main()

