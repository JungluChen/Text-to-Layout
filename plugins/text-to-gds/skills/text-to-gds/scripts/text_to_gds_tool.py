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

    plan_parser = subparsers.add_parser("plan-ljpa")
    plan_parser.add_argument("prompt")

    workflow_parser = subparsers.add_parser("design-workflow")
    workflow_parser.add_argument("prompt")
    workflow_parser.add_argument("--output-name", default="ljpa_seed.gds")
    workflow_parser.add_argument("--parameters-json")
    workflow_parser.add_argument("--jc-ua-per-um2", type=float, default=2.0)

    optimized_parser = subparsers.add_parser("optimize-design")
    optimized_parser.add_argument("prompt")
    optimized_parser.add_argument("--output-name", default="ljpa_optimized.gds")
    optimized_parser.add_argument("--parameters-json")
    optimized_parser.add_argument("--jc-ua-per-um2", type=float, default=2.0)
    optimized_parser.add_argument("--max-iterations", type=int, default=4)

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
    simulate_parser.add_argument("--adapter-executable")
    simulate_parser.add_argument("--target-frequency-ghz", type=float)
    simulate_parser.add_argument("--target-gain-db", type=float, default=20.0)
    simulate_parser.add_argument("--target-bandwidth-mhz", type=float)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("sidecar_path")
    extract_parser.add_argument("--no-gds-shapes", action="store_true")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("gds_path")
    preview_parser.add_argument("--output-name")

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
                adapter_executable=args.adapter_executable,
                target_frequency_ghz=args.target_frequency_ghz,
                target_gain_db=args.target_gain_db,
                target_bandwidth_mhz=args.target_bandwidth_mhz,
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

    if args.command == "preview":
        _print_json(server.export_3d_preview(args.gds_path, output_name=args.output_name))
        return

    compiled = server.compile_layout(
        pcell=args.pcell,
        parameters=_parameters(args.parameters_json),
        output_name=args.output_name,
    )
    drc = server.run_drc(compiled["gds_path"])
    extraction = server.extract_layout(compiled["sidecar_path"])
    preview = server.export_3d_preview(compiled["gds_path"])
    simulation = server.run_simulation(
        compiled["sidecar_path"],
        jc_ua_per_um2=args.jc_ua_per_um2,
        shunt_capacitance_ff=args.shunt_capacitance_ff,
    )
    _print_json(
        {
            "compile": compiled,
            "drc": drc,
            "extraction": extraction,
            "preview": preview,
            "simulation": simulation,
        }
    )


if __name__ == "__main__":
    main()
