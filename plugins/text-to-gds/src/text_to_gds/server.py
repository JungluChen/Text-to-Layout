from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from text_to_gds.adapters import (
    josephsoncircuits_plan_from_sidecar,
    josim_netlist_from_sidecar,
    list_simulation_adapters,
    ngspice_netlist_from_sidecar,
    run_josephsoncircuits,
    run_josim_transient,
    run_magic_extraction,
    run_ngspice,
    write_josephsoncircuits_script,
)
from text_to_gds.analytical import write_analytical_verification
from text_to_gds.cad_export import write_cad_artifacts
from text_to_gds.cryostat import analyze_cryogenic_chain
from text_to_gds.design import plan_ljpa_design
from text_to_gds.drc import parse_drc_report, run_external_klayout_drc, run_python_process_drc
from text_to_gds.extraction import (
    labels_from_gds,
    layer_bounding_boxes_from_gds,
    summarize_sidecar_parameters,
)
from text_to_gds.em_bridges import write_hfss_project_bridge, write_sonnet_project_bridge
from text_to_gds.em_solvers import list_em_solvers as list_em_solver_metadata
from text_to_gds.em_solvers import recommend_em_solver as recommend_em_solver_for_sidecar
from text_to_gds.open_solver_manager import open_eigenmode as run_open_eigenmode
from text_to_gds.open_solver_manager import route as route_open_solver_plan
from text_to_gds.open_q3d import OpenQ3D, tune_idc_capacitance as run_idc_tuning
from text_to_gds.feasibility_gate import check_design_feasibility as run_design_feasibility
from text_to_gds.physics_templates import (
    list_templates as list_device_templates,
    validate_sidecar as validate_device_template_sidecar,
)
from text_to_gds.review import review_committee
from text_to_gds.ai_scientist import assess_design, write_review_report
from text_to_gds.layout_understanding import summarize_layout as summarize_layout_circuit
from text_to_gds.open_benchmarks import run_open_benchmarks as run_open_benchmark_suite
from text_to_gds.solver_agreement import cross_validate
from text_to_gds.epr import write_epr_analysis
from text_to_gds.experiment_database import record_experiment
from text_to_gds.fitting import measurement_from_fit, write_measurement_fit
from text_to_gds.integrations import list_research_integrations as discover_research_integrations
from text_to_gds.improvements import (
    call_improvement,
    list_improvements as build_improvement_registry,
    validate_improvement_registry,
)
from text_to_gds.elmer_bridge import write_elmer_project
from text_to_gds.meshing import write_stack_mesh
from text_to_gds.optimization import optimize_ljpa_parameters
from text_to_gds.package_model import write_package_model
from text_to_gds.palace_bridge import write_palace_project
from text_to_gds.parasitics import export_fastcap as run_fastcap_extraction
from text_to_gds.parasitics import export_fasthenry as run_fasthenry_extraction
from text_to_gds.plots import write_simulation_plot
from text_to_gds.pcells import (
    cpw_quarter_wave_resonator,
    cpw_straight,
    dc_squid_pair,
    flux_bias_line,
    ground_plane,
    jj_ic_calibration_array,
    lumped_element_jpa_seed,
    manhattan_josephson_junction,
    meander_inductor,
    periodically_loaded_kit_unit_cell,
    photonic_crystal_stwpa,
    via_chain_monitor,
    via_stack,
)
from text_to_gds.preview import write_stack_preview
from text_to_gds.process import DEFAULT_PROCESS
from text_to_gds.rendering import (
    component_sidecar as _component_sidecar,
    render_layout_screenshot as _render_layout_screenshot,
    scan_min_width_violations as _scan_min_width_violations,
)
from text_to_gds.pyaedt_bridge import em_geometry_correction, write_pyaedt_project_bundle
from text_to_gds.pyaedt_benchmarks import run_pyaedt_benchmark_suite
from text_to_gds.research import (
    run_research_optimization as run_research_optimization_artifacts,
    write_hamiltonian_model,
    write_measurement_plan,
    write_openems_project,
    write_quantum_metal_bridge,
)
from text_to_gds.jpa_analysis import run_jpa_analysis
from text_to_gds.jtwpa import write_gaydamachenko_benchmark
from text_to_gds.measurement_recipes import RECIPES, write_measurement_recipe
from text_to_gds.next_improvements import (
    call_next_improvement,
    list_next_improvements as build_next_improvement_registry,
    validate_next_improvement_registry,
)
from text_to_gds.paper_benchmarks import run_paper_benchmark_suite
from text_to_gds.pdk import PDKDatabase
from text_to_gds.process_database import (
    ProcessDatabase,
    plan_process_aware_jpa as build_process_aware_jpa_plan,
)
from text_to_gds.report import write_scientific_report
from text_to_gds.rf import write_rf_network_artifacts
from text_to_gds.scientific import write_scientific_plot, write_sweep_artifacts
from text_to_gds.simulation import estimate_physical_performance, simulate_ideal_junction
from text_to_gds.superconductivity import write_superconducting_material
from text_to_gds.third_wave import (
    call_third_wave_improvement,
    list_third_wave_improvements as build_third_wave_registry,
    validate_third_wave_registry,
)
from text_to_gds.traveling_wave import write_traveling_wave_paper_benchmark
from text_to_gds.uncertainty import run_process_monte_carlo
from text_to_gds.validation import build_validation_report
from text_to_gds.verification import (
    extract_circuit_from_gds,
    extract_equivalent_circuit as build_equivalent_circuit,
    generate_josephsoncircuits_model,
    generate_spice_netlist,
    generate_wafer_mask,
    run_superconducting_lvs,
)
from text_to_gds.workbench import write_design_workbench

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("TEXT_TO_GDS_WORKSPACE", PROJECT_ROOT / "workspace")).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts"

mcp = FastMCP("Text-to-GDS", json_response=True)

PCELL_REGISTRY = {
    "cpw_quarter_wave_resonator": cpw_quarter_wave_resonator,
    "cpw_straight": cpw_straight,
    "dc_squid_pair": dc_squid_pair,
    "flux_bias_line": flux_bias_line,
    "ground_plane": ground_plane,
    "jj_ic_calibration_array": jj_ic_calibration_array,
    "lumped_element_jpa_seed": lumped_element_jpa_seed,
    "manhattan_josephson_junction": manhattan_josephson_junction,
    "meander_inductor": meander_inductor,
    "periodically_loaded_kit_unit_cell": periodically_loaded_kit_unit_cell,
    "photonic_crystal_stwpa": photonic_crystal_stwpa,
    "via_chain_monitor": via_chain_monitor,
    "via_stack": via_stack,
}


def _ensure_dirs() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


def _artifact_path(name: str, suffix: str) -> Path:
    _ensure_dirs()
    filename = Path(name).name
    if Path(filename).suffix != suffix:
        filename = f"{Path(filename).stem or 'layout'}{suffix}"
    path = (ARTIFACT_ROOT / filename).resolve()
    if path != ARTIFACT_ROOT and ARTIFACT_ROOT not in path.parents:
        raise ValueError(f"Artifact path escapes workspace: {name}")
    return path


def _existing_path(path_value: str) -> Path:
    raw = Path(path_value)
    candidates = [raw] if raw.is_absolute() else [PROJECT_ROOT / raw, ARTIFACT_ROOT / raw.name]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError(f"File not found: {path_value}")


def _artifact_stem(name: str) -> str:
    filename = Path(name).name
    for suffix in (".sidecar.json", ".drc.json", ".simulation.json", ".extraction.json"):
        if filename.endswith(suffix):
            filename = filename[: -len(suffix)]
    return filename.rsplit(".", 1)[0] if filename.endswith((".gds", ".lyrdb", ".json")) else filename


@mcp.tool()
def compile_layout(
    pcell: str = "manhattan_josephson_junction",
    parameters: dict[str, Any] | None = None,
    output_name: str = "layout.gds",
) -> dict[str, Any]:
    """Compile a registered superconducting PCell into GDS and a semantic sidecar."""
    if pcell not in PCELL_REGISTRY:
        raise ValueError(f"Unknown PCell '{pcell}'. Available: {sorted(PCELL_REGISTRY)}")

    component = PCELL_REGISTRY[pcell](**(parameters or {}))
    gds_path = _artifact_path(output_name, ".gds")
    screenshot_path = gds_path.with_suffix(".layout.png")
    component.write_gds(str(gds_path))
    _render_layout_screenshot(gds_path, screenshot_path)

    sidecar = _component_sidecar(component, gds_path, pcell, screenshot_path)
    sidecar_path = gds_path.with_suffix(".sidecar.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    return {
        "status": "compiled",
        "gds_path": str(gds_path),
        "screenshot_path": str(screenshot_path),
        "sidecar_path": str(sidecar_path),
    }


@mcp.tool()
def run_drc(
    gds_path: str,
    ruleset: str = "builtin_min_bbox_width",
    min_width_um: float = 0.1,
) -> dict[str, Any]:
    """Run a local KLayout-backed min-width pass and emit a JSON DRC report."""
    layout_path = _existing_path(gds_path)
    violations: list[dict[str, Any]] = []
    scan_metadata: dict[str, Any] = {
        "engine": "input_check",
        "checked_shapes": 0,
        "warnings": [],
    }

    if layout_path.suffix.lower() != ".gds":
        violations.append(
            {
                "rule": "input_format",
                "message": "DRC input must be a .gds file.",
                "severity": "error",
            }
        )
    else:
        scan_violations, scan_metadata = _scan_min_width_violations(layout_path, min_width_um)
        violations.extend(scan_violations)

    report = {
        "schema": "text-to-gds.drc.v0",
        "engine": scan_metadata["engine"],
        "ruleset": ruleset,
        "input_gds": str(layout_path),
        "min_width_um": min_width_um,
        "status": "passed" if not violations else "failed",
        "checked_shapes": scan_metadata["checked_shapes"],
        "warnings": scan_metadata["warnings"],
        "violations": violations,
    }

    report_path = _artifact_path(f"{layout_path.stem}.drc.json", ".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


@mcp.tool()
def run_process_drc(
    gds_path: str,
    deck_path: str = "drc/superconducting_min_width.drc",
    output_name: str | None = None,
    klayout_executable: str = "klayout",
) -> dict[str, Any]:
    """Run an external headless KLayout DRC deck and normalize its report."""
    layout_path = _existing_path(gds_path)
    deck = _existing_path(deck_path)
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.process"
    lyrdb_path = _artifact_path(f"{stem}.lyrdb", ".lyrdb")
    command_result = run_external_klayout_drc(
        gds_path=layout_path,
        deck_path=deck,
        lyrdb_path=lyrdb_path,
        klayout_executable=klayout_executable,
    )

    violations: list[dict[str, Any]] = []
    warnings = list(command_result["warnings"])
    engine = command_result["engine"]
    checked_shapes = None
    checked_spacing_pairs = None
    if command_result["executed"] and command_result["returncode"] == 0:
        if lyrdb_path.exists():
            violations = parse_drc_report(lyrdb_path)
        else:
            warnings.append("KLayout command succeeded but did not write a .lyrdb report.")
    else:
        fallback = run_python_process_drc(layout_path)
        if fallback["executed"]:
            engine = fallback["engine"]
            checked_shapes = fallback["checked_shapes"]
            checked_spacing_pairs = fallback["checked_spacing_pairs"]
            violations = fallback["violations"]
            warnings.extend(fallback["warnings"])
            warnings.append(
                "External KLayout deck was unavailable or failed; used KLayout Python process "
                "rules instead."
            )
        else:
            warnings.extend(fallback["warnings"])

    if engine == command_result["engine"] and not command_result["executed"]:
        status = "skipped"
    elif command_result["returncode"] not in (None, 0) and engine == command_result["engine"]:
        status = "failed"
    else:
        status = "passed" if not violations else "failed"

    report = {
        "schema": "text-to-gds.drc.v0",
        "engine": engine,
        "ruleset": str(deck),
        "input_gds": str(layout_path),
        "status": status,
        "checked_shapes": checked_shapes,
        "checked_spacing_pairs": checked_spacing_pairs,
        "warnings": warnings,
        "violations": violations,
        "lyrdb_path": str(lyrdb_path),
        "command": command_result["command"],
        "returncode": command_result["returncode"],
        "stdout": command_result["stdout"],
        "stderr": command_result["stderr"],
    }
    report_path = _artifact_path(f"{stem}.drc.json", ".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


@mcp.tool()
def list_pcells() -> dict[str, Any]:
    """List registered PCells and the active process-stack defaults."""
    return {
        "schema": "text-to-gds.pcells.v0",
        "pcells": sorted(PCELL_REGISTRY),
        "process_stack": DEFAULT_PROCESS.to_dict(),
    }


@mcp.tool()
def extract_layout(sidecar_path: str, include_gds_shapes: bool = True) -> dict[str, Any]:
    """Summarize performance-relevant parameters from a sidecar and optional GDS scan."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    summary = summarize_sidecar_parameters(sidecar)
    if include_gds_shapes:
        summary["gds_shapes"] = layer_bounding_boxes_from_gds(sidecar["gds_path"])
        summary["labels"] = labels_from_gds(sidecar["gds_path"])

    output_path = _artifact_path(f"{sidecar_file.stem}.extraction.json", ".json")
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["result_path"] = str(output_path)
    return summary


@mcp.tool()
def run_magic_extract(
    gds_path: str,
    output_name: str | None = None,
    top_cell: str | None = None,
    tech_file: str | None = None,
    magic_executable: str = "magic",
) -> dict[str, Any]:
    """Run Magic VLSI GDS import/extraction/SPICE export when Magic is available."""
    layout_path = _existing_path(gds_path)
    tech_path = _existing_path(tech_file) if tech_file else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.magic"
    script_path = _artifact_path(f"{stem}.magic.tcl", ".tcl")
    report_path = _artifact_path(f"{stem}.magic.json", ".json")
    spice_path = _artifact_path(f"{stem}.magic.spice", ".spice")
    extract_path = _artifact_path(f"{stem}.magic.ext", ".ext")
    adapter_result = run_magic_extraction(
        gds_path=layout_path,
        script_path=script_path,
        report_path=report_path,
        spice_path=spice_path,
        extract_path=extract_path,
        top_cell=top_cell,
        tech_file=tech_path,
        magic_executable=magic_executable,
    )
    report = {
        "schema": "text-to-gds.magic-extraction.v0",
        "engine": "magic",
        "status": adapter_result["status"],
        "input_gds": str(layout_path),
        "top_cell": top_cell or layout_path.stem,
        "tech_file": str(tech_path) if tech_path else None,
        "script_path": str(script_path),
        "report_path": str(report_path),
        "spice_path": str(spice_path),
        "extract_path": str(extract_path),
        "adapter_result": adapter_result,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


@mcp.tool()
def list_simulators() -> dict[str, Any]:
    """List local external simulator adapters and installation hints."""
    return {
        "schema": "text-to-gds.simulators.v0",
        "adapters": list_simulation_adapters(),
    }


@mcp.tool()
def list_research_integrations() -> dict[str, Any]:
    """List optional upstream research integrations and their local availability."""
    return {
        "schema": "text-to-gds.research-integrations.v0",
        "integrations": discover_research_integrations(),
    }


@mcp.tool()
def list_fabrication_processes() -> dict[str, Any]:
    """List local measured fabrication-process records."""
    records = ProcessDatabase(PROJECT_ROOT / "process_database").list()
    return {
        "schema": "text-to-gds.fabrication-processes.v1",
        "processes": [record.raw for record in records],
    }


@mcp.tool()
def list_process_design_kits() -> dict[str, Any]:
    """List validated, versioned superconducting PDKs available to local workflows."""
    pdks = PDKDatabase(PROJECT_ROOT / "process").list()
    return {
        "schema": "text-to-gds.process-design-kits.v1",
        "process_design_kits": [pdk.to_dict() for pdk in pdks],
    }


@mcp.tool()
def inspect_process_design_kit(
    process_id: str,
    version: str | None = None,
    material: str | None = None,
    frequency_ghz: float = 6.0,
) -> dict[str, Any]:
    """Resolve a PDK version and optionally calculate one material's surface impedance."""
    pdk = PDKDatabase(PROJECT_ROOT / "process").get(process_id, version)
    result = {
        "schema": "text-to-gds.process-design-kit-inspection.v1",
        "process_design_kit": pdk.to_dict(),
        "legacy_process_stack": pdk.to_process_stack().to_dict(),
    }
    if material is not None:
        result["surface_impedance"] = {
            "material": material,
            **pdk.materials[material].surface_impedance(frequency_ghz * 1e9),
        }
    return result


@mcp.tool()
def list_improvement_functions() -> dict[str, Any]:
    """List and validate all 157 improvement-list implementations."""
    registry = build_improvement_registry()
    registry["validation"] = validate_improvement_registry()
    return registry


@mcp.tool()
def run_improvement_function(
    feature_id: int, arguments: dict[str, Any] | None = None
) -> Any:
    """Execute one registered improvement function with JSON-compatible arguments."""
    return call_improvement(feature_id, **(arguments or {}))


@mcp.tool()
def list_next_improvement_functions() -> dict[str, Any]:
    """List and import-validate all 146 functions in the Next Improvement List."""
    registry = build_next_improvement_registry()
    registry["validation"] = validate_next_improvement_registry()
    return registry


@mcp.tool()
def run_next_improvement_function(
    feature_id: int, arguments: dict[str, Any] | None = None
) -> Any:
    """Execute one next-list function with JSON-compatible arguments."""
    return call_next_improvement(feature_id, **(arguments or {}))


@mcp.tool()
def list_third_wave_improvement_functions() -> dict[str, Any]:
    """List and import-validate all 37 third-wave autonomous-scientist functions."""
    registry = build_third_wave_registry()
    registry["validation"] = validate_third_wave_registry()
    return registry


@mcp.tool()
def run_third_wave_improvement_function(
    feature_id: int, arguments: dict[str, Any] | None = None
) -> Any:
    """Execute one third-wave function with JSON-compatible arguments."""
    return call_third_wave_improvement(feature_id, **(arguments or {}))


@mcp.tool()
def extract_equivalent_circuit(
    sidecar_path: str, output_name: str | None = None
) -> dict[str, Any]:
    """Extract a circuit from GDS polygons or a sidecar, then generate SPICE and Julia."""
    source = _existing_path(sidecar_path)
    if source.suffix.lower() == ".gds":
        circuit = extract_circuit_from_gds(source)
    else:
        sidecar = json.loads(source.read_text(encoding="utf-8"))
        circuit = build_equivalent_circuit(sidecar)
    stem = _artifact_stem(output_name) if output_name else _artifact_stem(source.name)
    circuit_path = _artifact_path(f"{stem}.circuit.json", ".json")
    spice_path = _artifact_path(f"{stem}.spice", ".spice")
    julia_path = _artifact_path(f"{stem}.josephsoncircuits.jl", ".jl")
    circuit.update(
        {
            "circuit_path": str(circuit_path),
            "spice_path": str(spice_path),
            "josephsoncircuits_path": str(julia_path),
        }
    )
    circuit_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
    spice_path.write_text(generate_spice_netlist(circuit), encoding="utf-8")
    julia_path.write_text(generate_josephsoncircuits_model(circuit), encoding="utf-8")
    return circuit


@mcp.tool()
def run_lvs(extracted_circuit_path: str, schematic_path: str) -> dict[str, Any]:
    """Run superconducting LVS against a JSON or SPICE schematic."""
    extracted_path = _existing_path(extracted_circuit_path)
    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    result = run_superconducting_lvs(extracted, _existing_path(schematic_path))
    report_path = _artifact_path(f"{_artifact_stem(extracted_path.name)}.lvs.json", ".json")
    result["report_path"] = str(report_path)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


@mcp.tool()
def generate_wafer_level_mask(
    chip_gds: str,
    output_name: str = "wafer.gds",
    wafer_diameter_mm: float = 50.8,
    chip_width_mm: float = 5.0,
    chip_height_mm: float = 5.0,
    dicing_lane_um: float = 100.0,
    edge_exclusion_mm: float = 2.0,
) -> dict[str, Any]:
    """Generate a wafer GDS containing chip placements, dicing lanes, and alignment marks."""
    return generate_wafer_mask(
        _existing_path(chip_gds),
        _artifact_path(output_name, ".gds"),
        wafer_diameter_mm=wafer_diameter_mm,
        chip_width_mm=chip_width_mm,
        chip_height_mm=chip_height_mm,
        dicing_lane_um=dicing_lane_um,
        edge_exclusion_mm=edge_exclusion_mm,
    )


@mcp.tool()
def plan_process_aware_jpa(
    prompt: str,
    nominal_junction_area_um2: float = 0.0484,
) -> dict[str, Any]:
    """Correct a JPA design using a named process record and report expected Ic yield."""
    return build_process_aware_jpa_plan(
        prompt,
        database_root=PROJECT_ROOT / "process_database",
        nominal_junction_area_um2=nominal_junction_area_um2,
    )


@mcp.tool()
def run_uncertainty_analysis(
    process_name: str = "NCU 2025 AlOx process",
    output_name: str = "jpa-process-yield",
    samples: int = 5000,
    seed: int = 42,
    junction_area_um2: float = 0.0484,
    target_frequency_ghz: float = 6.0,
    target_gain_db: float = 20.0,
) -> dict[str, Any]:
    """Run process/lithography/capacitance Monte Carlo and write a yield report."""
    process = ProcessDatabase(PROJECT_ROOT / "process_database").get(process_name)
    stem = _artifact_stem(output_name)
    return run_process_monte_carlo(
        process.raw,
        report_path=_artifact_path(f"{stem}.uncertainty.json", ".json"),
        csv_path=_artifact_path(f"{stem}.uncertainty.csv", ".csv"),
        plot_path=_artifact_path(f"{stem}.yield_report.png", ".png"),
        samples=samples,
        seed=seed,
        junction_area_um2=junction_area_um2,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
    )


@mcp.tool()
def analyze_cryostat_input_chain(
    chain_path: str | None = None,
    source_temperature_k: float = 300.0,
) -> dict[str, Any]:
    """Calculate cryogenic chain Friis noise, pump power, and JPA headroom."""
    path = _existing_path(chain_path) if chain_path else PROJECT_ROOT / "cryostat" / "input_chain.yaml"
    return analyze_cryogenic_chain(path, source_temperature_k=source_temperature_k)


@mcp.tool()
def plan_ljpa(prompt: str) -> dict[str, Any]:
    """Convert an LJPA prompt into clarification questions and a local design workflow."""
    plan = plan_ljpa_design(prompt)
    processes = ProcessDatabase(PROJECT_ROOT / "process_database").list()
    if any(process.name.lower() in prompt.lower() for process in processes):
        plan["fabrication_process"] = build_process_aware_jpa_plan(
            prompt,
            database_root=PROJECT_ROOT / "process_database",
        )
    return plan


def _workflow_status_from_simulation(simulation: dict[str, Any]) -> str:
    adapter_status = simulation.get("adapter_status")
    if adapter_status == "executed":
        return "completed_with_external_simulation"
    if adapter_status:
        return f"completed_with_{adapter_status}_simulation_adapter"
    return "completed_with_mock_simulation"


@mcp.tool()
def export_3d_preview(gds_path: str, output_name: str | None = None) -> dict[str, Any]:
    """Export a local 2.5D HTML/JSON process-stack preview from GDS layer boxes."""
    layout_path = _existing_path(gds_path)
    stem = _artifact_stem(output_name) if output_name else layout_path.stem
    html_path = _artifact_path(f"{stem}.stack3d.html", ".html")
    json_path = _artifact_path(f"{stem}.stack3d.json", ".json")
    return write_stack_preview(layout_path, html_path, json_path)


@mcp.tool()
def export_cad_artifacts(gds_path: str, output_name: str | None = None) -> dict[str, Any]:
    """Export SVG/DXF/STL/GLB CAD-style inspection artifacts from a GDS layout."""
    layout_path = _existing_path(gds_path)
    stem = _artifact_stem(output_name) if output_name else layout_path.stem
    return write_cad_artifacts(
        layout_path,
        svg_path=_artifact_path(f"{stem}.layout.svg", ".svg"),
        dxf_path=_artifact_path(f"{stem}.layout.dxf", ".dxf"),
        stl_path=_artifact_path(f"{stem}.stack.stl", ".stl"),
        glb_path=_artifact_path(f"{stem}.stack.glb", ".glb"),
        json_path=_artifact_path(f"{stem}.cad.json", ".json"),
    )


@mcp.tool()
def export_scientific_plot(
    simulation_path: str,
    output_name: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Export publication-style PNG/SVG/CSV/JSON plot artifacts from simulation JSON."""
    result_path = _existing_path(simulation_path)
    simulation = json.loads(result_path.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{result_path.stem}.scientific"
    png_path = _artifact_path(f"{stem}.png", ".png")
    return write_scientific_plot(
        simulation,
        png_path,
        title=title,
        source_result_path=str(result_path),
    )


@mcp.tool()
def export_rf_network(
    simulation_path: str,
    output_name: str | None = None,
    reference_ohm: float = 50.0,
) -> dict[str, Any]:
    """Export simulation data as Touchstone S2P, RF plot, CSV, and JSON report."""
    result_path = _existing_path(simulation_path)
    simulation = json.loads(result_path.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{_artifact_stem(result_path.name)}.rf"
    return write_rf_network_artifacts(
        simulation,
        touchstone_path=_artifact_path(f"{stem}.s2p", ".s2p"),
        report_path=_artifact_path(f"{stem}.rf.json", ".json"),
        plot_path=_artifact_path(f"{stem}.rf.png", ".png"),
        csv_path=_artifact_path(f"{stem}.rf.csv", ".csv"),
        reference_ohm=reference_ohm,
    )


@mcp.tool()
def export_mesh(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    mesh_size_um: float | None = None,
) -> dict[str, Any]:
    """Mesh the GDS-on-process-stack geometry with gmsh into a 3D .msh for Palace/Elmer."""
    layout_path = _existing_path(gds_path)
    inferred = layout_path.with_suffix(".sidecar.json")
    sidecar_file = (
        _existing_path(sidecar_path)
        if sidecar_path
        else (inferred if inferred.exists() else None)
    )
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else layout_path.stem
    return write_stack_mesh(
        layout_path,
        mesh_path=_artifact_path(f"{stem}.msh", ".msh"),
        report_path=_artifact_path(f"{stem}.mesh.json", ".json"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        mesh_size_um=mesh_size_um,
    )


def _resolve_layout_and_sidecar(
    gds_path: str, sidecar_path: str | None
) -> tuple[Path, Path | None, Path | None]:
    layout_path = _existing_path(gds_path)
    inferred = layout_path.with_suffix(".sidecar.json")
    sidecar_file = (
        _existing_path(sidecar_path)
        if sidecar_path
        else (inferred if inferred.exists() else None)
    )
    return layout_path, sidecar_file, None


@mcp.tool()
def export_palace_project(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    problem_type: str = "Eigenmode",
    target_frequency_ghz: float = 6.0,
    num_modes: int = 4,
    run: bool = False,
) -> dict[str, Any]:
    """Generate a Palace eigenmode/driven project (config + gmsh mesh); the HFSS-eigenmode analog."""
    layout_path, sidecar_file, _ = _resolve_layout_and_sidecar(gds_path, sidecar_path)
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.palace"
    return write_palace_project(
        layout_path,
        config_path=_artifact_path(f"{stem}.config.json", ".json"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        mesh_path=_artifact_path(f"{stem}.msh", ".msh"),
        mesh_report_path=_artifact_path(f"{stem}.mesh.json", ".json"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        problem_type=problem_type,
        target_frequency_ghz=target_frequency_ghz,
        num_modes=num_modes,
        run=run,
    )


@mcp.tool()
def export_elmer_project(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    run: bool = False,
) -> dict[str, Any]:
    """Generate an Elmer electrostatic capacitance project (mesh + .sif); the Q3D analog."""
    layout_path, sidecar_file, _ = _resolve_layout_and_sidecar(gds_path, sidecar_path)
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.elmer"
    return write_elmer_project(
        layout_path,
        sif_path=_artifact_path(f"{stem}.sif", ".sif"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        mesh_path=_artifact_path(f"{stem}.msh", ".msh"),
        mesh_report_path=_artifact_path(f"{stem}.mesh.json", ".json"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        run=run,
    )


@mcp.tool()
def export_fasthenry(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Generate (and run when installed) a FastHenry conductor-inductance extraction deck."""
    layout_path, sidecar_file, _ = _resolve_layout_and_sidecar(gds_path, sidecar_path)
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.fasthenry"
    return run_fasthenry_extraction(
        layout_path,
        inp_path=_artifact_path(f"{stem}.inp", ".inp"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        run=run,
    )


@mcp.tool()
def export_fastcap(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Generate (and run when installed) a FastCap capacitance-matrix extraction deck."""
    layout_path, sidecar_file, _ = _resolve_layout_and_sidecar(gds_path, sidecar_path)
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.fastcap"
    return run_fastcap_extraction(
        layout_path,
        lst_path=_artifact_path(f"{stem}.lst", ".lst"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        run=run,
    )


@mcp.tool()
def list_em_solvers() -> dict[str, Any]:
    """List EM backends (openEMS, HFSS, Sonnet, Palace, Elmer) with method, license, availability."""
    return {"schema": "text-to-gds.em-solvers.v1", "solvers": list_em_solver_metadata()}


@mcp.tool()
def recommend_em_solver(
    sidecar_path: str | None = None,
    device_type: str | None = None,
) -> dict[str, Any]:
    """Route a device to the best EM backend, open-first (commercial = validation-only)."""
    if sidecar_path:
        sidecar = json.loads(_existing_path(sidecar_path).read_text(encoding="utf-8"))
    elif device_type:
        sidecar = {"info": {"device_type": device_type}}
    else:
        raise ValueError("Provide sidecar_path or device_type")
    return recommend_em_solver_for_sidecar(sidecar)


@mcp.tool()
def route_open_solver(
    device: str,
    target_accuracy: str = "iteration",
    validation: bool = False,
) -> dict[str, Any]:
    """Plan the open-source solver backends for a device (CPW/JPA/qubit/...).

    target_accuracy 'publication' requires >=2 open backends to agree; 'iteration'
    requires 1. Commercial solvers are listed only when validation=True.
    """
    return route_open_solver_plan(device, target_accuracy=target_accuracy, validation=validation)


@mcp.tool()
def cross_validate_solvers(
    sources: list[dict[str, Any]],
    quantity: str = "value",
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-check one quantity across >=2 solver/theory sources and score confidence.

    `sources` is a list of {"source": str, "value": float}. Returns reference value,
    max relative error, PASS/FAIL against tolerance, and a confidence percentage.
    A single source can never produce non-zero confidence.
    """
    return cross_validate(sources, quantity=quantity, tolerance_pct=tolerance_pct)


@mcp.tool()
def export_open_eigenmode(
    gds_path: str,
    output_name: str | None = None,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    target_frequency_ghz: float = 6.0,
    run: bool = False,
) -> dict[str, Any]:
    """Open HFSS-eigenmode analog (gmsh -> Palace) in the HFSS schema (f0/Q/participation)."""
    gds = _existing_path(gds_path)
    stem = _artifact_path(output_name or Path(gds_path).stem, ".gds").with_suffix("")
    return run_open_eigenmode(
        gds,
        output_stem=stem,
        sidecar_path=_existing_path(sidecar_path) if sidecar_path else None,
        process_path=process_path,
        target_frequency_ghz=target_frequency_ghz,
        run=run,
    )


@mcp.tool()
def extract_open_q3d(
    gds_path: str,
    output_name: str | None = None,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    run: bool = False,
) -> dict[str, Any]:
    """Open Q3D analog: C matrix (Elmer/FastCap) + L (FastHenry) + coupling."""
    gds = _existing_path(gds_path)
    stem = _artifact_path(output_name or Path(gds_path).stem, ".gds").with_suffix("")
    return OpenQ3D().extract(
        gds,
        output_stem=stem,
        sidecar_path=_existing_path(sidecar_path) if sidecar_path else None,
        process_path=process_path,
        run=run,
    )


@mcp.tool()
def tune_idc_capacitance(
    target_pf: float,
    epsilon_r: float = 11.45,
    min_feature_um: float = 0.2,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Auto-tune interdigital-capacitor finger geometry to hit a target capacitance."""
    return run_idc_tuning(
        target_pf,
        epsilon_r=epsilon_r,
        min_feature_um=min_feature_um,
        tolerance_pct=tolerance_pct,
    )


@mcp.tool()
def export_superconducting_material(
    material: str = "Nb",
    thickness_nm: float = 100.0,
    tc_k: float | None = None,
    lambda_l_nm: float | None = None,
    rn_sheet_ohm: float | None = None,
    trace_width_um: float | None = None,
    trace_length_um: float | None = None,
    geometric_inductance_ph: float | None = None,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Model a superconducting film: sheet kinetic inductance, total Lk, participation.

    Sheet Lk is derived from `lambda_l_nm`+`thickness_nm`, or `rn_sheet_ohm`+`tc_k`
    (Mattis-Bardeen), or a process-material default. Supplying trace geometry adds
    total Lk; supplying `geometric_inductance_ph` adds kinetic participation.
    """
    stem = _artifact_stem(output_name) if output_name else f"{material.lower()}_material"
    return write_superconducting_material(
        report_path=_artifact_path(f"{stem}.superconductor.json", ".json"),
        plot_path=_artifact_path(f"{stem}.superconductor.png", ".png"),
        material=material,
        thickness_nm=thickness_nm,
        tc_k=tc_k,
        lambda_l_nm=lambda_l_nm,
        rn_sheet_ohm=rn_sheet_ohm,
        trace_width_um=trace_width_um,
        trace_length_um=trace_length_um,
        geometric_inductance_ph=geometric_inductance_ph,
    )


@mcp.tool()
def export_package_model(
    operating_frequency_ghz: float = 6.0,
    bondwire_length_um: float = 800.0,
    bondwire_diameter_um: float = 25.0,
    bondwire_count: int = 1,
    bondwire_pitch_um: float | None = None,
    package_width_mm: float = 6.0,
    package_length_mm: float = 6.0,
    package_height_mm: float = 3.0,
    package_epsilon_r: float = 1.0,
    coupling_capacitance_ff: float | None = None,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Estimate chip/wirebond/package parasitics: bondwire L, package modes, warnings."""
    stem = _artifact_stem(output_name) if output_name else "package_model"
    return write_package_model(
        report_path=_artifact_path(f"{stem}.package.json", ".json"),
        plot_path=_artifact_path(f"{stem}.package.png", ".png"),
        operating_frequency_ghz=operating_frequency_ghz,
        bondwire_length_um=bondwire_length_um,
        bondwire_diameter_um=bondwire_diameter_um,
        bondwire_count=bondwire_count,
        bondwire_pitch_um=bondwire_pitch_um,
        package_width_mm=package_width_mm,
        package_length_mm=package_length_mm,
        package_height_mm=package_height_mm,
        package_epsilon_r=package_epsilon_r,
        coupling_capacitance_ff=coupling_capacitance_ff,
    )


@mcp.tool()
def fit_measurement(
    data_path: str,
    fit_kind: str = "auto",
    output_name: str | None = None,
    device_id: str | None = None,
    process_id: str | None = None,
    target_frequency_ghz: float | None = None,
    database_name: str = "experiments.sqlite",
) -> dict[str, Any]:
    """Fit a resonator/JPA-gain/pump/noise trace (CSV or JSON) into device metrics.

    `fit_kind` is one of `auto`, `resonator`, `jpa_gain`, `jpa_pump`, or `noise`.
    Resonator fits report f0/Qi/Qc/Ql; JPA fits report peak gain, 3 dB bandwidth,
    and gain-bandwidth product. When `device_id` is given, the fitted measurement
    is stored in the SQLite experiment database with a next-design correction.
    """
    source = _existing_path(data_path)
    stem = _artifact_stem(output_name) if output_name else f"{source.stem}.fit"
    result = write_measurement_fit(
        source,
        report_path=_artifact_path(f"{stem}.fit.json", ".json"),
        plot_path=_artifact_path(f"{stem}.fit.png", ".png"),
        fit_kind=fit_kind,
    )
    if device_id:
        measurement = measurement_from_fit(result["fit"])
        design: dict[str, Any] = {}
        if target_frequency_ghz is not None:
            design["target_frequency_ghz"] = target_frequency_ghz
        result["experiment"] = record_experiment(
            ARTIFACT_ROOT / Path(database_name).name,
            device_id=device_id,
            process_id=process_id,
            design=design,
            measurement=measurement,
        )
    return result


@mcp.tool()
def export_openems_project(
    sidecar_path: str,
    output_name: str | None = None,
    target_frequency_ghz: float | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Generate and (when openEMS is installed and run=True) execute a real CPW EM extraction."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.openems"
    return write_openems_project(
        sidecar,
        script_path=_artifact_path(f"{stem}.openems.py", ".py"),
        report_path=_artifact_path(f"{stem}.openems.json", ".json"),
        result_path=_artifact_path(f"{stem}.openems.result.json", ".json"),
        plot_path=_artifact_path(f"{stem}.openems.png", ".png"),
        target_frequency_ghz=target_frequency_ghz,
        run=run,
    )


@mcp.tool()
def export_hfss_project(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    setup_frequency_ghz: float = 6.0,
) -> dict[str, Any]:
    """Write a process-mapped PyAEDT HFSS driven/eigenmode project script."""
    layout_path = _existing_path(gds_path)
    sidecar_file = _existing_path(sidecar_path) if sidecar_path else None
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.hfss"
    return write_hfss_project_bridge(
        layout_path,
        script_path=_artifact_path(f"{stem}.hfss_build.py", ".py"),
        report_path=_artifact_path(f"{stem}.hfss.json", ".json"),
        project_path=_artifact_path(f"{stem}.aedt", ".aedt"),
        setup_frequency_ghz=setup_frequency_ghz,
        sidecar_path=sidecar_file,
        process_path=process_file,
    )


@mcp.tool()
def export_pyaedt_project(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    setup_frequency_ghz: float = 6.0,
    sweep_start_ghz: float = 1.0,
    sweep_stop_ghz: float = 12.0,
    sweep_points: int = 221,
    run: bool = False,
    solve: bool = False,
) -> dict[str, Any]:
    """Build HFSS driven/eigenmode and Q3D PyAEDT scripts, optionally running AEDT."""
    layout_path = _existing_path(gds_path)
    inferred_sidecar = layout_path.with_suffix(".sidecar.json")
    sidecar_file = (
        _existing_path(sidecar_path)
        if sidecar_path
        else (inferred_sidecar if inferred_sidecar.exists() else None)
    )
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.pyaedt"
    return write_pyaedt_project_bundle(
        layout_path,
        config_path=_artifact_path(f"{stem}.config.json", ".json"),
        hfss_script_path=_artifact_path(f"{stem}.hfss.py", ".py"),
        q3d_script_path=_artifact_path(f"{stem}.q3d.py", ".py"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        hfss_project_path=_artifact_path(f"{stem}.aedt", ".aedt"),
        q3d_project_path=_artifact_path(f"{stem}.q3d.aedt", ".aedt"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        setup_frequency_ghz=setup_frequency_ghz,
        sweep_start_ghz=sweep_start_ghz,
        sweep_stop_ghz=sweep_stop_ghz,
        sweep_points=sweep_points,
        run=run,
        solve=solve,
    )


@mcp.tool()
def export_q3d_extract(
    gds_path: str,
    sidecar_path: str | None = None,
    process_path: str | None = None,
    output_name: str | None = None,
    setup_frequency_ghz: float = 6.0,
    run: bool = False,
    solve: bool = False,
) -> dict[str, Any]:
    """Generate or run Q3D capacitance-matrix extraction from GDS and process data."""
    layout_path = _existing_path(gds_path)
    inferred_sidecar = layout_path.with_suffix(".sidecar.json")
    sidecar_file = (
        _existing_path(sidecar_path)
        if sidecar_path
        else (inferred_sidecar if inferred_sidecar.exists() else None)
    )
    process_file = _existing_path(process_path) if process_path else None
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.q3d"
    result = write_pyaedt_project_bundle(
        layout_path,
        config_path=_artifact_path(f"{stem}.config.json", ".json"),
        hfss_script_path=_artifact_path(f"{stem}.hfss.py", ".py"),
        q3d_script_path=_artifact_path(f"{stem}.q3d.py", ".py"),
        report_path=_artifact_path(f"{stem}.json", ".json"),
        hfss_project_path=_artifact_path(f"{stem}.hfss.aedt", ".aedt"),
        q3d_project_path=_artifact_path(f"{stem}.aedt", ".aedt"),
        sidecar_path=sidecar_file,
        process_path=process_file,
        setup_frequency_ghz=setup_frequency_ghz,
        run=run,
        solve=solve,
        run_hfss=False,
        run_q3d=True,
    )
    result["requested_analysis"] = "Q3D capacitance extraction"
    return result


@mcp.tool()
def recommend_pyaedt_design_correction(
    target_frequency_ghz: float,
    extracted_frequency_ghz: float,
    extracted_impedance_ohm: float | None = None,
    target_impedance_ohm: float = 50.0,
) -> dict[str, Any]:
    """Convert HFSS/Q3D errors into first-order geometry seeds for Optuna."""
    return em_geometry_correction(
        target_frequency_ghz=target_frequency_ghz,
        extracted_frequency_ghz=extracted_frequency_ghz,
        extracted_impedance_ohm=extracted_impedance_ohm,
        target_impedance_ohm=target_impedance_ohm,
    )


@mcp.tool()
def run_pyaedt_design_iteration(
    sidecar_path: str,
    target_frequency_ghz: float,
    extracted_frequency_ghz: float,
    extracted_impedance_ohm: float | None = None,
    target_impedance_ohm: float = 50.0,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Apply one HFSS-derived correction to supported CPW/LJPA geometry and write new GDS."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    pcell = str(sidecar.get("pcell") or "")
    info = sidecar.get("info") or {}
    correction = em_geometry_correction(
        target_frequency_ghz=target_frequency_ghz,
        extracted_frequency_ghz=extracted_frequency_ghz,
        extracted_impedance_ohm=extracted_impedance_ohm,
        target_impedance_ohm=target_impedance_ohm,
    )
    length_scale = float(correction["recommended_cpw_length_scale"])
    gap_scale = float(correction.get("recommended_cpw_gap_scale_seed", 1.0))
    if pcell == "lumped_element_jpa_seed":
        parameters = {
            "center_frequency_ghz": target_frequency_ghz,
            "target_bandwidth_mhz": float(info.get("target_bandwidth_mhz", 500.0)),
            "target_gain_db": float(info.get("target_gain_db", 20.0)),
            "active_width_um": float(info.get("active_width_um", 260.0)),
            "active_height_um": float(info.get("active_height_um", 180.0)),
            "junction_width": float(info.get("junction_width_um", 0.22)),
            "junction_height": float(info.get("junction_height_um", 0.22)),
            "cpw_length": float(info.get("cpw_length_um", 210.0)) * length_scale,
            "cpw_trace_width": float(info.get("cpw_trace_width_um", 10.0)),
            "cpw_gap": float(info.get("cpw_gap_um", 6.0)) * gap_scale,
            "flux_line_length": float(info.get("flux_line_length_um", 120.0)),
            "flux_line_width": float(info.get("flux_line_width_um", 1.5)),
            "inductor_turns": int(info.get("inductor_turns", 6)),
            "inductor_segment_length": float(info.get("inductor_segment_length_um", 24.0)),
            "inductor_trace_width": float(info.get("inductor_trace_width_um", 1.0)),
            "inductor_pitch": float(info.get("inductor_pitch_um", 3.0)),
        }
    elif pcell == "cpw_straight":
        parameters = {
            "length": float(info.get("length_um", 100.0)) * length_scale,
            "trace_width": float(info.get("trace_width_um", 10.0)),
            "gap": float(info.get("gap_um", 6.0)) * gap_scale,
            "ground_width": float(info.get("ground_width_um", 25.0)),
            "angle_deg": float(info.get("angle_deg", 0.0)),
        }
    else:
        raise ValueError(
            "EM-backed regeneration currently supports lumped_element_jpa_seed and cpw_straight; "
            f"got {pcell!r}"
        )
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.em-iteration.gds"
    compiled = compile_layout(pcell=pcell, parameters=parameters, output_name=stem)
    drc = run_drc(compiled["gds_path"])
    return {
        "schema": "text-to-gds.pyaedt-design-iteration.v1",
        "status": "regenerated",
        "source_sidecar": str(sidecar_file),
        "correction": correction,
        "updated_parameters": parameters,
        "layout": compiled,
        "drc": drc,
        "next_action": "Run export_pyaedt_project on the regenerated GDS and repeat until converged.",
    }


@mcp.tool()
def run_pyaedt_benchmarks(
    results_root: str | None = None,
    output_name: str = "pyaedt-benchmark-suite",
) -> dict[str, Any]:
    """Compare licensed HFSS/Q3D result JSON against solver qualification targets."""
    solver_results = _existing_path(results_root) if results_root else None
    stem = _artifact_stem(output_name)
    return run_pyaedt_benchmark_suite(
        PROJECT_ROOT / "benchmarks" / "pyaedt",
        report_path=_artifact_path(f"{stem}.json", ".json"),
        results_root=solver_results,
    )


@mcp.tool()
def export_sonnet_project(
    gds_path: str,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Write a SonnetLab script and expected Sonnet project path from GDS."""
    layout_path = _existing_path(gds_path)
    stem = _artifact_stem(output_name) if output_name else f"{layout_path.stem}.sonnet"
    return write_sonnet_project_bridge(
        layout_path,
        script_path=_artifact_path(f"{stem}.sonnet.m", ".m"),
        report_path=_artifact_path(f"{stem}.sonnet.json", ".json"),
        output_project_path=_artifact_path(f"{stem}.son", ".son"),
    )


@mcp.tool()
def export_measurement_plan(
    sidecar_path: str,
    simulation_path: str | None = None,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Write a QCoDeS-style measurement plan and script without touching instruments."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    simulation = None
    if simulation_path is not None:
        simulation_file = _existing_path(simulation_path)
        simulation = json.loads(simulation_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.measurement"
    return write_measurement_plan(
        sidecar,
        plan_path=_artifact_path(f"{stem}.measurement.json", ".json"),
        script_path=_artifact_path(f"{stem}.qcodes.py", ".py"),
        db_path=_artifact_path(f"{stem}.qcodes.db", ".db"),
        plot_path=_artifact_path(f"{stem}.qcodes.png", ".png"),
        simulation=simulation,
    )


@mcp.tool()
def export_measurement_recipe(
    recipe: str = "gain_map",
    output_name: str | None = None,
) -> dict[str, Any]:
    """Write an executable dry-run/QCoDeS-oriented JPA measurement recipe."""
    if recipe not in RECIPES:
        raise ValueError(f"Unknown recipe {recipe!r}; choose {sorted(RECIPES)}")
    stem = _artifact_stem(output_name) if output_name else recipe
    return write_measurement_recipe(
        recipe,
        script_path=_artifact_path(f"{stem}.measurement.py", ".py"),
        plan_path=_artifact_path(f"{stem}.measurement.json", ".json"),
    )


@mcp.tool()
def export_epr_analysis(
    sidecar_path: str,
    field_energy_path: str | None = None,
    hfss_project_path: str | None = None,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Write pyEPR HFSS analysis and optionally evaluate exported field energies."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    field_file = _existing_path(field_energy_path) if field_energy_path else None
    hfss_file = _existing_path(hfss_project_path) if hfss_project_path else None
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.epr"
    return write_epr_analysis(
        sidecar,
        report_path=_artifact_path(f"{stem}.epr.json", ".json"),
        script_path=_artifact_path(f"{stem}.pyepr.py", ".py"),
        field_energy_path=field_file,
        hfss_project_path=hfss_file,
    )


@mcp.tool()
def export_hamiltonian_model(
    sidecar_path: str,
    output_name: str | None = None,
    jc_ua_per_um2: float = 1.0,
    capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
) -> dict[str, Any]:
    """Write a scqubits-ready Hamiltonian starter model from sidecar JJ/SQUID values."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.hamiltonian"
    return write_hamiltonian_model(
        sidecar,
        json_path=_artifact_path(f"{stem}.hamiltonian.json", ".json"),
        script_path=_artifact_path(f"{stem}.scqubits.py", ".py"),
        plot_path=_artifact_path(f"{stem}.scqubits.png", ".png"),
        jc_ua_per_um2=jc_ua_per_um2,
        capacitance_ff=capacitance_ff,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
    )


@mcp.tool()
def export_quantum_metal_bridge(
    sidecar_path: str,
    output_name: str | None = None,
) -> dict[str, Any]:
    """Write Quantum Metal/Qiskit Metal bridge metadata for component architecture mapping."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.qmetal"
    return write_quantum_metal_bridge(
        sidecar,
        json_path=_artifact_path(f"{stem}.qmetal.json", ".json"),
        script_path=_artifact_path(f"{stem}.qmetal.py", ".py"),
        gds_path=_artifact_path(f"{stem}.qmetal.gds", ".gds"),
    )


@mcp.tool()
def export_scientific_report(
    sidecar_path: str,
    gds_layout_png: str | None = None,
    output_name: str | None = None,
    jc_ua_per_um2: float = 1.0,
    target_frequency_ghz: float | None = None,
    target_bandwidth_mhz: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.05,
) -> dict[str, Any]:
    """Assemble the full ten-figure JPA scientific report (composite PNG/SVG + JSON manifest)."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else sidecar_file.stem
    layout_png = gds_layout_png
    if layout_png is None:
        candidate = ARTIFACT_ROOT / f"{Path(sidecar.get('gds_path', '')).stem}.layout.png"
        layout_png = str(candidate) if candidate.exists() else None
    return write_scientific_report(
        sidecar,
        report_dir=ARTIFACT_ROOT,
        stem=stem,
        gds_layout_png=layout_png,
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=target_frequency_ghz,
        target_bandwidth_mhz=target_bandwidth_mhz,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
    )


@mcp.tool()
def run_analytical_verification(
    output_name: str = "jpa-theory-verification",
    center_frequency_ghz: float = 6.0,
    kappa_mhz: float = 120.0,
    pump_coupling_mhz: float = 55.0,
    simulation_path: str | None = None,
    measurement_path: str | None = None,
) -> dict[str, Any]:
    """Compare analytical Kerr-JPA metrics with optional simulation and measurement JSON."""
    simulation = None
    measurement = None
    if simulation_path:
        simulation = json.loads(_existing_path(simulation_path).read_text(encoding="utf-8"))
    if measurement_path:
        measurement = json.loads(_existing_path(measurement_path).read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name)
    return write_analytical_verification(
        report_path=_artifact_path(f"{stem}.theory.json", ".json"),
        plot_path=_artifact_path(f"{stem}.theory.png", ".png"),
        center_frequency_ghz=center_frequency_ghz,
        kappa_mhz=kappa_mhz,
        pump_coupling_mhz=pump_coupling_mhz,
        simulation=simulation,
        measurement=measurement,
    )


@mcp.tool()
def record_experiment_feedback(
    device_id: str,
    design_path: str,
    measurement_path: str,
    process_id: str | None = None,
    database_name: str = "experiments.sqlite",
) -> dict[str, Any]:
    """Record measured results and return correction factors for the next design."""
    design = json.loads(_existing_path(design_path).read_text(encoding="utf-8"))
    measurement = json.loads(_existing_path(measurement_path).read_text(encoding="utf-8"))
    return record_experiment(
        ARTIFACT_ROOT / Path(database_name).name,
        device_id=device_id,
        process_id=process_id,
        design=design,
        measurement=measurement,
    )


@mcp.tool()
def export_jpa_analysis(
    sidecar_path: str,
    output_name: str | None = None,
    jc_ua_per_um2: float = 1.0,
    target_frequency_ghz: float | None = None,
    target_bandwidth_mhz: float | None = None,
    n_pump_points: int = 16,
) -> dict[str, Any]:
    """Run a real JosephsonCircuits.jl pump sweep for gain/P1dB/noise/squeezing/stability."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.jpa"
    return run_jpa_analysis(
        sidecar,
        script_path=_artifact_path(f"{stem}.jpa.jl", ".jl"),
        result_path=_artifact_path(f"{stem}.jpa.result.json", ".json"),
        report_path=_artifact_path(f"{stem}.jpa.json", ".json"),
        plot_path=_artifact_path(f"{stem}.jpa.png", ".png"),
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=target_frequency_ghz,
        target_bandwidth_mhz=target_bandwidth_mhz,
        n_pump_points=n_pump_points,
    )


@mcp.tool()
def run_traveling_wave_paper_benchmark(
    output_name: str = "traveling-wave-paper-parity",
) -> dict[str, Any]:
    """Reproduce the two bundled papers' linear bands and reduced traveling-wave gain."""
    stem = _artifact_stem(output_name)
    return write_traveling_wave_paper_benchmark(
        report_path=_artifact_path(f"{stem}.json", ".json"),
        csv_path=_artifact_path(f"{stem}.csv", ".csv"),
        plot_path=_artifact_path(f"{stem}.png", ".png"),
    )


@mcp.tool()
def run_gaydamachenko_jtwpa_benchmark(
    output_name: str = "gaydamachenko-3wm-jtwpa",
    pump_frequency_ghz: float = 12.92,
) -> dict[str, Any]:
    """Reproduce the arXiv:2209.11052v2 loaded 3WM-JTWPA reference design."""
    stem = _artifact_stem(output_name)
    return write_gaydamachenko_benchmark(
        report_path=_artifact_path(f"{stem}.json", ".json"),
        csv_path=_artifact_path(f"{stem}.csv", ".csv"),
        plot_path=_artifact_path(f"{stem}.png", ".png"),
        paper_path=PROJECT_ROOT / "paper" / "2209.11052v2.pdf",
        pump_frequency_ghz=pump_frequency_ghz,
    )


@mcp.tool()
def run_paper_benchmarks(
    output_name: str = "paper-benchmark-suite",
) -> dict[str, Any]:
    """Run every supported paper reproduction and explicitly skip missing backends."""
    stem = _artifact_stem(output_name)
    return run_paper_benchmark_suite(
        PROJECT_ROOT / "benchmarks" / "papers",
        report_path=_artifact_path(f"{stem}.json", ".json"),
    )


@mcp.tool()
def run_research_optimization(
    sidecar_path: str,
    output_name: str | None = None,
    n_trials: int = 16,
    target_frequency_ghz: float = 5.0,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float = 500.0,
    min_p1db_dbm: float = -100.0,
    force_fallback: bool = False,
) -> dict[str, Any]:
    """Run Optuna if installed, else deterministic constrained surrogate optimization."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.optuna"
    return run_research_optimization_artifacts(
        sidecar,
        json_path=_artifact_path(f"{stem}.optuna.json", ".json"),
        csv_path=_artifact_path(f"{stem}.optuna.csv", ".csv"),
        plot_path=_artifact_path(f"{stem}.optuna.png", ".png"),
        n_trials=n_trials,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=target_bandwidth_mhz,
        min_p1db_dbm=min_p1db_dbm,
        force_fallback=force_fallback,
    )


def _linspace(start: float, stop: float, points: int) -> list[float]:
    if points < 2:
        raise ValueError(f"points must be >= 2, got {points}")
    if not start < stop:
        raise ValueError(f"start must be less than stop, got {start} >= {stop}")
    step = (stop - start) / float(points - 1)
    return [start + step * index for index in range(points)]


def _optional_existing_path(path_value: str | None) -> Path | None:
    if path_value is None:
        return None
    return _existing_path(path_value)


def _default_related_path(base: Path, suffix: str) -> Path | None:
    candidate = ARTIFACT_ROOT / f"{_artifact_stem(base.name)}{suffix}"
    return candidate if candidate.exists() else None


@mcp.tool()
def run_validation_checklist(
    gds_path: str | None = None,
    sidecar_path: str | None = None,
    drc_path: str | None = None,
    extraction_path: str | None = None,
    simulation_path: str | None = None,
    cad_path: str | None = None,
    em_path: str | None = None,
    measurement_path: str | None = None,
    output_name: str = "validation.json",
) -> dict[str, Any]:
    """Write an academic/industrial validation checklist plus a TRL readiness score."""
    gds = _optional_existing_path(gds_path)
    sidecar = _optional_existing_path(sidecar_path)
    if sidecar is None and gds is not None:
        sidecar = _default_related_path(gds, ".sidecar.json")
    if gds is None and sidecar is not None:
        try:
            sidecar_json = json.loads(sidecar.read_text(encoding="utf-8"))
            gds_value = sidecar_json.get("gds_path")
            gds = _existing_path(str(gds_value)) if gds_value else None
        except (json.JSONDecodeError, FileNotFoundError):
            gds = None

    base = gds or sidecar
    drc = _optional_existing_path(drc_path) if drc_path else (
        _default_related_path(base, ".drc.json") if base is not None else None
    )
    extraction = (
        _optional_existing_path(extraction_path)
        if extraction_path
        else (_default_related_path(base, ".sidecar.extraction.json") if base is not None else None)
    )
    simulation = (
        _optional_existing_path(simulation_path)
        if simulation_path
        else (_default_related_path(base, ".sidecar.simulation.json") if base is not None else None)
    )
    cad = _optional_existing_path(cad_path) if cad_path else (
        _default_related_path(base, ".cad.json") if base is not None else None
    )
    em = _optional_existing_path(em_path) if em_path else None
    measurement = (
        _optional_existing_path(measurement_path)
        if measurement_path
        else (_default_related_path(base, ".fit.json") if base is not None else None)
    )
    report = build_validation_report(
        gds_path=gds,
        sidecar_path=sidecar,
        drc_path=drc,
        extraction_path=extraction,
        simulation_path=simulation,
        cad_path=cad,
        em_path=em,
        measurement_path=measurement,
    )
    report_path = _artifact_path(output_name, ".json")
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _sweep_row(
    sidecar: dict[str, Any],
    *,
    sweep_parameter: str,
    value: float,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    target_frequency_ghz: float | None,
    target_gain_db: float,
    target_bandwidth_mhz: float | None,
    pump_current_fraction: float,
    coupling_capacitance_ff: float | None,
    resonator_capacitance_ff: float | None,
    flux_bias_phi0: float,
    squid_asymmetry: float,
    flux_sweep_span_phi0: float,
    flux_sweep_points: int,
    flux_period_current_ma: float | None,
    flux_mutual_inductance_ph: float | None,
) -> dict[str, Any]:
    swept_sidecar = json.loads(json.dumps(sidecar))
    info = swept_sidecar.setdefault("info", {})
    local_jc = jc_ua_per_um2
    local_shunt = shunt_capacitance_ff
    local_target_frequency = target_frequency_ghz
    local_target_bandwidth = target_bandwidth_mhz
    local_pump = pump_current_fraction
    local_coupling = coupling_capacitance_ff
    local_resonator = resonator_capacitance_ff
    local_flux_bias_phi0 = flux_bias_phi0
    local_squid_asymmetry = squid_asymmetry

    if sweep_parameter == "jc_ua_per_um2":
        local_jc = value
    elif sweep_parameter == "shunt_capacitance_ff":
        local_shunt = value
    elif sweep_parameter == "target_frequency_ghz":
        local_target_frequency = value
    elif sweep_parameter == "target_bandwidth_mhz":
        local_target_bandwidth = value
    elif sweep_parameter == "pump_current_fraction":
        local_pump = value
    elif sweep_parameter == "coupling_capacitance_ff":
        local_coupling = value
    elif sweep_parameter == "resonator_capacitance_ff":
        local_resonator = value
    elif sweep_parameter == "junction_area_um2":
        info["junction_area_um2"] = value
    elif sweep_parameter == "flux_bias_phi0":
        local_flux_bias_phi0 = value
    elif sweep_parameter == "squid_asymmetry":
        local_squid_asymmetry = value
    else:
        raise ValueError(
            "Unsupported sweep_parameter. Use one of: jc_ua_per_um2, "
            "junction_area_um2, shunt_capacitance_ff, target_frequency_ghz, "
            "target_bandwidth_mhz, pump_current_fraction, coupling_capacitance_ff, "
            "resonator_capacitance_ff, flux_bias_phi0, squid_asymmetry."
        )

    ideal = simulate_ideal_junction(
        swept_sidecar,
        jc_ua_per_um2=local_jc,
        shunt_capacitance_ff=local_shunt,
        flux_bias_phi0=local_flux_bias_phi0,
        squid_asymmetry=local_squid_asymmetry,
    )
    physical = estimate_physical_performance(
        swept_sidecar,
        jc_ua_per_um2=local_jc,
        shunt_capacitance_ff=local_shunt,
        target_frequency_ghz=local_target_frequency,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=local_target_bandwidth,
        pump_current_fraction=local_pump,
        coupling_capacitance_ff=local_coupling,
        resonator_capacitance_ff=local_resonator,
        flux_bias_phi0=local_flux_bias_phi0,
        squid_asymmetry=local_squid_asymmetry,
        flux_sweep_span_phi0=flux_sweep_span_phi0,
        flux_sweep_points=flux_sweep_points,
        flux_period_current_ma=flux_period_current_ma,
        flux_mutual_inductance_ph=flux_mutual_inductance_ph,
    )
    flux_tuning = physical.get("flux_tuning") if isinstance(physical, dict) else None
    flux_operating_point = (
        flux_tuning.get("operating_point")
        if isinstance(flux_tuning, dict) and isinstance(flux_tuning.get("operating_point"), dict)
        else {}
    )
    return {
        sweep_parameter: value,
        "junction_area_um2": ideal.get("junction_area_um2"),
        "jc_ua_per_um2": local_jc,
        "critical_current_ua": ideal.get("critical_current_ua"),
        "zero_flux_critical_current_ua": ideal.get("zero_flux_critical_current_ua"),
        "josephson_inductance_ph": ideal.get("josephson_inductance_ph"),
        "shunt_capacitance_ff": local_shunt,
        "flux_bias_phi0": local_flux_bias_phi0,
        "squid_asymmetry": local_squid_asymmetry,
        "flux_tuned_resonant_frequency_ghz": flux_operating_point.get(
            "resonant_frequency_ghz"
        ),
        "analysis_type": physical.get("analysis_type"),
        "center_frequency_ghz": physical.get("center_frequency_ghz"),
        "estimated_peak_gain_db": physical.get("estimated_peak_gain_db"),
        "bandwidth_3db_mhz": physical.get("bandwidth_3db_mhz"),
        "loaded_q": physical.get("loaded_q"),
        "estimated_saturation_power_dbm": physical.get("estimated_saturation_power_dbm"),
        "estimated_input_1db_compression_dbm": physical.get("estimated_input_1db_compression_dbm"),
        "pump_current_ua": physical.get("pump_current_ua"),
        "coupling_capacitance_ff": physical.get("coupling_capacitance_ff"),
        "resonator_capacitance_ff": physical.get("resonator_capacitance_ff"),
    }


@mcp.tool()
def run_parameter_sweep(
    sidecar_path: str,
    sweep_parameter: str = "jc_ua_per_um2",
    start: float = 0.5,
    stop: float = 5.0,
    points: int = 9,
    output_name: str | None = None,
    jc_ua_per_um2: float = 1.0,
    shunt_capacitance_ff: float = 0.0,
    target_frequency_ghz: float | None = None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Run a local layout-derived parameter sweep and write JSON/CSV/PNG/SVG artifacts."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    values = _linspace(start, stop, points)
    rows = [
        _sweep_row(
            sidecar,
            sweep_parameter=sweep_parameter,
            value=value,
            jc_ua_per_um2=jc_ua_per_um2,
            shunt_capacitance_ff=shunt_capacitance_ff,
            target_frequency_ghz=target_frequency_ghz,
            target_gain_db=target_gain_db,
            target_bandwidth_mhz=target_bandwidth_mhz,
            pump_current_fraction=pump_current_fraction,
            coupling_capacitance_ff=coupling_capacitance_ff,
            resonator_capacitance_ff=resonator_capacitance_ff,
            flux_bias_phi0=flux_bias_phi0,
            squid_asymmetry=squid_asymmetry,
            flux_sweep_span_phi0=flux_sweep_span_phi0,
            flux_sweep_points=flux_sweep_points,
            flux_period_current_ma=flux_period_current_ma,
            flux_mutual_inductance_ph=flux_mutual_inductance_ph,
        )
        for value in values
    ]
    stem = _artifact_stem(output_name) if output_name else f"{sidecar_file.stem}.{sweep_parameter}.sweep"
    json_path = _artifact_path(f"{stem}.json", ".json")
    plot = write_sweep_artifacts(
        {
            "sweep_parameter": sweep_parameter,
            "rows": rows,
        },
        _artifact_path(f"{stem}.png", ".png"),
    )
    result = {
        "schema": "text-to-gds.parameter-sweep.v0",
        "input_sidecar": str(sidecar_file),
        "sweep_parameter": sweep_parameter,
        "start": start,
        "stop": stop,
        "points": points,
        "rows": rows,
        "result_path": str(json_path),
        "plot": plot,
    }
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


@mcp.tool()
def run_design_workflow(
    prompt: str,
    output_name: str = "ljpa_seed.gds",
    parameters: dict[str, Any] | None = None,
    jc_ua_per_um2: float = 2.0,
    simulator: str = "mock_jj",
    analysis_mode: str = "auto",
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Run a local prompt-to-layout workflow and write a browser workbench."""
    plan = plan_ljpa(prompt)
    target = plan["target"]
    pcell_parameters = {
        "center_frequency_ghz": target.get("center_frequency_ghz") or 5.0,
        "target_bandwidth_mhz": target.get("bandwidth_mhz") or 500.0,
        "target_gain_db": target.get("gain_db") or 20.0,
    }
    effective_jc = jc_ua_per_um2
    process_plan = plan.get("fabrication_process")
    provided_parameters = parameters or {}
    if process_plan:
        effective_jc = float(process_plan["process"]["measured_Jc_ua_per_um2"])
        if not {"junction_width", "junction_height"}.intersection(provided_parameters):
            corrected_area = process_plan["design_correction"]["corrected_junction_area_um2"]
            junction_side = float(corrected_area) ** 0.5
            pcell_parameters.update(
                {"junction_width": junction_side, "junction_height": junction_side}
            )
    pcell_parameters.update(provided_parameters)

    compiled = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters=pcell_parameters,
        output_name=output_name,
    )
    drc = run_drc(compiled["gds_path"])
    process_drc = run_process_drc(compiled["gds_path"], output_name=f"{Path(output_name).stem}.process")
    extraction = extract_layout(compiled["sidecar_path"])
    magic = run_magic_extract(compiled["gds_path"], output_name=f"{Path(output_name).stem}.magic")
    preview = export_3d_preview(compiled["gds_path"])
    cad = export_cad_artifacts(compiled["gds_path"])
    simulation = run_simulation(
        compiled["sidecar_path"],
        simulator=simulator,
        jc_ua_per_um2=effective_jc,
        analysis_mode=analysis_mode,
        pump_current_fraction=pump_current_fraction,
        coupling_capacitance_ff=coupling_capacitance_ff,
        resonator_capacitance_ff=resonator_capacitance_ff,
        target_frequency_ghz=target.get("center_frequency_ghz"),
        target_gain_db=target.get("gain_db") or 20.0,
        target_bandwidth_mhz=target.get("bandwidth_mhz"),
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
        flux_sweep_span_phi0=flux_sweep_span_phi0,
        flux_sweep_points=flux_sweep_points,
        flux_period_current_ma=flux_period_current_ma,
        flux_mutual_inductance_ph=flux_mutual_inductance_ph,
    )
    rf = export_rf_network(
        simulation["result_path"],
        output_name=Path(output_name).stem,
    )
    validation = run_validation_checklist(
        gds_path=compiled["gds_path"],
        sidecar_path=compiled["sidecar_path"],
        drc_path=drc["report_path"],
        extraction_path=extraction["result_path"],
        simulation_path=simulation["result_path"],
        cad_path=cad["report_path"],
        output_name=f"{Path(output_name).stem}.validation.json",
    )

    workbench_path = _artifact_path(f"{Path(output_name).stem}.workbench.html", ".html")
    workbench = write_design_workbench(
        prompt=prompt,
        plan=plan,
        compiled=compiled,
        drc=drc,
        process_drc=process_drc,
        extraction=extraction,
        preview=preview,
        simulation=simulation,
        html_path=workbench_path,
        magic=magic,
        cad=cad,
        validation=validation,
        rf=rf,
    )

    return {
        "schema": "text-to-gds.design-workflow.v0",
        "status": _workflow_status_from_simulation(simulation),
        "prompt": prompt,
        "plan": plan,
        "pcell": "lumped_element_jpa_seed",
        "parameters": pcell_parameters,
        "compile": compiled,
        "drc": drc,
        "process_drc": process_drc,
        "extraction": extraction,
        "magic": magic,
        "preview": preview,
        "cad": cad,
        "simulation": simulation,
        "rf": rf,
        "validation": validation,
        "workbench": workbench,
    }


@mcp.tool()
def run_optimized_design_workflow(
    prompt: str,
    output_name: str = "ljpa_optimized.gds",
    parameters: dict[str, Any] | None = None,
    jc_ua_per_um2: float = 2.0,
    max_iterations: int = 4,
    simulator: str = "mock_jj",
    analysis_mode: str = "auto",
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Optimize first-pass LJPA geometry with a local surrogate, then run workflow."""
    plan = plan_ljpa(prompt)
    target = plan["target"]
    initial_parameters = {
        key: float(value) for key, value in (parameters or {}).items()
    }
    process_plan = plan.get("fabrication_process")
    if process_plan and not {"junction_width", "junction_height"}.intersection(
        initial_parameters
    ):
        corrected_area = process_plan["design_correction"]["corrected_junction_area_um2"]
        junction_side = float(corrected_area) ** 0.5
        initial_parameters.update(
            {"junction_width": junction_side, "junction_height": junction_side}
        )
    optimization = optimize_ljpa_parameters(
        target_frequency_ghz=float(target.get("center_frequency_ghz") or 5.0),
        target_bandwidth_mhz=float(target.get("bandwidth_mhz") or 500.0),
        target_gain_db=float(target.get("gain_db") or 20.0),
        initial_parameters=initial_parameters,
        max_iterations=max_iterations,
    )
    final_parameters = {
        "cpw_length": optimization["final_parameters"]["cpw_length"],
        "cpw_trace_width": optimization["final_parameters"]["cpw_trace_width"],
        "cpw_gap": optimization["final_parameters"]["cpw_gap"],
        "junction_width": optimization["final_parameters"]["junction_width"],
        "junction_height": optimization["final_parameters"]["junction_height"],
        "flux_line_length": optimization["final_parameters"]["flux_line_length"],
        "flux_line_width": optimization["final_parameters"]["flux_line_width"],
        "inductor_segment_length": optimization["final_parameters"]["inductor_segment_length"],
        "inductor_trace_width": optimization["final_parameters"]["inductor_trace_width"],
        "inductor_pitch": optimization["final_parameters"]["inductor_pitch"],
    }
    workflow = run_design_workflow(
        prompt=prompt,
        output_name=output_name,
        parameters=final_parameters,
        jc_ua_per_um2=jc_ua_per_um2,
        simulator=simulator,
        analysis_mode=analysis_mode,
        pump_current_fraction=pump_current_fraction,
        coupling_capacitance_ff=coupling_capacitance_ff,
        resonator_capacitance_ff=resonator_capacitance_ff,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
        flux_sweep_span_phi0=flux_sweep_span_phi0,
        flux_sweep_points=flux_sweep_points,
        flux_period_current_ma=flux_period_current_ma,
        flux_mutual_inductance_ph=flux_mutual_inductance_ph,
    )
    workflow["optimization"] = optimization
    workflow["status"] = "optimized_with_local_surrogate"
    workflow["simulation_status"] = _workflow_status_from_simulation(workflow["simulation"])
    return workflow


@mcp.tool()
def run_simulation(
    sidecar_path: str,
    simulator: str = "mock_jj",
    jc_ua_per_um2: float = 1.0,
    shunt_capacitance_ff: float = 0.0,
    analysis_mode: str = "auto",
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    adapter_executable: str | None = None,
    target_frequency_ghz: float | None = None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Run ideal JJ simulation and optional local external simulator adapters."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))

    normalized_simulator = simulator.lower().replace(" ", "").replace("-", "").replace("_", "")
    result = {
        "schema": "text-to-gds.simulation.v0",
        "engine": simulator,
        "input_sidecar": str(sidecar_file),
        **simulate_ideal_junction(
            sidecar,
            jc_ua_per_um2=jc_ua_per_um2,
            shunt_capacitance_ff=shunt_capacitance_ff,
            flux_bias_phi0=flux_bias_phi0,
            squid_asymmetry=squid_asymmetry,
        ),
    }
    result["physical_performance"] = estimate_physical_performance(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        shunt_capacitance_ff=shunt_capacitance_ff,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_db,
        target_bandwidth_mhz=target_bandwidth_mhz,
        pump_current_fraction=pump_current_fraction,
        coupling_capacitance_ff=coupling_capacitance_ff,
        resonator_capacitance_ff=resonator_capacitance_ff,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
        flux_sweep_span_phi0=flux_sweep_span_phi0,
        flux_sweep_points=flux_sweep_points,
        flux_period_current_ma=flux_period_current_ma,
        flux_mutual_inductance_ph=flux_mutual_inductance_ph,
    )
    if normalized_simulator in {"josim", "externalcli"}:
        deck = josim_netlist_from_sidecar(
            sidecar,
            jc_ua_per_um2=jc_ua_per_um2,
            shunt_capacitance_ff=shunt_capacitance_ff,
        )
        deck_path = _artifact_path(f"{sidecar_file.stem}.josim.cir", ".cir")
        deck_path.write_text(deck, encoding="utf-8")
        josim_output_path = _artifact_path(f"{sidecar_file.stem}.josim.json", ".json")
        adapter_result = run_josim_transient(
            deck_path=deck_path,
            output_path=josim_output_path,
            josim_executable=adapter_executable or "josim",
        )
        result["adapter"] = "JoSIM"
        result["adapter_status"] = adapter_result["status"]
        result["adapter_deck_path"] = str(deck_path)
        result["adapter_result"] = adapter_result
        result["available_adapters"] = list_simulation_adapters()
    elif normalized_simulator in {"ngspice", "externalspicecli"}:
        data_path = _artifact_path(f"{sidecar_file.stem}.ngspice.dat", ".dat")
        deck = ngspice_netlist_from_sidecar(
            sidecar,
            output_data_path=data_path.name,
            jc_ua_per_um2=jc_ua_per_um2,
            shunt_capacitance_ff=shunt_capacitance_ff,
            target_frequency_ghz=target_frequency_ghz,
            target_bandwidth_mhz=target_bandwidth_mhz,
            coupling_capacitance_ff=coupling_capacitance_ff,
            resonator_capacitance_ff=resonator_capacitance_ff,
        )
        deck_path = _artifact_path(f"{sidecar_file.stem}.ngspice.cir", ".cir")
        deck_path.write_text(deck, encoding="utf-8")
        ngspice_output_path = _artifact_path(f"{sidecar_file.stem}.ngspice.json", ".json")
        adapter_result = run_ngspice(
            deck_path=deck_path,
            output_path=ngspice_output_path,
            data_path=data_path,
            ngspice_executable=adapter_executable or "ngspice",
        )
        result["adapter"] = "ngspice"
        result["adapter_status"] = adapter_result["status"]
        result["adapter_deck_path"] = str(deck_path)
        result["adapter_result"] = adapter_result
        result["available_adapters"] = list_simulation_adapters()
    elif normalized_simulator in {"josephsoncircuits.jl", "josephsoncircuits", "externaljulia"}:
        script_path = _artifact_path(f"{sidecar_file.stem}.josephsoncircuits.jl", ".jl")
        jc_result_path = _artifact_path(f"{sidecar_file.stem}.josephsoncircuits.json", ".json")
        write_josephsoncircuits_script(
            sidecar,
            script_path=script_path,
            result_path=jc_result_path,
            jc_ua_per_um2=jc_ua_per_um2,
            shunt_capacitance_ff=shunt_capacitance_ff,
            analysis_mode=analysis_mode,
            pump_current_fraction=pump_current_fraction,
            coupling_capacitance_ff=coupling_capacitance_ff,
            resonator_capacitance_ff=resonator_capacitance_ff,
            target_frequency_ghz=target_frequency_ghz,
            target_gain_db=target_gain_db,
            target_bandwidth_mhz=target_bandwidth_mhz,
        )
        adapter_result = run_josephsoncircuits(
            script_path=script_path,
            result_path=jc_result_path,
            julia_executable=adapter_executable or "julia",
        )
        result["adapter"] = "JosephsonCircuits.jl"
        result["adapter_status"] = adapter_result["status"]
        result["adapter_script_path"] = str(script_path)
        result["adapter_plan"] = josephsoncircuits_plan_from_sidecar(
            sidecar,
            jc_ua_per_um2=jc_ua_per_um2,
            analysis_mode=analysis_mode,
            pump_current_fraction=pump_current_fraction,
            coupling_capacitance_ff=coupling_capacitance_ff,
            resonator_capacitance_ff=resonator_capacitance_ff,
            target_frequency_ghz=target_frequency_ghz,
            target_gain_db=target_gain_db,
            target_bandwidth_mhz=target_bandwidth_mhz,
        )
        result["adapter_result"] = adapter_result

    output_path = _artifact_path(f"{sidecar_file.stem}.simulation.json", ".json")
    result["result_path"] = str(output_path)
    plot_path = _artifact_path(f"{sidecar_file.stem}.simulation.png", ".png")
    plot = write_simulation_plot(result, plot_path)
    result["plot"] = plot
    result["plot_path"] = plot["plot_path"]
    scientific = write_scientific_plot(
        result,
        _artifact_path(f"{sidecar_file.stem}.scientific.png", ".png"),
        source_result_path=str(output_path),
    )
    result["scientific_plot"] = scientific
    result["scientific_plot_path"] = scientific["png_path"]
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Quantum Device Database, Physics Constraints, and Layout Foundation Model
# ---------------------------------------------------------------------------


@mcp.tool()
def record_quantum_device(
    device_id: str,
    gds_path: str = "",
    status: str = "draft",
    device_type: str = "",
    process_id: str = "",
    jc_ua_per_um2: float = 0.0,
    paper_doi: str = "",
    tags: list[str] | None = None,
    geometry_json: str = "{}",
    sidecar_json: str = "{}",
) -> dict[str, Any]:
    """Record a quantum device in the device database.

    Stores layout hash, geometry, fabrication data, and provenance for
    long-term design memory and ML training.
    """
    from text_to_gds.quantum_device_database import (
        DeviceRecord,
        FabricationRecord,
        GeometryRecord,
        ProvenanceRecord,
        QuantumDeviceDatabase,
    )

    db_path = WORKSPACE_ROOT / "devices.db"
    db = QuantumDeviceDatabase(db_path)

    geo = GeometryRecord(**json.loads(geometry_json))
    if device_type:
        geo.device_type = device_type

    fab = FabricationRecord(process_id=process_id, jc_ua_per_um2=jc_ua_per_um2)
    prov = ProvenanceRecord(paper_doi=paper_doi)

    gds_hash = ""
    resolved_gds = ""
    if gds_path:
        try:
            resolved = _existing_path(gds_path)
            resolved_gds = str(resolved)
            gds_hash = db.compute_gds_hash(resolved)
        except FileNotFoundError:
            resolved_gds = gds_path

    record = DeviceRecord(
        device_id=device_id,
        gds_path=resolved_gds,
        gds_hash=gds_hash,
        status=status,
        geometry=geo,
        fabrication=fab,
        provenance=prov,
        tags=tags or [],
        sidecar_json=json.loads(sidecar_json),
    )

    db.record_device(record)
    db.close()

    return {
        "status": "recorded",
        "device_id": device_id,
        "gds_hash": gds_hash,
        "db_path": str(db_path),
    }


@mcp.tool()
def query_quantum_devices(
    device_type: str = "",
    status: str = "",
    process_id: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Query the quantum device database with optional filters."""
    from text_to_gds.quantum_device_database import QuantumDeviceDatabase

    db_path = WORKSPACE_ROOT / "devices.db"
    if not db_path.exists():
        return {"total": 0, "devices": [], "message": "Database empty or not created."}

    db = QuantumDeviceDatabase(db_path)
    devices = db.query_devices(
        device_type=device_type or None,
        status=status or None,
        process_id=process_id or None,
        limit=limit,
    )
    db.close()

    return {
        "total": len(devices),
        "devices": [
            {
                "device_id": d.device_id,
                "status": d.status,
                "device_type": d.geometry.device_type,
                "process_id": d.fabrication.process_id,
                "jc_ua_per_um2": d.fabrication.jc_ua_per_um2,
                "num_simulations": len(d.simulations),
                "num_measurements": len(d.measurements),
                "tags": d.tags,
            }
            for d in devices
        ],
    }


@mcp.tool()
def export_device_training_data() -> dict[str, Any]:
    """Export device database as (geometry, performance) training pairs."""
    from text_to_gds.quantum_device_database import QuantumDeviceDatabase

    db_path = WORKSPACE_ROOT / "devices.db"
    if not db_path.exists():
        return {"pairs": 0, "message": "Database empty."}

    db = QuantumDeviceDatabase(db_path)
    pairs = db.export_training_pairs()
    db.close()

    output = _artifact_path("device_training_pairs.json", ".json")
    output.write_text(json.dumps(pairs, indent=2), encoding="utf-8")

    return {
        "pairs": len(pairs),
        "output_path": str(output),
    }


@mcp.tool()
def check_physics_constraints(
    specs_json: str,
    device_id: str = "",
) -> dict[str, Any]:
    """Run physics constraint checks against a specification dict.

    Specs may include: gain_db, bandwidth_mhz, frequency_ghz,
    quality_factor, anharmonicity_ghz, pump_frequency_ghz,
    pump_power_dbm, flux_bias_ua, loop_area_um2, critical_current_ua,
    kinetic_inductance_ph, geometric_inductance_ph, etc.
    """
    from text_to_gds.physics_constraints import check_all_constraints

    specs = json.loads(specs_json) if isinstance(specs_json, str) else specs_json
    report = check_all_constraints(specs, device_id=device_id)
    return report.to_dict()


@mcp.tool()
def check_design_feasibility(
    device: str,
    targets_json: str,
    device_id: str = "",
) -> dict[str, Any]:
    """Pre-layout 'can this exist?' gate: ACCEPT/REJECT a spec before generating GDS.

    Combines the device template's validity ranges with the physics constraint
    engine (Bode-Fano, Manley-Rowe, Kerr, quantum noise). Returns blockers and a
    feasible/infeasible verdict. `device` is e.g. 'JPA', 'CPW', 'transmon'.
    """
    targets = json.loads(targets_json) if isinstance(targets_json, str) else targets_json
    return run_design_feasibility(device, targets, device_id=device_id)


@mcp.tool()
def list_physics_templates() -> dict[str, Any]:
    """List device physics templates (CPW, Resonator, JPA, JTWPA, SFQ, Transmon)."""
    return {"schema": "text-to-gds.physics-templates.v1", "templates": list_device_templates()}


@mcp.tool()
def validate_device_template(sidecar_path: str, device: str) -> dict[str, Any]:
    """Check a layout sidecar against a device template's must-have feature list."""
    sidecar = json.loads(_existing_path(sidecar_path).read_text(encoding="utf-8"))
    return validate_device_template_sidecar(sidecar, device)


@mcp.tool()
def review_layout(
    sidecar_path: str,
    simulation_path: str | None = None,
    drc_path: str | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    """Run the rule-based review committee on a layout's evidence.

    Aggregates the Physics, Microwave, Fabrication, and Measurement reviewers
    into a single approved/score verdict. The committee score is the minimum
    across reviewers, so any error keeps it below the 90 acceptance threshold.
    """
    evidence: dict[str, Any] = {
        "sidecar": json.loads(_existing_path(sidecar_path).read_text(encoding="utf-8"))
    }
    if simulation_path:
        evidence["simulation"] = json.loads(_existing_path(simulation_path).read_text(encoding="utf-8"))
    if drc_path:
        evidence["drc"] = json.loads(_existing_path(drc_path).read_text(encoding="utf-8"))
    if device:
        evidence["device"] = device
    return review_committee(evidence)


@mcp.tool()
def understand_layout(gds_path: str, sidecar_path: str | None = None) -> dict[str, Any]:
    """Parse a GDS into circuit elements and classify the device drawn."""
    gds = _existing_path(gds_path)
    sidecar = (
        json.loads(_existing_path(sidecar_path).read_text(encoding="utf-8")) if sidecar_path else None
    )
    return summarize_layout_circuit(gds, sidecar=sidecar)


@mcp.tool()
def run_open_benchmarks() -> dict[str, Any]:
    """Run the open functional benchmark suite (CPW Z0/f0, IDC 0.6 pF, JPA gain)."""
    return run_open_benchmark_suite()


@mcp.tool()
def run_ai_scientist(
    prompt: str,
    device: str = "JPA",
    targets_json: str | None = None,
    output_name: str = "ai_scientist.gds",
    jc_ua_per_um2: float = 2.0,
) -> dict[str, Any]:
    """End-to-end open-source pipeline: feasibility -> generate -> review -> readiness.

    Rejects an infeasible spec before any layout is generated. Otherwise runs the
    local open workflow, reviews the result with the committee, and returns a
    research-readiness verdict plus a Markdown review report. Uses no commercial
    solvers.
    """
    if targets_json:
        targets = json.loads(targets_json)
    else:
        plan = plan_ljpa(prompt)
        t = plan["target"]
        targets = {
            key: value
            for key, value in {
                "frequency_ghz": t.get("center_frequency_ghz"),
                "gain_db": t.get("gain_db"),
                "bandwidth_mhz": t.get("bandwidth_mhz"),
                "quality_factor": t.get("quality_factor"),
            }.items()
            if value is not None
        }

    feasibility = run_design_feasibility(device, targets)
    if not feasibility["accepted"]:
        return {
            "schema": "text-to-gds.ai-scientist.v1",
            "accepted": False,
            "stage": "feasibility",
            "verdict": "rejected_infeasible",
            "device": device,
            "targets": targets,
            "feasibility": feasibility,
            "recommendation": "Rejected before layout generation; adjust the targets.",
        }

    workflow = run_design_workflow(prompt, output_name=output_name, jc_ua_per_um2=jc_ua_per_um2)
    sidecar = json.loads(_existing_path(workflow["compile"]["sidecar_path"]).read_text(encoding="utf-8"))
    simulation = json.loads(_existing_path(workflow["simulation"]["result_path"]).read_text(encoding="utf-8"))
    evidence = {
        "device": device,
        "sidecar": sidecar,
        "simulation": simulation,
        "drc": workflow["drc"],
        "gds_path": workflow["compile"]["gds_path"],
    }
    assessment = assess_design(device, targets, evidence)
    report_path = _artifact_path(f"{Path(output_name).stem}.review_report.md", ".md")
    report = write_review_report(assessment, report_path)
    return {
        "schema": "text-to-gds.ai-scientist.v1",
        "accepted": assessment["accepted"],
        "stage": assessment["stage"],
        "verdict": assessment["verdict"],
        "device": device,
        "targets": targets,
        "assessment": assessment,
        "workflow_status": workflow["status"],
        "artifacts": {
            "gds": workflow["compile"]["gds_path"],
            "sidecar": workflow["compile"]["sidecar_path"],
            "review_report": report["report_path"],
        },
    }


@mcp.tool()
def predict_device_performance(
    source_path: str,
    device_id: str = "",
) -> dict[str, Any]:
    """Predict EM performance from GDS or sidecar using the layout transformer.

    Returns predicted f0, Q, Z0, eps_eff, S11, S21, gain, BW without
    running HFSS/openEMS.
    """
    from text_to_gds.device_prediction import DevicePredictor

    predictor = DevicePredictor()
    resolved = _existing_path(source_path)

    if resolved.suffix == ".gds":
        result = predictor.predict_from_gds(resolved, device_id=device_id)
    else:
        result = predictor.predict_from_sidecar(resolved, device_id=device_id)

    return result.to_dict()


@mcp.tool()
def score_layout_quality(
    sidecar_json: str = "{}",
    drc_json: str = "{}",
    target_specs_json: str = "{}",
) -> dict[str, Any]:
    """Score a quantum device layout on fabrication, design, and performance.

    Returns a composite quality grade (A-F) with issues and suggestions.
    """
    from text_to_gds.quality_scorer import LayoutQualityScorer

    sidecar = json.loads(sidecar_json) if isinstance(sidecar_json, str) else sidecar_json
    drc = json.loads(drc_json) if isinstance(drc_json, str) else drc_json
    targets = json.loads(target_specs_json) if isinstance(target_specs_json, str) else target_specs_json

    scorer = LayoutQualityScorer()
    score = scorer.score_layout(
        sidecar=sidecar,
        drc_result=drc,
        target_specs=targets,
    )
    return score.to_dict()


@mcp.tool()
def tokenize_layout(
    source_path: str,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Tokenize a GDS or sidecar into ML-ready token sequences.

    Returns token IDs, layer vocabulary, and metadata for the layout transformer.
    """
    from text_to_gds.gds_tokenizer import GDSTokenizer

    tokenizer = GDSTokenizer(max_tokens=max_tokens)
    resolved = _existing_path(source_path)

    if resolved.suffix == ".gds":
        seq = tokenizer.tokenize_gds(resolved)
    else:
        seq = tokenizer.tokenize_sidecar(resolved)

    return {
        "length": len(seq),
        "token_ids": seq.ids[:max_tokens],
        "layer_map": seq.layer_map,
        "metadata": seq.metadata,
        "vocab_size": tokenizer.vocab_size,
    }


@mcp.tool()
def list_quantum_devices() -> dict[str, Any]:
    """List all devices in the quantum device database with summary stats."""
    from text_to_gds.quantum_device_database import QuantumDeviceDatabase

    db_path = WORKSPACE_ROOT / "devices.db"
    if not db_path.exists():
        return {
            "total_devices": 0,
            "total_simulations": 0,
            "total_measurements": 0,
            "device_ids": [],
            "db_path": str(db_path),
        }

    db = QuantumDeviceDatabase(db_path)
    summary = db.summary()
    summary["device_ids"] = db.list_all_device_ids()
    db.close()
    return summary


def main() -> None:
    transport = os.environ.get("TEXT_TO_GDS_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
