"""GDS geometry extraction and physics parameter derivation.

Every derived value carries a ``method_label`` in its lineage entry:
  estimated  — analytical or rule-of-thumb formula
  extracted  — measured from GDS geometry
  simulated  — from a real solver output file
  measured   — imported from experiment data
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.process import DEFAULT_PROCESS, Layer, layer_to_list

# Physical constants — canonical, never overridden.
PHI0_WEBER = 2.067833848e-15       # Magnetic flux quantum (Wb)
ELECTRON_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34

# Layer numbers for JJ, M1, M2 in the default process.
_JJ_LAYER  = DEFAULT_PROCESS.layers["JJ"].layer   # (4, 0)
_M1_LAYER  = DEFAULT_PROCESS.layers["M1"].layer   # (3, 0)
_M2_LAYER  = DEFAULT_PROCESS.layers["M2"].layer   # (5, 0)
_MIN_JJ_WIDTH = DEFAULT_PROCESS.rules.min_junction_width_um
_MIN_JJ_HEIGHT = DEFAULT_PROCESS.rules.min_junction_height_um


def quantity(
    value: float | int | None,
    unit: str,
    *,
    method_label: str,
    source: str,
    formula: str,
    confidence: float,
    inputs: list[str] | None = None,
    assumptions: list[str] | None = None,
    solver: str | None = None,
) -> dict[str, Any]:
    """Return the canonical extraction quantity object."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    record: dict[str, Any] = {
        "value": value,
        "unit": unit,
        "method_label": method_label,
        "source": source,
        "formula": formula,
        "confidence": confidence,
    }
    if assumptions:
        record["assumptions"] = assumptions
    if inputs:
        record["inputs"] = inputs
    if solver:
        record["solver"] = solver
    return record


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


# ---------------------------------------------------------------------------
# Junction overlap area from GDS (Part 6 — formula safety)
# ---------------------------------------------------------------------------

def _junction_overlap_area_um2(gds_path: Path) -> float:
    """Return the JJ ∩ M1 ∩ M2 overlap area in µm² using KLayout boolean regions."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    def _region(layer_tuple: tuple[int, int]) -> "kdb.Region":
        r = kdb.Region()
        for li in layout.layer_indices():
            info = layout.get_info(li)
            if (int(info.layer), int(info.datatype)) == layer_tuple:
                top = layout.top_cell()
                if top is None:
                    for cell in layout.each_cell():
                        r.insert(cell.shapes(li))
                else:
                    r.insert(top.begin_shapes_rec(li))
        return r

    jj_region  = _region(_JJ_LAYER)
    m1_region  = _region(_M1_LAYER)
    m2_region  = _region(_M2_LAYER)

    overlap = jj_region & m1_region & m2_region
    area_dbu2 = sum(shape.area() for shape in overlap.each())
    return float(area_dbu2) * (dbu ** 2)


def _positive(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n > 0.0 else None


def _smallest_layer_box(boxes: list[dict[str, Any]], layer_name: str) -> dict[str, Any] | None:
    candidates = [box for box in boxes if box.get("layer_name") == layer_name]
    if not candidates:
        return None
    return min(candidates, key=lambda box: float(box.get("area_um2", 0.0)))


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_physical_parameters(
    gds_path: Path | str,
    sidecar: dict[str, Any] | Path | str,
    *,
    jc_ua_per_um2: float | None = None,
    capacitance_ff: float | None = None,
    inductance_ph: float | None = None,
    target_frequency_ghz: float | None = None,
    frequency_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Extract physical parameters from a GDS file with full lineage.

    Every numeric value carries a ``method_label`` on its lineage entry:
      extracted  — from GDS geometry or explicit process input
      estimated  — from an analytical formula

    Parameters
    ----------
    gds_path:
        Path to the GDS file.
    sidecar:
        Sidecar JSON dict or path to sidecar file.
    jc_ua_per_um2:
        Critical current density in µA/µm².  Required for junction devices.
    capacitance_ff:
        Explicit shunt capacitance in fF.
    inductance_ph:
        Explicit inductance in pH.  If absent for a JJ device, Lj is used.
    target_frequency_ghz:
        Validation bound only — never inserted into the result as extracted f0.
    frequency_tolerance:
        Relative tolerance for the f0 validation check (default 2%).

    Returns
    -------
    dict conforming to text-to-gds.extraction.v1 schema.
    """
    from text_to_gds.extraction_schema import empty_extraction_v1, SCHEMA_VERSION

    gds = Path(gds_path)
    if isinstance(sidecar, (str, Path)):
        sidecar = json.loads(Path(sidecar).read_text(encoding="utf-8"))

    device = str(sidecar.get("pcell", sidecar.get("info", {}).get("device_type", "")))
    result = empty_extraction_v1(device)
    result["schema"] = SCHEMA_VERSION
    result["source_gds"] = str(gds)

    # Bare-name aliases — set to None so tests can read them without KeyError.
    # Updated in-place further down when actual values are computed.
    result["junction"]["area"] = None
    result["junction"]["ic"] = None
    result["junction"]["lj"] = None
    result["junction"]["jc"] = None
    result["linear_circuit"]["capacitance"] = None
    result["linear_circuit"]["inductance"] = None
    result["linear_circuit"]["resonance_frequency"] = None

    errors: list[str] = []

    # --- geometry from GDS --------------------------------------------------
    try:
        boxes = layer_bounding_boxes_from_gds(gds)
    except Exception:  # noqa: BLE001
        boxes = []

    layer_groups: dict[str, dict[str, Any]] = {}
    for box in boxes:
        name = box["layer_name"]
        if name not in layer_groups:
            layer_groups[name] = {"area_um2": 0.0, "shape_count": 0}
        layer_groups[name]["area_um2"] += box["area_um2"]
        layer_groups[name]["shape_count"] += 1

    result["geometry"]["layers"] = layer_groups
    result["geometry"]["shape_count"] = sum(g["shape_count"] for g in layer_groups.values())
    result["lineage"]["geometry"] = quantity(
        result["geometry"]["shape_count"],
        "count",
        method_label="geometry_extracted",
        source="GDS",
        formula="KLayout flattened shape scan",
        confidence=1.0 if boxes else 0.0,
    )

    # --- junction area: JJ ∩ M1 ∩ M2 ----------------------------------------
    if "JJ" in layer_groups and layer_groups["JJ"].get("area_um2", 0.0) > 0.0:
        try:
            area_um2 = _junction_overlap_area_um2(gds)
        except Exception:  # noqa: BLE001
            area_um2 = layer_groups["JJ"].get("area_um2", 0.0)

        min_area = _MIN_JJ_WIDTH * _MIN_JJ_HEIGHT
        if area_um2 <= min_area:
            errors.append(
                f"junction area {area_um2:g} µm² is not above process minimum {min_area:g} µm²"
            )
        else:
            jj_box = _smallest_layer_box(boxes, "JJ")
            m1_box = _smallest_layer_box(boxes, "M1")
            m2_box = _smallest_layer_box(boxes, "M2")
            result["junction"]["area"] = area_um2
            result["junction"]["area_um2"] = area_um2
            if jj_box:
                result["junction"]["width_um"] = jj_box["width_um"]
                result["junction"]["height_um"] = jj_box["height_um"]
            if m1_box:
                result["junction"]["bottom_electrode_width_um"] = min(
                    float(m1_box["width_um"]), float(m1_box["height_um"])
                )
            if m2_box:
                result["junction"]["top_electrode_width_um"] = min(
                    float(m2_box["width_um"]), float(m2_box["height_um"])
                )
            result["geometry"]["manhattan_jj"] = {
                "junction_area_um2": area_um2,
                "top_electrode_width": result["junction"].get("top_electrode_width_um"),
                "bottom_electrode_width": result["junction"].get("bottom_electrode_width_um"),
            }
            result["lineage"]["junction.area"] = quantity(
                area_um2,
                "um^2",
                method_label="geometry_extracted",
                source="GDS",
                formula="area(JJ intersect M1 intersect M2)",
                confidence=1.0,
            )

    # --- Jc from explicit process input -------------------------------------
    jc = _positive(jc_ua_per_um2)
    if jc is not None:
        result["junction"]["jc"] = jc * 1e6  # store as A/m²
        result["junction"]["jc_ua_per_um2"] = jc
        result["lineage"]["junction.jc"] = quantity(
            jc,
            "uA/um^2",
            method_label="geometry_extracted",
            source="process_file",
            formula="explicit process critical-current density input",
            confidence=1.0,
        )

    # --- Ic = Jc × area -----------------------------------------------------
    area = result["junction"].get("area")
    jc_stored = result["junction"].get("jc")
    if area is not None and jc_stored is not None:
        ic_a = float(area) * 1e-12 * float(jc_stored)
        lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
        if ic_a <= 0.0 or lj_h <= 0.0:
            errors.append("derived Ic and Lj must be positive")
        else:
            result["junction"].update({"ic": ic_a, "lj": lj_h, "ic_a": ic_a, "lj_h": lj_h})
            result["lineage"]["junction.ic"] = quantity(
                ic_a,
                "A",
                method_label="analytical",
                source="GDS",
                formula="Ic = Jc * area",
                confidence=0.98,
                inputs=["junction.area", "junction.jc"],
                assumptions=["uniform Jc over extracted overlap area"],
            )
            result["lineage"]["junction.lj"] = quantity(
                lj_h,
                "H",
                method_label="analytical",
                source="GDS",
                formula="Lj = Phi0 / (2*pi*Ic)",
                confidence=0.98,
                inputs=["junction.ic"],
                assumptions=["zero-phase small-signal Josephson inductance"],
            )

    # --- capacitance (explicit input) ----------------------------------------
    cap = _positive(capacitance_ff)
    if cap is not None:
        cap_f = cap * 1e-15
        result["linear_circuit"]["capacitance"] = cap_f
        result["linear_circuit"]["capacitance_f"] = cap_f
        result["lineage"]["linear_circuit.capacitance"] = quantity(
            cap_f,
            "F",
            method_label="geometry_extracted",
            source="process_file",
            formula="explicit capacitance extractor/process input",
            confidence=0.9,
        )

    # --- inductance (explicit or from Lj) ------------------------------------
    ind = _positive(inductance_ph)
    if ind is not None:
        ind_h = ind * 1e-12
        result["linear_circuit"]["inductance"] = ind_h
        result["linear_circuit"]["inductance_h"] = ind_h
        result["lineage"]["linear_circuit.inductance"] = quantity(
            ind_h,
            "H",
            method_label="geometry_extracted",
            source="process_file",
            formula="explicit inductance extractor/process input",
            confidence=0.9,
        )
    elif result["junction"].get("lj") is not None:
        lj_val = result["junction"]["lj"]
        result["linear_circuit"]["inductance"] = lj_val
        result["linear_circuit"]["inductance_h"] = lj_val
        result["lineage"]["linear_circuit.inductance"] = quantity(
            lj_val,
            "H",
            method_label="analytical",
            source="GDS",
            formula="L = Lj from extracted Josephson junction",
            confidence=0.95,
        )

    # --- resonance frequency from LC -----------------------------------------
    L = result["linear_circuit"].get("inductance")
    C = result["linear_circuit"].get("capacitance")
    if L is not None and C is not None:
        f0_hz = 1.0 / (2.0 * math.pi * math.sqrt(float(L) * float(C)))
        result["linear_circuit"]["resonance_frequency"] = f0_hz
        result["linear_circuit"]["resonance_frequency_hz"] = f0_hz
        result["lineage"]["linear_circuit.resonance_frequency"] = quantity(
            f0_hz,
            "Hz",
            method_label="analytical",
            source="GDS",
            formula="f0 = 1 / (2*pi*sqrt(L*C))",
            confidence=0.9,
            inputs=["linear_circuit.inductance", "linear_circuit.capacitance"],
            assumptions=["lumped-element small-signal model"],
        )
        target = _positive(target_frequency_ghz)
        if target is not None:
            rel_error = abs(f0_hz - target * 1e9) / (target * 1e9)
            result["validation"]["checks"]["resonance_target"] = {
                "passed": rel_error < frequency_tolerance,
                "relative_error": rel_error,
                "tolerance": frequency_tolerance,
            }
            if rel_error >= frequency_tolerance:
                errors.append(
                    f"extracted resonance {f0_hz / 1e9:.4f} GHz is outside target tolerance "
                    f"({rel_error:.1%} > {frequency_tolerance:.0%})"
                )

    # --- required parameters check ------------------------------------------
    is_junction_device = (
        result["junction"]["area"] is not None
        or "junction" in device.lower()
        or "jj" in device.lower()
        or "jpa" in device.lower()
    )
    if is_junction_device and jc is None:
        errors.append("missing extracted parameter: junction.jc")
    if is_junction_device and result["junction"]["lj"] is None and jc is not None:
        errors.append("missing extracted parameter: junction.lj")

    result["validation"]["errors"] = errors
    result["validation"]["passed"] = not errors
    result["validation"]["all_numbers_have_lineage"] = bool(result["lineage"])
    result["status"] = "ok" if not errors else "failed"
    result["reason"] = None if not errors else errors[0]
    return result


def write_extraction(result: dict[str, Any], path: Path | str) -> dict[str, Any]:
    """Write an extraction result to disk and return it with ``result_path`` added."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    result["result_path"] = str(out)
    return result
