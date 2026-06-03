from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from text_to_gds.pcells import manhattan_josephson_junction
from text_to_gds.simulation import simulate_ideal_junction

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("TEXT_TO_GDS_WORKSPACE", PROJECT_ROOT / "workspace")).resolve()
ARTIFACT_ROOT = WORKSPACE_ROOT / "artifacts"

mcp = FastMCP("Text-to-GDS", json_response=True)

PCELL_REGISTRY = {
    "manhattan_josephson_junction": manhattan_josephson_junction,
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
        "info": dict(component.info),
    }


def _layer_color(layer: list[int]) -> tuple[int, int, int, int]:
    palette = {
        (3, 0): (56, 102, 214, 190),
        (4, 0): (218, 73, 86, 210),
        (5, 0): (48, 154, 103, 190),
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
def run_simulation(
    sidecar_path: str,
    simulator: str = "mock_jj",
    jc_ua_per_um2: float = 1.0,
    shunt_capacitance_ff: float = 0.0,
) -> dict[str, Any]:
    """Run a mock Josephson Junction calculation from the semantic sidecar."""
    sidecar_file = _existing_path(sidecar_path)
    sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))

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

    output_path = _artifact_path(f"{sidecar_file.stem}.simulation.json", ".json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["result_path"] = str(output_path)
    return result


def main() -> None:
    transport = os.environ.get("TEXT_TO_GDS_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
