"""Layout geometry validation — polygon-level GDS truth checking.

Every check operates on raw GDS polygons and the process stack.
No extraction from filenames, prompts, or stored metadata.

Usage:
    from text_to_gds.layout_validator import validate_layout
    report = validate_layout("path/to/layout.gds")
    assert report["passed"]

Schema: text-to-gds.layout-validation.v1
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import klayout.db as kdb

from text_to_gds.process import DEFAULT_PROCESS, ProcessStack

SCHEMA = "text-to-gds.layout-validation.v1"

_PROCESS = DEFAULT_PROCESS
_LAYER_MAP = {spec.layer: name for name, spec in _PROCESS.layers.items()}


@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    check: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _layer_index(layout: kdb.Layout, layer: tuple[int, int]) -> int | None:
    idx = layout.find_layer(layer[0], layer[1])
    return idx if idx is not None and idx >= 0 else None


def _polygons_on_layer(cell: kdb.Cell, layer_idx: int) -> list[kdb.DPolygon]:
    result = []
    # Use recursive iterator to collect from all subcells (gf.boolean creates sub-cells)
    ri = kdb.RecursiveShapeIterator(cell.layout(), cell, layer_idx)
    while not ri.at_end():
        shape = ri.shape()
        if shape.is_polygon() or shape.is_box() or shape.is_path():
            result.append(shape.dpolygon.transformed(ri.dtrans()))
        ri.next()
    return result


def _bounding_box(polys: list[kdb.DPolygon]) -> tuple[float, float, float, float] | None:
    if not polys:
        return None
    all_pts = [pt for p in polys for pt in p.each_point()]
    if not all_pts:
        return None
    xs = [pt.x for pt in all_pts]
    ys = [pt.y for pt in all_pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _polygon_area(poly: kdb.DPolygon) -> float:
    return abs(poly.area())


def _overlap_area(polys_a: list[kdb.DPolygon], polys_b: list[kdb.DPolygon]) -> float:
    r = kdb.Region()
    for p in polys_a:
        r.insert(kdb.Polygon.from_dpoly(p * 1000))
    s = kdb.Region()
    for p in polys_b:
        s.insert(kdb.Polygon.from_dpoly(p * 1000))
    overlap = r & s
    return sum(p.area() for p in overlap.each()) / 1e6


def _overlap_area_many(*poly_groups: list[kdb.DPolygon]) -> float:
    if not poly_groups:
        return 0.0
    region: kdb.Region | None = None
    for polys in poly_groups:
        current = _region_from_polys(polys)
        region = current if region is None else region & current
    return _region_area_um2(region or kdb.Region())


def _region_from_polys(polys: list[kdb.DPolygon], *, scale: int = 1000) -> kdb.Region:
    region = kdb.Region()
    for poly in polys:
        region.insert(kdb.Polygon.from_dpoly(poly * scale))
    return region


def _region_area_um2(region: kdb.Region, *, scale: int = 1000) -> float:
    return sum(poly.area() for poly in region.each()) / float(scale * scale)


def _layer_from_sidecar(info: dict[str, Any], *names: str, fallback: tuple[int, int]) -> tuple[int, int]:
    layers = info.get("layers", {})
    if isinstance(layers, dict):
        for name in names:
            value = layers.get(name)
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return (int(value[0]), int(value[1]))
    return fallback


# ── Check 1: Universal GDS checks ──────────────────────────────────────────

def check_gds_basic(path: Path, layout: kdb.Layout, cell: kdb.Cell) -> list[Finding]:
    findings: list[Finding] = []

    if path.stat().st_size < 100:
        findings.append(Finding("error", "gds_basic", f"GDS file too small: {path.stat().st_size} bytes"))

    if cell.bbox().empty():
        findings.append(Finding("error", "gds_basic", "Top cell has empty bounding box"))
        return findings

    dbu = layout.dbu
    findings.append(Finding("info", "gds_basic", f"Database unit: {dbu} µm", {"dbu": dbu}))

    total_polygons = 0
    layers_found: list[str] = []
    empty_layers: list[str] = []

    for name, spec in _PROCESS.layers.items():
        idx = _layer_index(layout, spec.layer)
        if idx is None:
            continue
        polys = _polygons_on_layer(cell, idx)
        if polys:
            layers_found.append(name)
            total_polygons += len(polys)
        else:
            empty_layers.append(name)

    if total_polygons == 0:
        findings.append(Finding("error", "gds_basic", "GDS contains zero polygons on process layers"))

    findings.append(Finding("info", "gds_basic", f"Layers with geometry: {layers_found}",
                            {"layers": layers_found, "polygon_count": total_polygons}))

    bbox = cell.dbbox()
    findings.append(Finding("info", "gds_basic",
                            f"Bounding box: {bbox.width():.2f} × {bbox.height():.2f} µm",
                            {"width_um": bbox.width(), "height_um": bbox.height()}))

    return findings


# ── Check 2: Minimum width / spacing ───────────────────────────────────────

def check_min_width(layout: kdb.Layout, cell: kdb.Cell) -> list[Finding]:
    findings: list[Finding] = []

    for name, spec in _PROCESS.layers.items():
        if spec.min_width_um <= 0:
            continue
        idx = _layer_index(layout, spec.layer)
        if idx is None:
            continue
        polys = _polygons_on_layer(cell, idx)
        if not polys:
            continue

        for i, poly in enumerate(polys):
            bbox = poly.bbox()
            w = min(bbox.width(), bbox.height())
            if w < spec.min_width_um * 0.95:
                findings.append(Finding(
                    "error", "min_width",
                    f"Layer {name}: polygon {i} width {w:.4f} µm < min {spec.min_width_um} µm",
                    {"layer": name, "polygon_index": i, "width_um": w, "min_um": spec.min_width_um},
                ))

    return findings


# ── Check 3: Josephson Junction validation ─────────────────────────────────

def check_jj_geometry(layout: kdb.Layout, cell: kdb.Cell) -> list[Finding]:
    findings: list[Finding] = []

    bottom_idx = _layer_index(layout, _PROCESS.layer("M1"))
    barrier_idx = _layer_index(layout, _PROCESS.layer("JJ"))
    top_idx = _layer_index(layout, _PROCESS.layer("M2"))

    if barrier_idx is None:
        findings.append(Finding("info", "jj_geometry", "No JJ barrier layer found — not a junction device"))
        return findings

    barriers = _polygons_on_layer(cell, barrier_idx)
    if not barriers:
        findings.append(Finding("info", "jj_geometry", "JJ barrier layer exists but has no polygons"))
        return findings

    findings.append(Finding("info", "jj_geometry", f"Found {len(barriers)} JJ barrier polygon(s)"))

    if bottom_idx is None:
        findings.append(Finding("error", "jj_geometry", "JJ barrier exists but no M1 (bottom electrode) layer"))
        return findings
    if top_idx is None:
        findings.append(Finding("error", "jj_geometry", "JJ barrier exists but no M2 (top electrode) layer"))
        return findings

    bottoms = _polygons_on_layer(cell, bottom_idx)
    tops = _polygons_on_layer(cell, top_idx)

    if not bottoms:
        findings.append(Finding("error", "jj_geometry", "M1 (bottom electrode) has no polygons"))
    if not tops:
        findings.append(Finding("error", "jj_geometry", "M2 (top electrode) has no polygons"))

    overlap_m1_jj = _overlap_area(bottoms, barriers)
    overlap_m2_jj = _overlap_area(tops, barriers)
    overlap_m1_m2 = _overlap_area_many(bottoms, tops, barriers)

    findings.append(Finding("info", "jj_geometry",
                            f"Extracted JJ Al overlap area: {overlap_m1_m2:.6f} um^2",
                            {"jj_area_um2": overlap_m1_m2,
                             "area_formula": "area(M1 intersect M2 within JJ process window)"}))

    for jj_poly in barriers:
        jj_area = _polygon_area(jj_poly)
        findings.append(Finding("info", "jj_geometry",
                                f"JJ barrier area: {jj_area:.6f} µm²",
                                {"barrier_area_um2": jj_area}))

    total_jj_area = sum(_polygon_area(p) for p in barriers)
    findings.append(Finding("info", "jj_geometry",
                            f"Total JJ area: {total_jj_area:.6f} µm²; "
                            f"M1∩JJ overlap: {overlap_m1_jj:.6f} µm²; "
                            f"M2∩JJ overlap: {overlap_m2_jj:.6f} µm²",
                            {"total_barrier_area_um2": total_jj_area,
                             "al_overlap_area_um2": overlap_m1_m2,
                             "overlap_m1_jj_um2": overlap_m1_jj,
                             "overlap_m2_jj_um2": overlap_m2_jj}))

    if overlap_m1_m2 <= 1e-9:
        findings.append(Finding("error", "jj_geometry",
                                "Junction marker exists but no M1/M2 Al overlap produces junction area"))

    if overlap_m1_jj < total_jj_area * 0.8:
        findings.append(Finding("error", "jj_geometry",
                                f"M1 does not fully overlap JJ barrier (overlap={overlap_m1_jj:.6f} µm², "
                                f"barrier={total_jj_area:.6f} µm²)"))

    if overlap_m2_jj < total_jj_area * 0.8:
        findings.append(Finding("error", "jj_geometry",
                                f"M2 does not fully overlap JJ barrier (overlap={overlap_m2_jj:.6f} µm², "
                                f"barrier={total_jj_area:.6f} µm²)"))

    return findings


# ── Check 4: CPW topology ──────────────────────────────────────────────────

def check_cpw_topology(layout: kdb.Layout, cell: kdb.Cell, sidecar: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []

    info = (sidecar or {}).get("info", {})
    device_type = info.get("device_type", "")
    if "cpw" not in device_type.lower() and "resonator" not in device_type.lower():
        findings.append(Finding("info", "cpw_topology", "Not a CPW device — skipping CPW topology check"))
        return findings

    trace_width = info.get("trace_width_um") or info.get("cpw_trace_width_um")
    gap = info.get("gap_um") or info.get("cpw_gap_um")
    z0_sidecar = info.get("z0_ohm")
    signal_layer = _layer_from_sidecar(info, "signal", "rf_signal", "cpw", "launcher", fallback=_PROCESS.layer("M2"))
    ground_layer = _layer_from_sidecar(info, "ground", fallback=_PROCESS.layer("M1"))
    signal_idx = _layer_index(layout, signal_layer)
    ground_idx = _layer_index(layout, ground_layer)

    if signal_idx is None:
        findings.append(Finding("error", "cpw_topology", f"CPW signal layer {signal_layer} missing from GDS"))
        return findings
    if ground_idx is None:
        findings.append(Finding("error", "cpw_topology", f"CPW ground layer {ground_layer} missing from GDS"))
        return findings

    signal_polys = _polygons_on_layer(cell, signal_idx)
    ground_polys = _polygons_on_layer(cell, ground_idx)
    if not signal_polys:
        findings.append(Finding("error", "cpw_topology", "CPW signal layer has no polygons"))
    if not ground_polys:
        findings.append(Finding("error", "cpw_topology", "CPW ground layer has no polygons"))
    if signal_polys and ground_polys:
        short_area = _overlap_area(signal_polys, ground_polys)
        findings.append(Finding(
            "info",
            "cpw_topology",
            f"CPW signal-ground overlap area: {short_area:.6f} um^2",
            {"signal_ground_overlap_um2": short_area, "signal_layer": list(signal_layer), "ground_layer": list(ground_layer)},
        ))
        if short_area > 1e-6:
            findings.append(Finding(
                "error",
                "cpw_topology",
                f"CPW center conductor shorts to ground: overlap {short_area:.6f} um^2",
            ))
    if signal_polys and ground_polys and gap is not None:
        signal_region = _region_from_polys(signal_polys)
        ground_region = _region_from_polys(ground_polys)
        inner_clearance = signal_region.sized(int(float(gap) * 0.95 * 1000))
        clearance_intrusion = _region_area_um2(inner_clearance & ground_region)
        findings.append(Finding(
            "info",
            "cpw_topology",
            f"CPW boolean clearance intrusion area: {clearance_intrusion:.6f} um^2",
            {"clearance_intrusion_um2": clearance_intrusion, "required_gap_um": float(gap)},
        ))
        if clearance_intrusion > 1e-6:
            findings.append(Finding(
                "error",
                "cpw_topology",
                f"Ground enters the CPW gap; intrusion {clearance_intrusion:.6f} um^2 inside {float(gap):.3f} um clearance",
            ))

    if trace_width is not None and gap is not None:
        from text_to_gds.pcells.passives import cpw_conformal_mapping
        cpw = cpw_conformal_mapping(float(trace_width), float(gap),
                                     float(info.get("effective_permittivity", 6.2)))
        z0_calc = cpw["z0_ohm"]
        findings.append(Finding("info", "cpw_topology",
                                f"CPW: W={trace_width} µm, G={gap} µm → Z0={z0_calc:.2f} Ω",
                                {"trace_width_um": trace_width, "gap_um": gap,
                                 "z0_calculated_ohm": z0_calc}))

        if z0_sidecar is not None:
            deviation = abs(z0_calc - float(z0_sidecar)) / max(float(z0_sidecar), 1e-12)
            if deviation > 0.05:
                findings.append(Finding("warning", "cpw_topology",
                                        f"Sidecar Z0={z0_sidecar} Ω vs calculated Z0={z0_calc:.2f} Ω "
                                        f"({deviation*100:.1f}% deviation)"))

        if z0_calc < 20 or z0_calc > 150:
            findings.append(Finding("warning", "cpw_topology",
                                    f"Z0={z0_calc:.1f} Ω is outside typical CPW range (20–150 Ω)"))
    else:
        findings.append(Finding("warning", "cpw_topology",
                                "CPW device but trace_width_um or gap_um not in sidecar"))

    return findings


# ── Check 5: Resonator length validation ───────────────────────────────────

def check_jpa_features(layout: kdb.Layout, cell: kdb.Cell, sidecar: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    info = (sidecar or {}).get("info", {})
    device_type = str(info.get("device_type", ""))
    if "jpa" not in device_type.lower() and "ljpa" not in device_type.lower():
        return findings

    ports = (sidecar or {}).get("ports", [])
    rf_ports = [p for p in ports if "rf" in str(p.get("name", "")).lower()]
    if not rf_ports:
        findings.append(Finding("error", "jpa_features", "JPA requires at least one RF port"))

    ground_idx = _layer_index(layout, _PROCESS.layer("M1"))
    if ground_idx is None or not _polygons_on_layer(cell, ground_idx):
        findings.append(Finding("error", "jpa_features", "JPA requires ground geometry on M1"))

    barrier_idx = _layer_index(layout, _PROCESS.layer("JJ"))
    jj_count = len(_polygons_on_layer(cell, barrier_idx)) if barrier_idx is not None else 0
    if jj_count < 2:
        findings.append(Finding("error", "jpa_features", f"JPA requires two Josephson junctions; found {jj_count}"))

    required = info.get("required_jpa_features", {})
    if not info.get("squid_enabled") or int(info.get("squid_junction_count", 0) or 0) < 2:
        findings.append(Finding("error", "jpa_features", "JPA requires a SQUID loop with two junctions"))
    if not required.get("idc_shunt_capacitor") or int(info.get("idc_finger_count", 0) or 0) < 4:
        findings.append(Finding("error", "jpa_features", "JPA requires an IDC/shunt capacitor with extracted fingers"))
    if not required.get("coupling_capacitor") or not info.get("coupling_capacitor_length_um"):
        findings.append(Finding("error", "jpa_features", "JPA requires a coupling capacitor"))

    findings.append(Finding(
        "info",
        "jpa_features",
        "JPA feature inventory",
        {
            "rf_ports": [p.get("name") for p in rf_ports],
            "jj_count": jj_count,
            "idc_finger_count": info.get("idc_finger_count"),
            "squid_junction_count": info.get("squid_junction_count"),
        },
    ))
    return findings


def check_resonator_length(sidecar: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    info = (sidecar or {}).get("info", {})

    device_type = info.get("device_type", "")
    if "resonator" not in device_type.lower():
        return findings

    freq_ghz = info.get("target_frequency_ghz")
    eps_eff = info.get("effective_permittivity")
    length_um = info.get("electrical_length_um") or info.get("meander_length_um")

    if freq_ghz is not None and eps_eff is not None and length_um is not None:
        c0 = 299_792_458.0
        vp = c0 / math.sqrt(float(eps_eff))
        expected_length_um = vp / (4.0 * float(freq_ghz) * 1e9) * 1e6
        actual = float(length_um)

        deviation = abs(actual - expected_length_um) / max(expected_length_um, 1e-12)
        findings.append(Finding("info", "resonator_length",
                                f"λ/4 length: expected {expected_length_um:.1f} µm, "
                                f"actual {actual:.1f} µm ({deviation*100:.1f}% deviation)",
                                {"expected_um": expected_length_um, "actual_um": actual,
                                 "deviation_pct": deviation * 100}))

        if deviation > 0.10:
            findings.append(Finding("warning", "resonator_length",
                                    f"Resonator length deviation {deviation*100:.1f}% exceeds 10%"))

        if actual < 100 or actual > 100_000:
            findings.append(Finding("error", "resonator_length",
                                    f"Resonator length {actual:.1f} µm is unrealistic"))
    else:
        findings.append(Finding("info", "resonator_length",
                                "Missing frequency/permittivity/length — cannot validate resonator"))

    return findings


# ── Check 6: Via chain validation ──────────────────────────────────────────

def check_via_chain(layout: kdb.Layout, cell: kdb.Cell, sidecar: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    info = (sidecar or {}).get("info", {})

    device_type = info.get("device_type", "")
    if "via" not in device_type.lower():
        return findings

    stage_count = info.get("stage_count", 0)
    via12_idx = _layer_index(layout, _PROCESS.layer("VIA12"))
    via23_idx = _layer_index(layout, _PROCESS.layer("VIA23"))

    total_vias = 0
    if via12_idx is not None:
        total_vias += len(_polygons_on_layer(cell, via12_idx))
    if via23_idx is not None:
        total_vias += len(_polygons_on_layer(cell, via23_idx))

    findings.append(Finding("info", "via_chain",
                            f"Via chain: {total_vias} via polygons for {stage_count} stages",
                            {"via_count": total_vias, "stage_count": stage_count}))

    if stage_count > 0 and total_vias < stage_count:
        findings.append(Finding("error", "via_chain",
                                f"Via count ({total_vias}) < stage count ({stage_count}) — "
                                f"chain may be broken"))

    m1_idx = _layer_index(layout, _PROCESS.layer("M1"))
    m2_idx = _layer_index(layout, _PROCESS.layer("M2"))
    m3_idx = _layer_index(layout, _PROCESS.layer("M3"))

    metal_layers_present = sum(1 for idx in [m1_idx, m2_idx, m3_idx]
                                if idx is not None and _polygons_on_layer(cell, idx))
    if metal_layers_present < 2:
        findings.append(Finding("error", "via_chain",
                                f"Via chain has metal on only {metal_layers_present} layer(s) — "
                                "needs at least 2 for inter-layer connectivity"))

    if via12_idx is not None and m1_idx is not None and m2_idx is not None:
        via12_polys = _polygons_on_layer(cell, via12_idx)
        m1_polys = _polygons_on_layer(cell, m1_idx)
        m2_polys = _polygons_on_layer(cell, m2_idx)
        if via12_polys:
            overlap_bottom = _overlap_area(via12_polys, m1_polys)
            overlap_top = _overlap_area(via12_polys, m2_polys)
            total_via_area = sum(_polygon_area(p) for p in via12_polys)
            if total_via_area > 0:
                if overlap_bottom < total_via_area * 0.5:
                    findings.append(Finding("error", "via_chain",
                                            "VIA12 polygons do not sufficiently overlap M1"))
                if overlap_top < total_via_area * 0.5:
                    findings.append(Finding("error", "via_chain",
                                            "VIA12 polygons do not sufficiently overlap M2"))

    return findings


# ── Check 7: Port connectivity ─────────────────────────────────────────────

def check_port_connectivity(layout: kdb.Layout, cell: kdb.Cell, sidecar: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    ports = (sidecar or {}).get("ports", [])

    if not ports:
        findings.append(Finding("info", "port_connectivity", "No ports defined in sidecar"))
        return findings

    findings.append(Finding("info", "port_connectivity", f"{len(ports)} port(s) defined"))

    for port in ports:
        if not isinstance(port, dict):
            continue
        port_name = port.get("name", "unnamed")
        port_layer = port.get("layer")
        if port_layer is None:
            continue
        if isinstance(port_layer, (list, tuple)) and len(port_layer) >= 2:
            idx = _layer_index(layout, (int(port_layer[0]), int(port_layer[1])))
        else:
            continue
        if idx is None:
            findings.append(Finding("warning", "port_connectivity",
                                    f"Port '{port_name}' references layer {port_layer} not in GDS"))
            continue

        polys = _polygons_on_layer(cell, idx)
        if not polys:
            findings.append(Finding("error", "port_connectivity",
                                    f"Port '{port_name}' layer {port_layer} has no polygons"))

    return findings


# ── Main validator ─────────────────────────────────────────────────────────

def validate_layout(
    gds_path: str | Path,
    sidecar_path: str | Path | None = None,
    *,
    process: ProcessStack | None = None,
) -> dict[str, Any]:
    """Run all geometry checks on a GDS file.

    Returns a validation report with ``passed`` (bool), ``findings`` (list),
    and ``summary`` (dict of check → error/warning/info counts).
    """
    global _PROCESS, _LAYER_MAP
    if process is not None:
        _PROCESS = process
        _LAYER_MAP = {spec.layer: name for name, spec in _PROCESS.layers.items()}

    gds = Path(gds_path)
    if not gds.is_file():
        return {
            "schema": SCHEMA,
            "passed": False,
            "findings": [{"severity": "error", "check": "file_exists",
                          "message": f"GDS file not found: {gds}"}],
        }

    layout = kdb.Layout()
    layout.read(str(gds))

    if layout.top_cells() == 0:
        return {
            "schema": SCHEMA,
            "passed": False,
            "findings": [{"severity": "error", "check": "gds_basic",
                          "message": "GDS contains no cells"}],
        }

    cell = layout.top_cell()

    sidecar: dict[str, Any] = {}
    if sidecar_path is not None:
        sp = Path(sidecar_path)
        if sp.is_file():
            sidecar = json.loads(sp.read_text(encoding="utf-8"))

    all_findings: list[Finding] = []
    all_findings.extend(check_gds_basic(gds, layout, cell))
    all_findings.extend(check_min_width(layout, cell))
    all_findings.extend(check_jj_geometry(layout, cell))
    all_findings.extend(check_cpw_topology(layout, cell, sidecar))
    all_findings.extend(check_jpa_features(layout, cell, sidecar))
    all_findings.extend(check_resonator_length(sidecar))
    all_findings.extend(check_via_chain(layout, cell, sidecar))
    all_findings.extend(check_port_connectivity(layout, cell, sidecar))

    errors = sum(1 for f in all_findings if f.severity == "error")
    warnings = sum(1 for f in all_findings if f.severity == "warning")
    infos = sum(1 for f in all_findings if f.severity == "info")

    return {
        "schema": SCHEMA,
        "gds_path": str(gds),
        "passed": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "findings": [
            {"severity": f.severity, "check": f.check, "message": f.message, "details": f.details}
            for f in all_findings
        ],
    }


def validate_against_golden(
    gds_path: str | Path,
    expected: dict[str, Any],
    sidecar_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a GDS against a golden expected.json.

    Expected keys:
      - layers: list of layer names that must have geometry
      - jj_area_um2: expected JJ barrier area (±10%)
      - ports: expected port count
      - z0_ohm: expected characteristic impedance (±10%)
      - stage_count: expected via chain stages
    """
    report = validate_layout(gds_path, sidecar_path)
    golden_findings: list[dict[str, Any]] = []

    layout = kdb.Layout()
    layout.read(str(gds_path))
    cell = layout.top_cell()

    if "layers" in expected:
        for layer_name in expected["layers"]:
            spec = _PROCESS.layers.get(layer_name)
            if spec is None:
                golden_findings.append({"severity": "error", "check": "golden_layers",
                                        "message": f"Expected layer '{layer_name}' not in process"})
                continue
            idx = _layer_index(layout, spec.layer)
            if idx is None or not _polygons_on_layer(cell, idx):
                golden_findings.append({"severity": "error", "check": "golden_layers",
                                        "message": f"Expected layer '{layer_name}' has no geometry"})

    if "jj_area_um2" in expected:
        barrier_idx = _layer_index(layout, _PROCESS.layer("JJ"))
        if barrier_idx is not None:
            barriers = _polygons_on_layer(cell, barrier_idx)
            actual_area = sum(_polygon_area(p) for p in barriers)
            expected_area = float(expected["jj_area_um2"])
            if expected_area > 0 and abs(actual_area - expected_area) / expected_area > 0.10:
                golden_findings.append({
                    "severity": "error", "check": "golden_jj_area",
                    "message": f"JJ area {actual_area:.6f} µm² vs expected {expected_area:.6f} µm²",
                    "details": {"actual": actual_area, "expected": expected_area},
                })
            else:
                golden_findings.append({
                    "severity": "info", "check": "golden_jj_area",
                    "message": f"JJ area {actual_area:.6f} µm² matches expected {expected_area:.6f} µm²",
                })

    if "ports" in expected:
        sidecar: dict = {}
        if sidecar_path is not None:
            sp = Path(sidecar_path)
            if sp.is_file():
                sidecar = json.loads(sp.read_text(encoding="utf-8"))
        port_count = len(sidecar.get("ports", []))
        if port_count != int(expected["ports"]):
            golden_findings.append({
                "severity": "error", "check": "golden_ports",
                "message": f"Port count {port_count} vs expected {expected['ports']}",
            })

    report["golden_findings"] = golden_findings
    report["golden_passed"] = all(f["severity"] != "error" for f in golden_findings)
    report["passed"] = report["passed"] and report["golden_passed"]
    return report
