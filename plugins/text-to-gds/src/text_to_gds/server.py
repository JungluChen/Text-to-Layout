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


def _component_sidecar(component: Any, gds_path: Path, pcell: str) -> dict[str, Any]:
    try:
        port_items = component.ports.items()
    except AttributeError:
        port_items = [(p.name, p) for p in component.get_ports_list()]

    bbox = component.bbox_np().tolist() if hasattr(component, "bbox_np") else None
    return {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": pcell,
        "gds_path": str(gds_path),
        "bbox_um": bbox,
        "ports": [_port_to_dict(name, port) for name, port in port_items],
        "info": dict(component.info),
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
    component.write_gds(str(gds_path))

    sidecar = _component_sidecar(component, gds_path, pcell)
    sidecar_path = gds_path.with_suffix(".sidecar.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    return {"status": "compiled", "gds_path": str(gds_path), "sidecar_path": str(sidecar_path)}


@mcp.tool()
def run_drc(
    gds_path: str,
    ruleset: str = "mock_min_width",
    min_width_um: float = 0.1,
) -> dict[str, Any]:
    """Run a mock DRC pass and emit a JSON report shaped like a future KLayout adapter."""
    layout_path = _existing_path(gds_path)
    violations: list[dict[str, Any]] = []

    if layout_path.suffix.lower() != ".gds":
        violations.append(
            {
                "rule": "input_format",
                "message": "DRC input must be a .gds file.",
                "severity": "error",
            }
        )

    report = {
        "schema": "text-to-gds.drc.v0",
        "engine": "mock",
        "ruleset": ruleset,
        "input_gds": str(layout_path),
        "min_width_um": min_width_um,
        "status": "passed" if not violations else "failed",
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
