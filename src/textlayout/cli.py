"""Command-line interface for textlayout.

Four subcommands cover the usage modes from a single shared core:

    textlayout prompt "Create a 0.6 pF IDC ..." --out out/idc_demo  # NL -> closed loop
    textlayout generate spec.json --out out_dir   # DSL file -> verified artifacts
    textlayout verify   spec.json                 # DSL file -> verification report
    textlayout doctor                             # environment + solver health check
    textlayout serve    --host 0.0.0.0 --port 8000  # run the plugin API server
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textlayout import __version__, build_default_workflow, build_from_text_workflow
from textlayout.errors import TextLayoutError
from textlayout.schemas.dsl import LayoutSpec

if TYPE_CHECKING:  # pragma: no cover
    from textlayout.chip_lattice import QubitLattice
    from textlayout.epr import EPRResult
    from textlayout.measurement import MeasurementRecord, SimulatedPrediction


def _load_spec(path: str) -> LayoutSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return LayoutSpec.model_validate(data)


def _load_lattice(path: str) -> "QubitLattice":
    from textlayout.chip_lattice import QubitLattice

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return QubitLattice.model_validate(data)


def _cmd_prompt(args: argparse.Namespace) -> int:
    workflow = build_from_text_workflow()
    result = workflow.run(
        args.prompt,
        args.out,
        tolerance_percent=args.tolerance,
        execute_solver=not args.no_solver,
        solver_executable=args.executable,
    )
    payload = result.to_dict()
    if getattr(args, "include_epr", False):
        from textlayout.epr import render_markdown as render_epr_markdown
        from textlayout.epr import write_epr_report

        epr_result = _run_epr(result.spec, frequency_ghz=None)
        payload["epr"] = epr_result.to_dict()
        payload["epr_files"] = write_epr_report(epr_result, args.out)
        report_path = result.files.get("report")
        if report_path:
            _append_epr_section_to_report(Path(report_path), render_epr_markdown(epr_result))
    missing = result.missing_circuit_simulators
    if args.strict_simulation and missing:
        payload["strict_simulation_failure"] = (
            f"requested circuit simulators are not installed: {', '.join(missing)}"
        )
        print(json.dumps(payload, indent=2))
        return 3
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 2


def _cmd_generate(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    spec = _load_spec(args.spec)
    result = workflow.run(spec, output_dir=args.out)
    print(
        json.dumps(
            {
                "summary": result.summary,
                "verification": result.report.to_dict(),
                "files": dict(result.files),
            },
            indent=2,
        )
    )
    return 0 if result.report.passed else 2


def _append_epr_section_to_report(report_path: Path, epr_markdown: str) -> None:
    """Fold the EPR/coherence markdown into the main design report as one section.

    Demotes the EPR report's own top-level heading by one level so it nests
    under the design report instead of competing with it, then appends a
    horizontal rule + the demoted section. Never overwrites — the design
    report's capacitance/inductance content is untouched.
    """
    if not report_path.is_file():
        return
    demoted = "\n".join(
        f"#{line}" if line.startswith("#") else line for line in epr_markdown.splitlines()
    )
    existing = report_path.read_text(encoding="utf-8")
    report_path.write_text(existing.rstrip("\n") + "\n\n---\n\n" + demoted, encoding="utf-8")


def _cmd_verify(args: argparse.Namespace) -> int:
    workflow = build_default_workflow()
    spec = _load_spec(args.spec)
    report = workflow.verify_only(spec)
    payload = report.to_dict()
    if getattr(args, "include_epr", False):
        payload["epr"] = _run_epr(spec, frequency_ghz=args.frequency_ghz).to_dict()
    print(json.dumps(payload, indent=2))
    return 0 if report.passed else 2


def _run_epr(spec: LayoutSpec, *, frequency_ghz: float | None) -> "EPRResult":
    from textlayout.epr import default_epr_backend

    frequency = frequency_ghz
    if frequency is None:
        target = spec.target.get("frequency_ghz")
        frequency = float(target) if isinstance(target, (int, float)) and target > 0 else 6.0
    return default_epr_backend().analyze(spec, frequency_ghz=frequency)


def _cmd_epr(args: argparse.Namespace) -> int:
    from textlayout.epr import EPR_STATUS_SKIPPED, write_epr_report

    spec = _load_spec(args.spec)
    result = _run_epr(spec, frequency_ghz=args.frequency_ghz)
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_epr_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.status != EPR_STATUS_SKIPPED or not args.strict else 3


def _cmd_yield_jj(args: argparse.Namespace) -> int:
    from textlayout.yield_model import (
        FrequencyTarget,
        JJProcessModel,
        JunctionGeometry,
        run_jj_yield,
        write_yield_report,
    )

    process = JJProcessModel(
        target_jc_ua_per_um2=args.jc,
        wafer_jc_sigma_pct=args.wafer_sigma_pct,
        local_jc_sigma_pct=args.local_sigma_pct,
        cd_sigma_nm=args.cd_sigma_nm,
        junction_area_bias_um2=args.area_bias_um2,
        spatial_gradient_pct_per_mm=args.gradient_pct_per_mm,
    )
    junction = JunctionGeometry(width_um=args.width_um, height_um=args.height_um)
    target = FrequencyTarget(target_ghz=args.target_ghz, tolerance_mhz=args.tolerance_mhz)
    result = run_jj_yield(
        process=process,
        junction=junction,
        shunt_c_pf=args.shunt_c_pf,
        target=target,
        n_samples=args.n_samples,
        seed=args.seed,
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_yield_qubit_array(args: argparse.Namespace) -> int:
    from textlayout.yield_model import (
        FrequencyTarget,
        JJProcessModel,
        JunctionGeometry,
        run_qubit_array_yield,
        write_yield_report,
    )

    process = JJProcessModel(
        target_jc_ua_per_um2=args.jc,
        wafer_jc_sigma_pct=args.wafer_sigma_pct,
        local_jc_sigma_pct=args.local_sigma_pct,
        cd_sigma_nm=args.cd_sigma_nm,
        junction_area_bias_um2=args.area_bias_um2,
        spatial_gradient_pct_per_mm=args.gradient_pct_per_mm,
    )
    junction = JunctionGeometry(width_um=args.width_um, height_um=args.height_um)
    target = FrequencyTarget(target_ghz=args.target_ghz, tolerance_mhz=args.tolerance_mhz)
    result = run_qubit_array_yield(
        process=process,
        junction=junction,
        shunt_c_pf=args.shunt_c_pf,
        target=target,
        n_qubits=args.n_qubits,
        n_chips=args.n_chips,
        qubit_pitch_mm=args.qubit_pitch_mm,
        seed=args.seed,
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_chip_analyze(args: argparse.Namespace) -> int:
    from textlayout.chip_lattice import run_chip_collision_yield, write_chip_yield_report

    lattice = _load_lattice(args.lattice)
    result = run_chip_collision_yield(lattice, n_samples=args.n_samples, seed=args.seed)
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_chip_yield_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.nominal_report.collision_free or not args.strict else 2


def _cmd_chip_optimize(args: argparse.Namespace) -> int:
    from textlayout.chip_lattice import optimize_frequencies, write_chip_optimize_report

    lattice = _load_lattice(args.lattice)
    result = optimize_frequencies(
        lattice, max_retune_mhz=args.max_retune_mhz, step_mhz=args.step_mhz
    )
    payload = result.to_dict()
    if args.out:
        payload["files"] = write_chip_optimize_report(result, args.out)
    print(json.dumps(payload, indent=2))
    return 0 if result.after.collision_free or not args.strict else 2


def _cmd_pdk_list(args: argparse.Namespace) -> int:
    from textlayout import build_default_workflow

    workflow = build_default_workflow()
    print(json.dumps({"technologies": workflow.technology_names}, indent=2))
    return 0


def _cmd_pdk_info(args: argparse.Namespace) -> int:
    from textlayout.knowledge.technology_library import PDKS_DIR
    from textlayout.pdk import load_pdk

    for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
        pdk = load_pdk(pdk_path)
        if pdk.name == args.name:
            payload = pdk.model_dump(mode="json")
            print(json.dumps(payload, indent=2))
            return 0
    print(
        json.dumps(
            {
                "error": "not a PDK-backed technology",
                "message": (
                    f"{args.name!r} is not loaded from a PDK YAML (it may be the "
                    "built-in generic_2metal Technology, which predates the PDK "
                    "schema). No richer PDK metadata is available."
                ),
            }
        ),
        file=sys.stderr,
    )
    return 1


def _load_predictions(path: str) -> "list[SimulatedPrediction]":
    from textlayout.measurement import SimulatedPrediction

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [SimulatedPrediction.model_validate(item) for item in data]


def _load_measurements(path: str) -> "list[MeasurementRecord]":
    from textlayout.measurement import MeasurementRecord

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [MeasurementRecord.model_validate(item) for item in data]


def _cmd_measurement_compare(args: argparse.Namespace) -> int:
    from textlayout.measurement import compare_all, pair_by_design_hash, write_comparison_report

    predictions = _load_predictions(args.predicted)
    measurements = _load_measurements(args.measured)
    pairs = pair_by_design_hash(predictions, measurements)
    residuals = compare_all(pairs)
    payload: dict[str, object] = {"residuals": [r.model_dump(mode="json") for r in residuals]}
    if args.out:
        payload["files"] = write_comparison_report(residuals, args.out)
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_measurement_calibrate(args: argparse.Namespace) -> int:
    from textlayout.measurement import (
        build_calibration,
        write_calibration,
        write_calibration_report,
    )

    predictions = _load_predictions(args.predicted)
    measurements = _load_measurements(args.measured)
    calibration = build_calibration(predictions, measurements, synthetic=not args.production)
    payload = calibration.to_dict()
    if args.out:
        files = {
            "calibration": str(write_calibration(calibration, Path(args.out) / "calibration.yaml"))
        }
        files.update(write_calibration_report(calibration, args.out))
        payload["files"] = files
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from textlayout.doctor import render_text, run_doctor

    report = run_doctor(
        output_dir=args.out,
        strict=args.strict,
        strict_em=args.strict_em,
        strict_fullchip=args.strict_fullchip,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_text(report))
    return 0 if report.ok else 1


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "textlayout.backend.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=False,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="textlayout", description="Text-to-Layout CLI")
    parser.add_argument("--version", action="version", version=f"textlayout {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser(
        "prompt",
        help="Natural-language request -> intent, layout, verification, simulation, report.",
    )
    p_prompt.add_argument(
        "prompt", help="e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'"
    )
    p_prompt.add_argument("--out", default="out/textlayout_prompt", help="Output directory.")
    p_prompt.add_argument("--tolerance", type=float, default=5.0, help="Tolerance in percent.")
    p_prompt.add_argument(
        "--no-solver",
        action="store_true",
        help="Prepare solver inputs but do not attempt to execute a solver.",
    )
    p_prompt.add_argument(
        "--executable",
        default=None,
        help="Explicit component solver path (FasterCap, Octave/openEMS, FastHenry, or JoSIM).",
    )
    p_prompt.add_argument(
        "--strict-simulation",
        action="store_true",
        help="Exit non-zero when a requested circuit simulator (JoSIM/PSCAN2/WRspice) "
        "is not installed. Default: prepare inputs and report the absence honestly.",
    )
    p_prompt.add_argument(
        "--include-epr",
        action="store_true",
        help="Append an EPR_ANALYTICAL_ONLY loss-participation / coherence estimate to "
        "the design report (epr_report.json/.md alongside the usual artifacts). "
        "Capacitance/inductance accuracy does not imply coherence accuracy.",
    )
    p_prompt.set_defaults(func=_cmd_prompt)

    p_gen = sub.add_parser("generate", help="Generate verified artifacts from a DSL file.")
    p_gen.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_gen.add_argument("--out", default="workspace/textlayout", help="Output directory.")
    p_gen.set_defaults(func=_cmd_generate)

    p_ver = sub.add_parser("verify", help="Verify a DSL file (no export).")
    p_ver.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_ver.add_argument(
        "--include-epr",
        action="store_true",
        help="Append an EPR_ANALYTICAL_ONLY loss-participation / coherence estimate "
        "to the verification report.",
    )
    p_ver.add_argument(
        "--frequency-ghz",
        type=float,
        default=None,
        help="Frequency for the EPR coherence estimate (default: spec target or 6 GHz).",
    )
    p_ver.set_defaults(func=_cmd_verify)

    p_epr = sub.add_parser(
        "epr",
        help="Loss-participation (EPR) and coherence estimate for a DSL file. "
        "EPR_ANALYTICAL_ONLY by default; never a field solution.",
    )
    p_epr.add_argument("spec", help="Path to a Layout DSL JSON file.")
    p_epr.add_argument(
        "--frequency-ghz",
        type=float,
        default=None,
        help="Analysis frequency (default: spec target frequency or 6 GHz).",
    )
    p_epr.add_argument("--out", default=None, help="Directory for epr_report.json / epr_report.md.")
    p_epr.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the EPR backend is unavailable (skipped).",
    )
    p_epr.set_defaults(func=_cmd_epr)

    p_doc = sub.add_parser("doctor", help="Check the environment (imports, solvers, write perms).")
    p_doc.add_argument("--out", default="out", help="Output directory to probe for writability.")
    p_doc.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_doc.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing external solvers as failures. Default: report them as optional.",
    )
    p_doc.add_argument(
        "--strict-em",
        action="store_true",
        help="Require openEMS, CSXCAD, Octave interfaces, and scikit-rf.",
    )
    p_doc.add_argument(
        "--strict-fullchip",
        action="store_true",
        help="Require Palace, Gmsh, and meshio for the future full-chip FEM path.",
    )
    p_doc.set_defaults(func=_cmd_doctor)

    p_srv = sub.add_parser("serve", help="Run the FastAPI plugin server.")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.set_defaults(func=_cmd_serve)

    p_yield = sub.add_parser(
        "yield",
        help="JJ critical-current variability / fabrication-yield Monte Carlo. "
        "Drawing one SQUID loop proves geometry, not manufacturability.",
    )
    yield_sub = p_yield.add_subparsers(dest="yield_command", required=True)

    def _add_process_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--jc", type=float, required=True, help="Target Jc (uA/um^2).")
        p.add_argument(
            "--wafer-sigma-pct",
            type=float,
            required=True,
            help="Wafer-to-wafer Jc sigma (%% of mean).",
        )
        p.add_argument(
            "--local-sigma-pct",
            type=float,
            required=True,
            help="Junction-to-junction local Jc sigma (%% of mean).",
        )
        p.add_argument(
            "--cd-sigma-nm",
            type=float,
            default=0.0,
            help="Lithography CD sigma per linear dimension (nm).",
        )
        p.add_argument(
            "--area-bias-um2",
            type=float,
            default=0.0,
            help="Systematic junction-area bias (um^2).",
        )
        p.add_argument(
            "--gradient-pct-per-mm",
            type=float,
            default=0.0,
            help="Optional linear Jc gradient across the chip (%% of mean per mm).",
        )
        p.add_argument("--width-um", type=float, required=True, help="Drawn junction width (um).")
        p.add_argument("--height-um", type=float, required=True, help="Drawn junction height (um).")
        p.add_argument("--shunt-c-pf", type=float, required=True, help="Shunt capacitance (pF).")
        p.add_argument("--target-ghz", type=float, required=True, help="Target frequency (GHz).")
        p.add_argument(
            "--tolerance-mhz",
            type=float,
            required=True,
            help="Acceptance half-window (MHz).",
        )
        p.add_argument("--seed", type=int, default=1234, help="Monte Carlo seed (reproducible).")
        p.add_argument("--out", default=None, help="Directory for the JSON/Markdown yield report.")

    p_yield_jj = yield_sub.add_parser(
        "jj", help="Single junction/mode yield: frequency distribution, hit rate, CI95."
    )
    _add_process_args(p_yield_jj)
    p_yield_jj.add_argument("--n-samples", type=int, default=5000, help="Monte Carlo sample count.")
    p_yield_jj.set_defaults(func=_cmd_yield_jj)

    p_yield_array = yield_sub.add_parser(
        "qubit-array",
        help="Chip-level yield: probability that ALL qubits on a chip are simultaneously in spec.",
    )
    _add_process_args(p_yield_array)
    p_yield_array.add_argument(
        "--n-qubits", type=int, required=True, help="Qubits per chip that must all pass."
    )
    p_yield_array.add_argument(
        "--n-chips", type=int, default=2000, help="Simulated chips (Monte Carlo trials)."
    )
    p_yield_array.add_argument(
        "--qubit-pitch-mm",
        type=float,
        default=1.0,
        help="Synthetic qubit placement pitch for the spatial gradient (mm).",
    )
    p_yield_array.set_defaults(func=_cmd_yield_qubit_array)

    p_chip = sub.add_parser(
        "chip",
        help="Multi-qubit chip-level frequency-collision analysis. A single-device "
        "closed loop cannot answer whether a processor works.",
    )
    chip_sub = p_chip.add_subparsers(dest="chip_command", required=True)

    p_chip_analyze = chip_sub.add_parser(
        "analyze",
        help="Deterministic + Monte Carlo collision analysis of a qubit lattice JSON file.",
    )
    p_chip_analyze.add_argument("lattice", help="Path to a QubitLattice JSON file.")
    p_chip_analyze.add_argument(
        "--n-samples", type=int, default=2000, help="Monte Carlo sample count."
    )
    p_chip_analyze.add_argument("--seed", type=int, default=1234, help="Monte Carlo seed.")
    p_chip_analyze.add_argument(
        "--out",
        default=None,
        help="Directory for chip_yield_report.json/.md and collision_matrix.csv.",
    )
    p_chip_analyze.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the nominal (target-frequency) lattice has any collision.",
    )
    p_chip_analyze.set_defaults(func=_cmd_chip_analyze)

    p_chip_optimize = chip_sub.add_parser(
        "optimize",
        help="Greedily retune target frequencies to reduce/eliminate collisions.",
    )
    p_chip_optimize.add_argument("lattice", help="Path to a QubitLattice JSON file.")
    p_chip_optimize.add_argument(
        "--max-retune-mhz",
        type=float,
        default=300.0,
        help="Max allowed retune from each qubit's original target (MHz).",
    )
    p_chip_optimize.add_argument(
        "--step-mhz", type=float, default=5.0, help="Greedy search step size (MHz)."
    )
    p_chip_optimize.add_argument(
        "--out",
        default=None,
        help="Directory for chip_optimize_report.json/.md.",
    )
    p_chip_optimize.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the optimizer does not reach a collision-free result.",
    )
    p_chip_optimize.set_defaults(func=_cmd_chip_optimize)

    p_pdk = sub.add_parser(
        "pdk",
        help="Foundry PDK abstraction: list registered technologies or inspect a PDK's "
        "full provenance and process parameters.",
    )
    pdk_sub = p_pdk.add_subparsers(dest="pdk_command", required=True)

    p_pdk_list = pdk_sub.add_parser(
        "list", help="List all registered technology names (LayoutSpec.technology values)."
    )
    p_pdk_list.set_defaults(func=_cmd_pdk_list)

    p_pdk_info = pdk_sub.add_parser(
        "info", help="Print full PDK metadata (version, foundry_validated, layers, source)."
    )
    p_pdk_info.add_argument("name", help="PDK name, e.g. 'example_superconducting_pdk'.")
    p_pdk_info.set_defaults(func=_cmd_pdk_info)

    p_measurement = sub.add_parser(
        "measurement",
        help="Simulation-vs-measurement correlation: the path from illustrative to "
        "fab-calibrated numbers.",
    )
    measurement_sub = p_measurement.add_subparsers(dest="measurement_command", required=True)

    p_meas_compare = measurement_sub.add_parser(
        "compare",
        help="Residual table: simulated/predicted vs measured, per device per quantity.",
    )
    p_meas_compare.add_argument(
        "--predicted", required=True, help="Path to a JSON list of SimulatedPrediction."
    )
    p_meas_compare.add_argument(
        "--measured", required=True, help="Path to a JSON list of MeasurementRecord."
    )
    p_meas_compare.add_argument(
        "--out", default=None, help="Directory for measurement_comparison.json/.md."
    )
    p_meas_compare.set_defaults(func=_cmd_measurement_compare)

    p_meas_calibrate = measurement_sub.add_parser(
        "calibrate",
        help="Fit capacitance/inductance/loss-tangent/Jc correction factors from measurements.",
    )
    p_meas_calibrate.add_argument(
        "--predicted", required=True, help="Path to a JSON list of SimulatedPrediction."
    )
    p_meas_calibrate.add_argument(
        "--measured", required=True, help="Path to a JSON list of MeasurementRecord."
    )
    p_meas_calibrate.add_argument(
        "--production",
        action="store_true",
        help="Mark the resulting calibration as non-synthetic (real cooldown data only).",
    )
    p_meas_calibrate.add_argument(
        "--out",
        default=None,
        help="Directory for calibration.yaml and calibration_report.md.",
    )
    p_meas_calibrate.set_defaults(func=_cmd_measurement_calibrate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
        return result
    except TextLayoutError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
