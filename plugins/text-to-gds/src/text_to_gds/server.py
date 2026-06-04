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
    run_josephsoncircuits,
    run_josim_transient,
    write_josephsoncircuits_script,
)
from text_to_gds.design import plan_ljpa_design
from text_to_gds.drc import parse_drc_report, run_external_klayout_drc, run_python_process_drc
from text_to_gds.extraction import (
    labels_from_gds,
    layer_bounding_boxes_from_gds,
    summarize_sidecar_parameters,
)
from text_to_gds.optimization import optimize_ljpa_parameters
from text_to_gds.pcells import (
    cpw_straight,
    flux_bias_line,
    ground_plane,
    lumped_element_jpa_seed,
    manhattan_josephson_junction,
    meander_inductor,
    via_stack,
)
from text_to_gds.preview import write_stack_preview
from text_to_gds.process import DEFAULT_PROCESS
from text_to_gds.simulation import simulate_ideal_junction
from text_to_gds.workbench import write_design_workbench

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("TEXT_TO_GDS_WORKSPACE", PROJECT_ROOT / "workspace")).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts"

mcp = FastMCP("Text-to-GDS", json_response=True)

PCELL_REGISTRY = {
    "cpw_straight": cpw_straight,
    "flux_bias_line": flux_bias_line,
    "ground_plane": ground_plane,
    "lumped_element_jpa_seed": lumped_element_jpa_seed,
    "manhattan_josephson_junction": manhattan_josephson_junction,
    "meander_inductor": meander_inductor,
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


def _port_to_dict(name: str, port: Any) -> dict[str, Any]:
    layer_info = getattr(port, "layer_info", None)
    if layer_info is not None:
        layer = [int(layer_info.layer), int(layer_info.datatype)]
    else:
        port_layer = getattr(port, "layer", None)
        layer = list(port_layer) if isinstance(port_layer, tuple) else port_layer
    return {
        "name": name,
        "center": [float(v) for v in getattr(port, "center", (0.0, 0.0))],
        "width": float(getattr(port, "width", 0.0)),
        "orientation": getattr(port, "orientation", None),
        "layer": layer,
        "port_type": getattr(port, "port_type", "electrical"),
    }


def _component_sidecar(
    component: Any,
    gds_path: Path,
    pcell: str,
    screenshot_path: Path,
) -> dict[str, Any]:
    try:
        port_items = component.ports.items()
    except AttributeError:
        port_items = [(p.name, p) for p in component.get_ports_list()]

    bbox = component.bbox_np().tolist() if hasattr(component, "bbox_np") else None
    return {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": pcell,
        "gds_path": str(gds_path),
        "screenshot_path": str(screenshot_path),
        "bbox_um": bbox,
        "ports": [_port_to_dict(name, port) for name, port in port_items],
        "labels": labels_from_gds(gds_path),
        "info": dict(component.info),
        "process_stack": DEFAULT_PROCESS.to_dict(),
    }


def _layer_color(layer: list[int]) -> tuple[int, int, int, int]:
    palette = {
        (3, 0): (56, 102, 214, 190),
        (4, 0): (218, 73, 86, 210),
        (5, 0): (48, 154, 103, 190),
        (6, 0): (124, 58, 237, 180),
        (7, 0): (245, 158, 11, 210),
        (8, 0): (249, 115, 22, 210),
        (10, 0): (90, 90, 90, 170),
    }
    key = (layer[0], layer[1])
    if key in palette:
        return palette[key]
    seed = (layer[0] * 97 + layer[1] * 53) % 255
    return (80 + seed % 120, 80 + (seed * 3) % 120, 80 + (seed * 7) % 120, 180)


def _render_layout_screenshot(
    layout_path: Path,
    screenshot_path: Path,
    *,
    image_size: int = 1000,
) -> None:
    import klayout.db as kdb
    from PIL import Image, ImageDraw

    layout = kdb.Layout()
    layout.read(str(layout_path))
    dbu = float(layout.dbu)

    shapes: list[tuple[list[float], list[int]]] = []
    for layer_index in layout.layer_indices():
        layer_info = layout.get_info(layer_index)
        layer = [int(layer_info.layer), int(layer_info.datatype)]
        for cell in layout.each_cell():
            for shape in cell.shapes(layer_index).each():
                bbox = shape.bbox()
                width_um = float(bbox.width()) * dbu
                height_um = float(bbox.height()) * dbu
                if width_um <= 0.0 or height_um <= 0.0:
                    continue
                shapes.append(
                    (
                        [
                            float(bbox.left) * dbu,
                            float(bbox.bottom) * dbu,
                            float(bbox.right) * dbu,
                            float(bbox.top) * dbu,
                        ],
                        layer,
                    )
                )

    layer_order = {
        (3, 0): 0,
        (4, 0): 1,
        (5, 0): 2,
        (7, 0): 3,
        (6, 0): 4,
        (8, 0): 5,
        (10, 0): 6,
    }
    shapes.sort(key=lambda item: layer_order.get((item[1][0], item[1][1]), 99))

    image = Image.new("RGBA", (image_size, image_size), (250, 251, 252, 255))
    draw = ImageDraw.Draw(image, "RGBA")

    if not shapes:
        draw.text((24, 24), f"No drawable shapes in {layout_path.name}", fill=(30, 41, 59, 255))
        image.convert("RGB").save(screenshot_path)
        return

    min_x = min(shape[0][0] for shape in shapes)
    min_y = min(shape[0][1] for shape in shapes)
    max_x = max(shape[0][2] for shape in shapes)
    max_y = max(shape[0][3] for shape in shapes)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    margin = max(image_size * 0.08, 24.0)
    scale = min((image_size - 2 * margin) / span_x, (image_size - 2 * margin) / span_y)

    def to_px(x_um: float, y_um: float) -> tuple[float, float]:
        x_px = margin + (x_um - min_x) * scale
        y_px = image_size - (margin + (y_um - min_y) * scale)
        return x_px, y_px

    for bbox_um, layer in shapes:
        left, bottom, right, top = bbox_um
        points = [
            to_px(left, bottom),
            to_px(right, bottom),
            to_px(right, top),
            to_px(left, top),
        ]
        fill = _layer_color(layer)
        outline = (20, 31, 46, 220)
        draw.polygon(points, fill=fill, outline=outline)

    draw.rectangle((8, 8, image_size - 8, image_size - 8), outline=(148, 163, 184, 255), width=2)
    draw.text((18, 18), layout_path.name, fill=(30, 41, 59, 255))
    image.convert("RGB").save(screenshot_path)


def _scan_min_width_violations(
    layout_path: Path,
    min_width_um: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import klayout.db as kdb
    except ImportError:
        return [], {
            "engine": "mock",
            "checked_shapes": 0,
            "warnings": ["KLayout Python module is unavailable; skipped geometry scan."],
        }

    layout = kdb.Layout()
    layout.read(str(layout_path))

    violations: list[dict[str, Any]] = []
    checked_shapes = 0
    dbu = float(layout.dbu)

    for layer_index in layout.layer_indices():
        layer_info = layout.get_info(layer_index)
        layer = [int(layer_info.layer), int(layer_info.datatype)]
        for cell in layout.each_cell():
            for shape in cell.shapes(layer_index).each():
                bbox = shape.bbox()
                width_um = abs(float(bbox.width()) * dbu)
                height_um = abs(float(bbox.height()) * dbu)
                if width_um <= 0.0 or height_um <= 0.0:
                    continue

                checked_shapes += 1
                min_dimension_um = min(width_um, height_um)
                if min_dimension_um < min_width_um:
                    violations.append(
                        {
                            "rule": "min_bbox_width",
                            "message": (
                                f"Shape minimum bounding-box dimension {min_dimension_um:.6g} um "
                                f"is below {min_width_um:.6g} um."
                            ),
                            "severity": "error",
                            "cell": cell.name,
                            "layer": layer,
                            "bbox_um": [
                                float(bbox.left) * dbu,
                                float(bbox.bottom) * dbu,
                                float(bbox.right) * dbu,
                                float(bbox.top) * dbu,
                            ],
                            "min_dimension_um": min_dimension_um,
                        }
                    )

    return violations, {
        "engine": "klayout_python_bbox",
        "checked_shapes": checked_shapes,
        "dbu_um": dbu,
        "warnings": [],
    }


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
def list_simulators() -> dict[str, Any]:
    """List local external simulator adapters and installation hints."""
    return {
        "schema": "text-to-gds.simulators.v0",
        "adapters": list_simulation_adapters(),
    }


@mcp.tool()
def plan_ljpa(prompt: str) -> dict[str, Any]:
    """Convert an LJPA prompt into clarification questions and a local design workflow."""
    return plan_ljpa_design(prompt)


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
def run_design_workflow(
    prompt: str,
    output_name: str = "ljpa_seed.gds",
    parameters: dict[str, Any] | None = None,
    jc_ua_per_um2: float = 2.0,
    simulator: str = "mock_jj",
) -> dict[str, Any]:
    """Run a local prompt-to-layout workflow and write a browser workbench."""
    plan = plan_ljpa_design(prompt)
    target = plan["target"]
    pcell_parameters = {
        "center_frequency_ghz": target.get("center_frequency_ghz") or 5.0,
        "target_bandwidth_mhz": target.get("bandwidth_mhz") or 500.0,
        "target_gain_db": target.get("gain_db") or 20.0,
    }
    pcell_parameters.update(parameters or {})

    compiled = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters=pcell_parameters,
        output_name=output_name,
    )
    drc = run_drc(compiled["gds_path"])
    process_drc = run_process_drc(compiled["gds_path"], output_name=f"{Path(output_name).stem}.process")
    extraction = extract_layout(compiled["sidecar_path"])
    preview = export_3d_preview(compiled["gds_path"])
    simulation = run_simulation(
        compiled["sidecar_path"],
        simulator=simulator,
        jc_ua_per_um2=jc_ua_per_um2,
        target_frequency_ghz=target.get("center_frequency_ghz"),
        target_gain_db=target.get("gain_db") or 20.0,
        target_bandwidth_mhz=target.get("bandwidth_mhz"),
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
        "preview": preview,
        "simulation": simulation,
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
) -> dict[str, Any]:
    """Optimize first-pass LJPA geometry with a local surrogate, then run workflow."""
    plan = plan_ljpa_design(prompt)
    target = plan["target"]
    optimization = optimize_ljpa_parameters(
        target_frequency_ghz=float(target.get("center_frequency_ghz") or 5.0),
        target_bandwidth_mhz=float(target.get("bandwidth_mhz") or 500.0),
        target_gain_db=float(target.get("gain_db") or 20.0),
        initial_parameters={key: float(value) for key, value in (parameters or {}).items()},
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
    adapter_executable: str | None = None,
    target_frequency_ghz: float | None = None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
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
        ),
    }
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
    elif normalized_simulator in {"josephsoncircuits.jl", "josephsoncircuits", "externaljulia"}:
        script_path = _artifact_path(f"{sidecar_file.stem}.josephsoncircuits.jl", ".jl")
        jc_result_path = _artifact_path(f"{sidecar_file.stem}.josephsoncircuits.json", ".json")
        write_josephsoncircuits_script(
            sidecar,
            script_path=script_path,
            result_path=jc_result_path,
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
            target_frequency_ghz=target_frequency_ghz,
            target_gain_db=target_gain_db,
            target_bandwidth_mhz=target_bandwidth_mhz,
        )
        result["adapter_result"] = adapter_result

    output_path = _artifact_path(f"{sidecar_file.stem}.simulation.json", ".json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["result_path"] = str(output_path)
    return result


def main() -> None:
    transport = os.environ.get("TEXT_TO_GDS_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
