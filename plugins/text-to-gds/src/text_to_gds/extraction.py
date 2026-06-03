from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.process import DEFAULT_PROCESS, Layer, layer_to_list


def _layer_name(layer: Layer) -> str:
    for name, spec in DEFAULT_PROCESS.layers.items():
        if spec.layer == layer:
            return name
    return f"L{layer[0]}D{layer[1]}"


def _layer_spec_dict(layer: Layer) -> dict[str, Any]:
    for spec in DEFAULT_PROCESS.layers.values():
        if spec.layer == layer:
            return {
                "name": spec.name,
                "layer": layer_to_list(spec.layer),
                "purpose": spec.purpose,
                "material": spec.material,
                "thickness_nm": spec.thickness_nm,
                "min_width_um": spec.min_width_um,
                "min_spacing_um": spec.min_spacing_um,
            }
    return {
        "name": _layer_name(layer),
        "layer": layer_to_list(layer),
        "purpose": "unknown",
        "material": "unknown",
        "thickness_nm": 0.0,
        "min_width_um": 0.0,
        "min_spacing_um": 0.0,
    }


def layer_bounding_boxes_from_gds(gds_path: str | Path) -> list[dict[str, Any]]:
    """Extract rectangular shape bounding boxes from a GDS file with KLayout Python."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    boxes: list[dict[str, Any]] = []
    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        layer = (int(info.layer), int(info.datatype))
        layer_spec = _layer_spec_dict(layer)
        for cell in layout.each_cell():
            for shape in cell.shapes(layer_index).each():
                bbox = shape.bbox()
                width_um = abs(float(bbox.width()) * dbu)
                height_um = abs(float(bbox.height()) * dbu)
                if width_um <= 0.0 or height_um <= 0.0:
                    continue
                boxes.append(
                    {
                        "cell": cell.name,
                        "layer": layer_to_list(layer),
                        "layer_name": layer_spec["name"],
                        "material": layer_spec["material"],
                        "thickness_nm": layer_spec["thickness_nm"],
                        "bbox_um": [
                            float(bbox.left) * dbu,
                            float(bbox.bottom) * dbu,
                            float(bbox.right) * dbu,
                            float(bbox.top) * dbu,
                        ],
                        "width_um": width_um,
                        "height_um": height_um,
                        "area_um2": width_um * height_um,
                    }
                )
    return boxes


def labels_from_gds(gds_path: str | Path) -> list[dict[str, Any]]:
    """Extract text labels from a GDS file with KLayout Python."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    labels: list[dict[str, Any]] = []
    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        layer = (int(info.layer), int(info.datatype))
        layer_spec = _layer_spec_dict(layer)
        for cell in layout.each_cell():
            for shape in cell.shapes(layer_index).each():
                if not shape.is_text():
                    continue
                text = shape.text
                labels.append(
                    {
                        "cell": cell.name,
                        "text": text.string,
                        "layer": layer_to_list(layer),
                        "layer_name": layer_spec["name"],
                        "material": layer_spec["material"],
                        "position_um": [
                            float(text.trans.disp.x) * dbu,
                            float(text.trans.disp.y) * dbu,
                        ],
                    }
                )
    return labels


def summarize_sidecar_parameters(sidecar: dict[str, Any]) -> dict[str, Any]:
    """Return performance-relevant geometry/process parameters from a sidecar."""
    info = sidecar.get("info", {})
    parameters = {
        key: value
        for key, value in info.items()
        if key.endswith("_um")
        or key.endswith("_um2")
        or key.endswith("_nm")
        or key.endswith("_deg")
        or key in {"num_turns", "layers"}
    }
    layers = info.get("layers", {})
    layer_stack = []
    if isinstance(layers, dict):
        for role, value in layers.items():
            if isinstance(value, (list, tuple)) and len(value) == 2:
                layer = (int(value[0]), int(value[1]))
                spec = _layer_spec_dict(layer)
                spec["role"] = role
                layer_stack.append(spec)

    impacts = []
    if "junction_area_um2" in info:
        impacts.append("junction_area_um2 sets critical current for a given Jc and therefore Lj")
    if "trace_width_um" in info:
        impacts.append("trace_width_um changes impedance, current density, and kinetic inductance")
    if "gap_um" in info:
        impacts.append("gap_um changes CPW impedance and coupling")
    if "length_um" in info or "electrical_length_um" in info:
        impacts.append("length_um/electrical_length_um changes delay, resonance, and phase")
    if "angle_deg" in info:
        impacts.append("angle_deg affects routing orientation and coupling to nearby structures")
    if layer_stack:
        impacts.append("layer material and thickness affect inductance, loss, and DRC margins")

    return {
        "schema": "text-to-gds.extraction-summary.v0",
        "pcell": sidecar.get("pcell"),
        "gds_path": sidecar.get("gds_path"),
        "bbox_um": sidecar.get("bbox_um"),
        "ports": sidecar.get("ports", []),
        "labels": sidecar.get("labels", []),
        "parameters": parameters,
        "layer_stack": layer_stack,
        "performance_impacts": impacts,
    }
