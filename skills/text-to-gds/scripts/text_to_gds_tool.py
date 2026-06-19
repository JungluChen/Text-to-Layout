#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        pyproject = parent / "pyproject.toml"
        package_root = parent / "src" / "text_to_gds"
        if pyproject.is_file() and package_root.is_dir():
            return parent
    raise RuntimeError("Could not find a Text-to-GDS project root.")


def _load_server_module():
    project_root = _find_project_root()
    src_root = project_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from text_to_gds import server

    return server


def _load_ui_module():
    project_root = _find_project_root()
    src_root = project_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from text_to_gds import ui

    return ui


def _parameters(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("--parameters-json must decode to a JSON object")
    return value


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Text-to-GDS local tool helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("pcells")
    subparsers.add_parser("simulators")
    subparsers.add_parser("research-integrations")

    plan_parser = subparsers.add_parser("plan-ljpa")
    plan_parser.add_argument("prompt")

    workflow_parser = subparsers.add_parser("design-workflow")
    workflow_parser.add_argument("prompt")
    workflow_parser.add_argument("--output-name", default="ljpa_seed.gds")
    workflow_parser.add_argument("--parameters-json")
    workflow_parser.add_argument("--jc-ua-per-um2", type=float, default=2.0)
    workflow_parser.add_argument("--simulator", default="mock_jj")
    workflow_parser.add_argument("--analysis-mode", default="auto")
    workflow_parser.add_argument("--pump-current-fraction", type=float, default=0.017)
    workflow_parser.add_argument("--coupling-capacitance-ff", type=float)
    workflow_parser.add_argument("--resonator-capacitance-ff", type=float)
    workflow_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    workflow_parser.add_argument("--squid-asymmetry", type=float, default=0.0)
    workflow_parser.add_argument("--flux-sweep-span-phi0", type=float, default=1.0)
    workflow_parser.add_argument("--flux-sweep-points", type=int, default=101)
    workflow_parser.add_argument("--flux-period-current-ma", type=float)
    workflow_parser.add_argument("--flux-mutual-inductance-ph", type=float)

    optimized_parser = subparsers.add_parser("optimize-design")
    optimized_parser.add_argument("prompt")
    optimized_parser.add_argument("--output-name", default="ljpa_optimized.gds")
    optimized_parser.add_argument("--parameters-json")
    optimized_parser.add_argument("--jc-ua-per-um2", type=float, default=2.0)
    optimized_parser.add_argument("--max-iterations", type=int, default=4)
    optimized_parser.add_argument("--simulator", default="mock_jj")
    optimized_parser.add_argument("--analysis-mode", default="auto")
    optimized_parser.add_argument("--pump-current-fraction", type=float, default=0.017)
    optimized_parser.add_argument("--coupling-capacitance-ff", type=float)
    optimized_parser.add_argument("--resonator-capacitance-ff", type=float)
    optimized_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    optimized_parser.add_argument("--squid-asymmetry", type=float, default=0.0)
    optimized_parser.add_argument("--flux-sweep-span-phi0", type=float, default=1.0)
    optimized_parser.add_argument("--flux-sweep-points", type=int, default=101)
    optimized_parser.add_argument("--flux-period-current-ma", type=float)
    optimized_parser.add_argument("--flux-mutual-inductance-ph", type=float)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--pcell", default="manhattan_josephson_junction")
    compile_parser.add_argument("--parameters-json")
    compile_parser.add_argument("--output-name", default="layout.gds")

    drc_parser = subparsers.add_parser("drc")
    drc_parser.add_argument("gds_path")
    drc_parser.add_argument("--ruleset", default="builtin_min_bbox_width")
    drc_parser.add_argument("--min-width-um", type=float, default=0.1)

    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("sidecar_path")
    simulate_parser.add_argument("--simulator", default="mock_jj")
    simulate_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    simulate_parser.add_argument("--shunt-capacitance-ff", type=float, default=0.0)
    simulate_parser.add_argument(
        "--analysis-mode",
        choices=["auto", "multiport-ljpa", "single-port-reflection"],
        default="auto",
    )
    simulate_parser.add_argument("--pump-current-fraction", type=float, default=0.017)
    simulate_parser.add_argument("--coupling-capacitance-ff", type=float)
    simulate_parser.add_argument("--resonator-capacitance-ff", type=float)
    simulate_parser.add_argument("--adapter-executable")
    simulate_parser.add_argument("--target-frequency-ghz", type=float)
    simulate_parser.add_argument("--target-gain-db", type=float, default=20.0)
    simulate_parser.add_argument("--target-bandwidth-mhz", type=float)
    simulate_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    simulate_parser.add_argument("--squid-asymmetry", type=float, default=0.0)
    simulate_parser.add_argument("--flux-sweep-span-phi0", type=float, default=1.0)
    simulate_parser.add_argument("--flux-sweep-points", type=int, default=101)
    simulate_parser.add_argument("--flux-period-current-ma", type=float)
    simulate_parser.add_argument("--flux-mutual-inductance-ph", type=float)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("sidecar_path")
    extract_parser.add_argument("--no-gds-shapes", action="store_true")

    magic_parser = subparsers.add_parser("magic-extract")
    magic_parser.add_argument("gds_path")
    magic_parser.add_argument("--output-name")
    magic_parser.add_argument("--top-cell")
    magic_parser.add_argument("--tech-file")
    magic_parser.add_argument("--magic-executable", default="magic")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("gds_path")
    preview_parser.add_argument("--output-name")

    validation_parser = subparsers.add_parser("validate-roadmap")
    validation_parser.add_argument("--gds-path")
    validation_parser.add_argument("--sidecar-path")
    validation_parser.add_argument("--drc-path")
    validation_parser.add_argument("--extraction-path")
    validation_parser.add_argument("--simulation-path")
    validation_parser.add_argument("--cad-path")
    validation_parser.add_argument("--output-name", default="validation.json")

    cad_parser = subparsers.add_parser("cad-export")
    cad_parser.add_argument("gds_path")
    cad_parser.add_argument("--output-name")

    plot_parser = subparsers.add_parser("scientific-plot")
    plot_parser.add_argument("simulation_path")
    plot_parser.add_argument("--output-name")
    plot_parser.add_argument("--title")

    rf_parser = subparsers.add_parser("rf-export")
    rf_parser.add_argument("simulation_path")
    rf_parser.add_argument("--output-name")
    rf_parser.add_argument("--reference-ohm", type=float, default=50.0)

    openems_parser = subparsers.add_parser("openems-project")
    openems_parser.add_argument("sidecar_path")
    openems_parser.add_argument("--output-name")
    openems_parser.add_argument("--target-frequency-ghz", type=float)

    measurement_parser = subparsers.add_parser("measurement-plan")
    measurement_parser.add_argument("sidecar_path")
    measurement_parser.add_argument("--simulation-path")
    measurement_parser.add_argument("--output-name")

    hamiltonian_parser = subparsers.add_parser("hamiltonian-model")
    hamiltonian_parser.add_argument("sidecar_path")
    hamiltonian_parser.add_argument("--output-name")
    hamiltonian_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    hamiltonian_parser.add_argument("--capacitance-ff", type=float)
    hamiltonian_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    hamiltonian_parser.add_argument("--squid-asymmetry", type=float, default=0.0)

    qmetal_parser = subparsers.add_parser("quantum-metal-bridge")
    qmetal_parser.add_argument("sidecar_path")
    qmetal_parser.add_argument("--output-name")

    jpa_parser = subparsers.add_parser("jpa-analysis")
    jpa_parser.add_argument("sidecar_path")
    jpa_parser.add_argument("--output-name")
    jpa_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    jpa_parser.add_argument("--target-frequency-ghz", type=float)
    jpa_parser.add_argument("--target-bandwidth-mhz", type=float)
    jpa_parser.add_argument("--n-pump-points", type=int, default=16)

    report_parser = subparsers.add_parser("scientific-report")
    report_parser.add_argument("sidecar_path")
    report_parser.add_argument("--output-name")
    report_parser.add_argument("--gds-layout-png")
    report_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    report_parser.add_argument("--target-frequency-ghz", type=float)
    report_parser.add_argument("--target-bandwidth-mhz", type=float)
    report_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    report_parser.add_argument("--squid-asymmetry", type=float, default=0.05)

    research_optimizer = subparsers.add_parser("research-optimize")
    research_optimizer.add_argument("sidecar_path")
    research_optimizer.add_argument("--output-name")
    research_optimizer.add_argument("--n-trials", type=int, default=16)
    research_optimizer.add_argument("--target-frequency-ghz", type=float, default=5.0)
    research_optimizer.add_argument("--target-gain-db", type=float, default=20.0)
    research_optimizer.add_argument("--target-bandwidth-mhz", type=float, default=500.0)
    research_optimizer.add_argument("--min-p1db-dbm", type=float, default=-100.0)
    research_optimizer.add_argument("--force-fallback", action="store_true")

    sweep_parser = subparsers.add_parser("sweep")
    sweep_parser.add_argument("sidecar_path")
    sweep_parser.add_argument("--sweep-parameter", default="jc_ua_per_um2")
    sweep_parser.add_argument("--start", type=float, default=0.5)
    sweep_parser.add_argument("--stop", type=float, default=5.0)
    sweep_parser.add_argument("--points", type=int, default=9)
    sweep_parser.add_argument("--output-name")
    sweep_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    sweep_parser.add_argument("--shunt-capacitance-ff", type=float, default=0.0)
    sweep_parser.add_argument("--target-frequency-ghz", type=float)
    sweep_parser.add_argument("--target-gain-db", type=float, default=20.0)
    sweep_parser.add_argument("--target-bandwidth-mhz", type=float)
    sweep_parser.add_argument("--pump-current-fraction", type=float, default=0.017)
    sweep_parser.add_argument("--coupling-capacitance-ff", type=float)
    sweep_parser.add_argument("--resonator-capacitance-ff", type=float)
    sweep_parser.add_argument("--flux-bias-phi0", type=float, default=0.0)
    sweep_parser.add_argument("--squid-asymmetry", type=float, default=0.0)
    sweep_parser.add_argument("--flux-sweep-span-phi0", type=float, default=1.0)
    sweep_parser.add_argument("--flux-sweep-points", type=int, default=101)
    sweep_parser.add_argument("--flux-period-current-ma", type=float)
    sweep_parser.add_argument("--flux-mutual-inductance-ph", type=float)

    ui_parser = subparsers.add_parser("ui")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8765)

    toolchain_parser = subparsers.add_parser("toolchain")
    toolchain_parser.add_argument("--pcell", default="manhattan_josephson_junction")
    toolchain_parser.add_argument("--parameters-json")
    toolchain_parser.add_argument("--output-name", default="layout.gds")
    toolchain_parser.add_argument("--jc-ua-per-um2", type=float, default=1.0)
    toolchain_parser.add_argument("--shunt-capacitance-ff", type=float, default=0.0)

    args = parser.parse_args()
    server = _load_server_module()

    if args.command == "pcells":
        _print_json(server.list_pcells())
        return

    if args.command == "simulators":
        _print_json(server.list_simulators())
        return

    if args.command == "research-integrations":
        _print_json(server.list_research_integrations())
        return

    if args.command == "plan-ljpa":
        _print_json(server.plan_ljpa(args.prompt))
        return

    if args.command == "design-workflow":
        _print_json(
            server.run_design_workflow(
                prompt=args.prompt,
                output_name=args.output_name,
                parameters=_parameters(args.parameters_json),
                jc_ua_per_um2=args.jc_ua_per_um2,
                simulator=args.simulator,
                analysis_mode=args.analysis_mode,
                pump_current_fraction=args.pump_current_fraction,
                coupling_capacitance_ff=args.coupling_capacitance_ff,
                resonator_capacitance_ff=args.resonator_capacitance_ff,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
                flux_sweep_span_phi0=args.flux_sweep_span_phi0,
                flux_sweep_points=args.flux_sweep_points,
                flux_period_current_ma=args.flux_period_current_ma,
                flux_mutual_inductance_ph=args.flux_mutual_inductance_ph,
            )
        )
        return

    if args.command == "optimize-design":
        _print_json(
            server.run_optimized_design_workflow(
                prompt=args.prompt,
                output_name=args.output_name,
                parameters=_parameters(args.parameters_json),
                jc_ua_per_um2=args.jc_ua_per_um2,
                max_iterations=args.max_iterations,
                simulator=args.simulator,
                analysis_mode=args.analysis_mode,
                pump_current_fraction=args.pump_current_fraction,
                coupling_capacitance_ff=args.coupling_capacitance_ff,
                resonator_capacitance_ff=args.resonator_capacitance_ff,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
                flux_sweep_span_phi0=args.flux_sweep_span_phi0,
                flux_sweep_points=args.flux_sweep_points,
                flux_period_current_ma=args.flux_period_current_ma,
                flux_mutual_inductance_ph=args.flux_mutual_inductance_ph,
            )
        )
        return

    if args.command == "ui":
        ui = _load_ui_module()
        ui.serve_workbench(host=args.host, port=args.port)
        return

    if args.command == "compile":
        _print_json(
            server.compile_layout(
                pcell=args.pcell,
                parameters=_parameters(args.parameters_json),
                output_name=args.output_name,
            )
        )
        return

    if args.command == "drc":
        _print_json(
            server.run_drc(
                gds_path=args.gds_path,
                ruleset=args.ruleset,
                min_width_um=args.min_width_um,
            )
        )
        return

    if args.command == "simulate":
        _print_json(
            server.run_simulation(
                sidecar_path=args.sidecar_path,
                simulator=args.simulator,
                jc_ua_per_um2=args.jc_ua_per_um2,
                shunt_capacitance_ff=args.shunt_capacitance_ff,
                analysis_mode=args.analysis_mode,
                pump_current_fraction=args.pump_current_fraction,
                coupling_capacitance_ff=args.coupling_capacitance_ff,
                resonator_capacitance_ff=args.resonator_capacitance_ff,
                adapter_executable=args.adapter_executable,
                target_frequency_ghz=args.target_frequency_ghz,
                target_gain_db=args.target_gain_db,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
                flux_sweep_span_phi0=args.flux_sweep_span_phi0,
                flux_sweep_points=args.flux_sweep_points,
                flux_period_current_ma=args.flux_period_current_ma,
                flux_mutual_inductance_ph=args.flux_mutual_inductance_ph,
            )
        )
        return

    if args.command == "extract":
        _print_json(
            server.extract_layout(
                sidecar_path=args.sidecar_path,
                include_gds_shapes=not args.no_gds_shapes,
            )
        )
        return

    if args.command == "magic-extract":
        _print_json(
            server.run_magic_extract(
                gds_path=args.gds_path,
                output_name=args.output_name,
                top_cell=args.top_cell,
                tech_file=args.tech_file,
                magic_executable=args.magic_executable,
            )
        )
        return

    if args.command == "preview":
        _print_json(server.export_3d_preview(args.gds_path, output_name=args.output_name))
        return

    if args.command == "validate-roadmap":
        _print_json(
            server.run_validation_checklist(
                gds_path=args.gds_path,
                sidecar_path=args.sidecar_path,
                drc_path=args.drc_path,
                extraction_path=args.extraction_path,
                simulation_path=args.simulation_path,
                cad_path=args.cad_path,
                output_name=args.output_name,
            )
        )
        return

    if args.command == "cad-export":
        _print_json(server.export_cad_artifacts(args.gds_path, output_name=args.output_name))
        return

    if args.command == "scientific-plot":
        _print_json(
            server.export_scientific_plot(
                args.simulation_path,
                output_name=args.output_name,
                title=args.title,
            )
        )
        return

    if args.command == "rf-export":
        _print_json(
            server.export_rf_network(
                args.simulation_path,
                output_name=args.output_name,
                reference_ohm=args.reference_ohm,
            )
        )
        return

    if args.command == "openems-project":
        _print_json(
            server.export_openems_project(
                args.sidecar_path,
                output_name=args.output_name,
                target_frequency_ghz=args.target_frequency_ghz,
            )
        )
        return

    if args.command == "measurement-plan":
        _print_json(
            server.export_measurement_plan(
                args.sidecar_path,
                simulation_path=args.simulation_path,
                output_name=args.output_name,
            )
        )
        return

    if args.command == "hamiltonian-model":
        _print_json(
            server.export_hamiltonian_model(
                args.sidecar_path,
                output_name=args.output_name,
                jc_ua_per_um2=args.jc_ua_per_um2,
                capacitance_ff=args.capacitance_ff,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
            )
        )
        return

    if args.command == "quantum-metal-bridge":
        _print_json(
            server.export_quantum_metal_bridge(
                args.sidecar_path,
                output_name=args.output_name,
            )
        )
        return

    if args.command == "jpa-analysis":
        _print_json(
            server.export_jpa_analysis(
                args.sidecar_path,
                output_name=args.output_name,
                jc_ua_per_um2=args.jc_ua_per_um2,
                target_frequency_ghz=args.target_frequency_ghz,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
                n_pump_points=args.n_pump_points,
            )
        )
        return

    if args.command == "scientific-report":
        _print_json(
            server.export_scientific_report(
                args.sidecar_path,
                gds_layout_png=args.gds_layout_png,
                output_name=args.output_name,
                jc_ua_per_um2=args.jc_ua_per_um2,
                target_frequency_ghz=args.target_frequency_ghz,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
            )
        )
        return

    if args.command == "research-optimize":
        _print_json(
            server.run_research_optimization(
                args.sidecar_path,
                output_name=args.output_name,
                n_trials=args.n_trials,
                target_frequency_ghz=args.target_frequency_ghz,
                target_gain_db=args.target_gain_db,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
                min_p1db_dbm=args.min_p1db_dbm,
                force_fallback=args.force_fallback,
            )
        )
        return

    if args.command == "sweep":
        _print_json(
            server.run_parameter_sweep(
                args.sidecar_path,
                sweep_parameter=args.sweep_parameter,
                start=args.start,
                stop=args.stop,
                points=args.points,
                output_name=args.output_name,
                jc_ua_per_um2=args.jc_ua_per_um2,
                shunt_capacitance_ff=args.shunt_capacitance_ff,
                target_frequency_ghz=args.target_frequency_ghz,
                target_gain_db=args.target_gain_db,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
                pump_current_fraction=args.pump_current_fraction,
                coupling_capacitance_ff=args.coupling_capacitance_ff,
                resonator_capacitance_ff=args.resonator_capacitance_ff,
                flux_bias_phi0=args.flux_bias_phi0,
                squid_asymmetry=args.squid_asymmetry,
                flux_sweep_span_phi0=args.flux_sweep_span_phi0,
                flux_sweep_points=args.flux_sweep_points,
                flux_period_current_ma=args.flux_period_current_ma,
                flux_mutual_inductance_ph=args.flux_mutual_inductance_ph,
            )
        )
        return

    compiled = server.compile_layout(
        pcell=args.pcell,
        parameters=_parameters(args.parameters_json),
        output_name=args.output_name,
    )
    drc = server.run_drc(compiled["gds_path"])
    extraction = server.extract_layout(compiled["sidecar_path"])
    magic = server.run_magic_extract(compiled["gds_path"])
    preview = server.export_3d_preview(compiled["gds_path"])
    cad = server.export_cad_artifacts(compiled["gds_path"])
    simulation = server.run_simulation(
        compiled["sidecar_path"],
        jc_ua_per_um2=args.jc_ua_per_um2,
        shunt_capacitance_ff=args.shunt_capacitance_ff,
    )
    rf = server.export_rf_network(
        simulation["result_path"],
        output_name=Path(args.output_name).stem,
    )
    validation = server.run_validation_checklist(
        gds_path=compiled["gds_path"],
        sidecar_path=compiled["sidecar_path"],
        drc_path=drc["report_path"],
        extraction_path=extraction["result_path"],
        simulation_path=simulation["result_path"],
        cad_path=cad["report_path"],
        output_name=f"{Path(args.output_name).stem}.validation.json",
    )
    _print_json(
        {
            "compile": compiled,
            "drc": drc,
            "extraction": extraction,
            "magic": magic,
            "preview": preview,
            "cad": cad,
            "simulation": simulation,
            "rf": rf,
            "validation": validation,
        }
    )


if __name__ == "__main__":
    main()
