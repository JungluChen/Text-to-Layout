"""Geometry, connectivity, and boundary truth audit for the Palace resonator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import klayout.db as kdb
from pydantic import BaseModel, ConfigDict, Field

from textlayout.fem import FEMModel
from textlayout.models import Geometry, Polygon, Technology
from textlayout.schemas.dsl import QuarterWaveResonatorSpec
from textlayout.solvers.palace.models import PalaceOutputError


class ConnectivityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    detail: str


class HypothesisDisposition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    hypothesis: str
    disposition: Literal["NOT_SUPPORTED", "SUPPORTED", "UNRESOLVED"]
    evidence: list[str]


class QuarterWaveModelAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-quarter-wave-model-audit.v1"
    status: Literal["PASS", "FAIL"]
    resonator_centerline_um: list[tuple[float, float]]
    physical_open_end_um: tuple[float, float]
    physical_grounded_end_um: tuple[float, float]
    ground_connection_bbox_um: tuple[float, float, float, float]
    coupling_capacitor_geometry: dict[str, Any]
    conductor_attributes: list[int]
    substrate_attributes: list[int]
    vacuum_attributes: list[int]
    pec_boundary_attributes: list[int]
    radiation_or_impedance_boundary_attributes: list[int]
    material_tensor_mapping: dict[int, dict[str, Any]]
    critical_regions: list[dict[str, Any]]
    expected_electrical_connectivity: list[str]
    resonator_effective_physical_length_um: float = Field(gt=0.0)
    klayout_connectivity_checks: list[ConnectivityCheck]
    gds_cross_check: dict[str, Any]
    mesh_physical_groups: dict[str, dict[str, int]]
    mesh_physical_group_cross_check: dict[str, Any]
    palace_boundary_cross_check: dict[str, Any]
    hypotheses: list[HypothesisDisposition]
    visual_diagnostics: list[str]
    blockers: list[str]
    limitations: list[str]


def _region(polygon: Polygon, *, scale: int = 1000) -> kdb.Region:
    points = [kdb.Point(round(x * scale), round(y * scale)) for x, y in polygon.points]
    return kdb.Region(kdb.Polygon(points))


def _roles(geometry: Geometry) -> dict[str, kdb.Region]:
    raw = geometry.metadata.get("polygon_roles")
    if not isinstance(raw, list) or len(raw) != len(geometry.polygons):
        raise PalaceOutputError(
            "quarter-wave polygon roles are missing or do not cover every polygon"
        )
    roles = [str(item) for item in raw]
    if len(set(roles)) != len(roles):
        raise PalaceOutputError("quarter-wave polygon roles are not unique")
    return {role: _region(polygon) for role, polygon in zip(roles, geometry.polygons, strict=True)}


def _point(metadata: object, *, name: str) -> tuple[float, float]:
    if not isinstance(metadata, (list, tuple)) or len(metadata) != 2:
        raise PalaceOutputError(f"{name} is missing or invalid")
    point = (float(metadata[0]), float(metadata[1]))
    if not all(value == value and abs(value) != float("inf") for value in point):
        raise PalaceOutputError(f"{name} must contain finite coordinates")
    return point


def _box(metadata: object, *, name: str) -> tuple[float, float, float, float]:
    if not isinstance(metadata, (list, tuple)) or len(metadata) != 4:
        raise PalaceOutputError(f"{name} is missing or invalid")
    box = (
        float(metadata[0]),
        float(metadata[1]),
        float(metadata[2]),
        float(metadata[3]),
    )
    if box[0] >= box[2] or box[1] >= box[3]:
        raise PalaceOutputError(f"{name} has non-positive area")
    return box


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gds_cross_check(
    geometry: Geometry,
    technology: Technology,
    gds_path: Path | None,
) -> dict[str, Any]:
    if gds_path is None:
        return {"executed": False, "reason": "no GDS path supplied"}
    if not gds_path.is_file():
        raise PalaceOutputError(f"GDS cross-check input is missing: {gds_path}")
    layout = kdb.Layout()
    layout.read(str(gds_path))
    cell = layout.top_cell()
    if cell is None:
        raise PalaceOutputError("GDS cross-check found no top cell")
    layer = technology.layer(str(geometry.metadata["metal"]))
    layer_index = layout.find_layer(layer.gds_layer, layer.gds_datatype)
    if layer_index is None:
        raise PalaceOutputError("GDS cross-check found no resonator conductor layer")
    imported = kdb.Region(cell.begin_shapes_rec(layer_index)).merged()
    expected = kdb.Region()
    for polygon in geometry.polygons:
        expected += _region(polygon)
    expected.merge()
    expected_area_um2 = expected.area() / 1_000_000.0
    imported_area_um2 = imported.area() * layout.dbu * layout.dbu
    area_error = abs(imported_area_um2 - expected_area_um2)
    return {
        "executed": True,
        "backend": "KLayout",
        "gds_path": str(gds_path).replace("\\", "/"),
        "gds_sha256": _sha256(gds_path),
        "expected_area_um2": expected_area_um2,
        "imported_area_um2": imported_area_um2,
        "area_difference_um2": area_error,
        "passed": area_error <= 1e-6,
    }


def _mesh_physical_groups(mesh_path: Path | None) -> dict[str, dict[str, int]]:
    if mesh_path is None:
        return {}
    text = mesh_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    try:
        start = lines.index("$PhysicalNames")
        count = int(lines[start + 1])
    except (ValueError, IndexError) as exc:
        raise PalaceOutputError(f"{mesh_path}: no valid Gmsh PhysicalNames section") from exc
    groups: dict[str, dict[str, int]] = {}
    for line in lines[start + 2 : start + 2 + count]:
        dimension, attribute, quoted_name = line.split(maxsplit=2)
        groups[quoted_name.strip('"')] = {
            "dimension": int(dimension),
            "attribute": int(attribute),
        }
    return dict(sorted(groups.items()))


def _palace_boundary_check(
    model: FEMModel, resolved_config_path: Path | None
) -> dict[str, Any]:
    if resolved_config_path is None:
        return {"executed": False, "reason": "no resolved Palace config supplied"}
    config = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    boundaries = config.get("Boundaries", {})
    pec = sorted(int(value) for value in boundaries.get("PEC", {}).get("Attributes", []))
    interfaces = sorted(interface.attribute for interface in model.interfaces)
    expected_pec = sorted(
        [surface.attribute for surface in model.surfaces if surface.kind == "pec"]
        + [port.attribute for port in model.wave_ports]
        + [port.attribute for port in model.lumped_ports]
    )
    interface_pec_overlap = sorted(set(interfaces) & set(pec))
    return {
        "executed": True,
        "resolved_config_path": str(resolved_config_path).replace("\\", "/"),
        "pec_attributes": pec,
        "expected_inactive_eigenmode_pec_attributes": expected_pec,
        "interface_attributes": interfaces,
        "interface_attributes_in_pec": interface_pec_overlap,
        "passed": pec == expected_pec and not interface_pec_overlap,
    }


def audit_quarter_wave_model(
    geometry: Geometry,
    params: QuarterWaveResonatorSpec,
    model: FEMModel,
    technology: Technology,
    *,
    gds_path: Path | None = None,
    mesh_path: Path | None = None,
    resolved_config_path: Path | None = None,
    visual_diagnostics: list[str] | None = None,
    scientific_context: dict[str, float | int] | None = None,
) -> QuarterWaveModelAudit:
    """Cross-check generator metadata, KLayout connectivity, mesh tags, and Palace BCs."""
    roles = _roles(geometry)
    centerline_raw = geometry.metadata.get("resonator_centerline_um")
    if not isinstance(centerline_raw, list) or len(centerline_raw) != 2:
        raise PalaceOutputError("resonator centreline metadata is missing")
    centerline = [_point(point, name="resonator centreline point") for point in centerline_raw]
    grounded = _point(
        geometry.metadata.get("physical_grounded_end_um"), name="physical grounded end"
    )
    open_end = _point(geometry.metadata.get("physical_open_end_um"), name="physical open end")
    if centerline[0] != grounded or centerline[1] != open_end:
        raise PalaceOutputError("centreline endpoint order disagrees with physical endpoint metadata")
    length = ((open_end[0] - grounded[0]) ** 2 + (open_end[1] - grounded[1]) ** 2) ** 0.5
    if abs(length - params.length_um) > 1e-9:
        raise PalaceOutputError("resonator centreline length disagrees with layout parameters")
    ground_box = _box(
        geometry.metadata.get("ground_connection_bbox_um"), name="ground connection bbox"
    )
    coupling_box = _box(
        geometry.metadata.get("coupling_gap_bbox_um"), name="coupling gap bbox"
    )

    signal = roles["resonator_signal"]
    ground_left = roles["resonator_ground_left"]
    ground_right = roles["resonator_ground_right"]
    short = roles["grounded_end_bridge"]
    coupler = roles["feedline_signal"]
    direct_ground = (ground_left + ground_right).merged()
    intended_grounded = (signal + short + direct_ground).merged().count() == 1
    signal_without_short_isolated = (signal + direct_ground).merged().count() == 3
    coupler_isolated = (coupler & (signal + short + direct_ground)).is_empty()
    signal_continuous = signal.merged().count() == 1
    gap_matches = abs((coupling_box[3] - coupling_box[1]) - params.coupling_gap_um) <= 1e-9
    checks = [
        ConnectivityCheck(
            name="grounded_end_connected_to_ground",
            passed=intended_grounded,
            detail="KLayout merges resonator signal, explicit short bridge, and both ground rails",
        ),
        ConnectivityCheck(
            name="open_end_electrically_unshorted",
            passed=signal_without_short_isolated and gap_matches,
            detail="signal is isolated from ground without the declared short and retains the coupling gap",
        ),
        ConnectivityCheck(
            name="coupling_electrode_isolated",
            passed=coupler_isolated,
            detail="KLayout intersection of feedline signal with resonator/ground group is empty",
        ),
        ConnectivityCheck(
            name="signal_conductor_continuous",
            passed=signal_continuous,
            detail="resonator signal is one merged KLayout region",
        ),
        ConnectivityCheck(
            name="no_accidental_signal_ground_bridge",
            passed=signal_without_short_isolated and intended_grounded,
            detail="ground connection appears only after the explicit grounded-end bridge is included",
        ),
    ]
    gds = _gds_cross_check(geometry, technology, gds_path)
    groups = _mesh_physical_groups(mesh_path)
    expected_groups = {
        **{
            volume.name: {"dimension": 3, "attribute": volume.attribute}
            for volume in model.volumes
        },
        **{
            surface.name: {"dimension": 2, "attribute": surface.attribute}
            for surface in model.surfaces
        },
        **{
            interface.name: {"dimension": 2, "attribute": interface.attribute}
            for interface in model.interfaces
        },
        **{
            port.name: {"dimension": 2, "attribute": port.attribute}
            for port in model.wave_ports
        },
        **{
            port.name: {"dimension": 2, "attribute": port.attribute}
            for port in model.lumped_ports
        },
    }
    mesh_groups_passed = not groups or groups == dict(sorted(expected_groups.items()))
    mesh_group_check = {
        "executed": mesh_path is not None,
        "expected": dict(sorted(expected_groups.items())),
        "observed": groups,
        "passed": mesh_groups_passed,
    }
    boundary = _palace_boundary_check(model, resolved_config_path)
    connectivity_passed = all(check.passed for check in checks)
    auxiliary_passed = (
        bool(gds.get("passed", True))
        and mesh_groups_passed
        and bool(boundary.get("passed", True))
    )
    blockers = [check.name for check in checks if not check.passed]
    if gds.get("passed") is False:
        blockers.append("GDS geometry disagrees with Geometry IR")
    if boundary.get("passed") is False:
        blockers.append("resolved Palace boundaries disagree with FEMModel")
    if not mesh_groups_passed:
        blockers.append("Gmsh physical groups disagree with FEMModel")
    context = scientific_context or {}
    mode_count = int(context.get("mode_count", 0))
    frequency_change = context.get("frequency_change_percent")
    zz_indicator = context.get("global_error_indicator_percent")
    localization = context.get("resonator_localization")
    mesh_evidence = [
        message
        for value, message in (
            (zz_indicator, f"final ZZ indicator {zz_indicator} percent"),
            (frequency_change, f"finest frequency change {frequency_change} percent"),
        )
        if value is not None
    ]
    hypotheses = [
        HypothesisDisposition(code="A", hypothesis="wrong selected eigenmode", disposition="UNRESOLVED", evidence=["diagnostic multimode catalog not yet executed"]),
        HypothesisDisposition(code="B", hypothesis="wrong endpoint orientation", disposition="NOT_SUPPORTED", evidence=["typed endpoint metadata agrees with centreline and KLayout geometry"]),
        HypothesisDisposition(code="C", hypothesis="incorrect boundary assignment", disposition=("NOT_SUPPORTED" if boundary.get("passed") else "SUPPORTED"), evidence=["resolved Palace PEC attributes cross-checked against FEMModel"]),
        HypothesisDisposition(code="D", hypothesis="incorrect geometry or conductor connectivity", disposition=("NOT_SUPPORTED" if connectivity_passed and gds.get("passed", True) else "SUPPORTED"), evidence=["KLayout region connectivity and GDS readback"]),
        HypothesisDisposition(code="E", hypothesis="incorrect field sampling", disposition="NOT_SUPPORTED", evidence=["manufactured evaluator is endpoint-, phase-, amplitude-, and ordering-invariant"]),
        HypothesisDisposition(code="F", hypothesis="insufficient modal search range", disposition="UNRESOLVED", evidence=[f"bounded release retained {mode_count} modes" if mode_count else "mode count was not supplied"]),
        HypothesisDisposition(code="G", hypothesis="insufficient mesh resolution", disposition=("SUPPORTED" if mesh_evidence else "UNRESOLVED"), evidence=mesh_evidence or ["mesh-convergence context was not supplied"]),
        HypothesisDisposition(code="H", hypothesis="package or substrate mode contamination", disposition="UNRESOLVED", evidence=([f"selected-mode resonator localization is {localization}"] if localization is not None else []) + ["mode classification not yet executed"]),
    ]
    material_by_name = {material.name: material for material in model.materials}
    material_mapping = {
        volume.attribute: {
            "volume": volume.name,
            "material": volume.material,
            "permittivity": material_by_name[volume.material].permittivity,
            "permeability": material_by_name[volume.material].permeability,
        }
        for volume in model.volumes
    }
    return QuarterWaveModelAudit(
        status=("PASS" if connectivity_passed and auxiliary_passed else "FAIL"),
        resonator_centerline_um=centerline,
        physical_open_end_um=open_end,
        physical_grounded_end_um=grounded,
        ground_connection_bbox_um=ground_box,
        coupling_capacitor_geometry={
            "gap_bbox_um": coupling_box,
            "gap_um": params.coupling_gap_um,
            "feedline_signal_role": "feedline_signal",
            "resonator_signal_role": "resonator_signal",
        },
        conductor_attributes=sorted(
            surface.attribute for surface in model.surfaces if surface.role == "superconducting_metal"
        ),
        substrate_attributes=sorted(volume.attribute for volume in model.volumes if volume.role == "substrate"),
        vacuum_attributes=sorted(volume.attribute for volume in model.volumes if volume.role == "vacuum"),
        pec_boundary_attributes=sorted(surface.attribute for surface in model.surfaces if surface.kind == "pec"),
        radiation_or_impedance_boundary_attributes=sorted(surface.attribute for surface in model.surfaces if surface.kind in {"absorbing", "impedance"}),
        material_tensor_mapping=material_mapping,
        critical_regions=[region.model_dump(mode="json") for region in model.critical_regions],
        expected_electrical_connectivity=[check.name for check in checks],
        resonator_effective_physical_length_um=length,
        klayout_connectivity_checks=checks,
        gds_cross_check=gds,
        mesh_physical_groups=groups,
        mesh_physical_group_cross_check=mesh_group_check,
        palace_boundary_cross_check=boundary,
        hypotheses=hypotheses,
        visual_diagnostics=visual_diagnostics or [],
        blockers=blockers,
        limitations=[
            "critical-region records currently use broad volume compatibility attributes; "
            "localized surface and near-field mapping remains required before EPR"
        ],
    )


def render_quarter_wave_audit_svg(
    geometry: Geometry,
    audit: QuarterWaveModelAudit,
    *,
    sampling_stations: int = 20,
) -> str:
    """Render deterministic endpoint, centreline, boundary, and sampling overlays."""
    if sampling_stations < 2:
        raise ValueError("at least two sampling stations are required")
    box = geometry.bbox()
    margin = max(box.width, 80.0)
    view_x = box.xmin - margin
    view_y = box.ymin - 40.0
    view_width = box.width + 2.0 * margin
    view_height = box.height + 80.0
    flip = 2.0 * view_y + view_height
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_x:g} {view_y:g} {view_width:g} {view_height:g}">',
        f'<rect x="{view_x:g}" y="{view_y:g}" width="{view_width:g}" height="{view_height:g}" fill="white"/>',
    ]
    for polygon in geometry.polygons:
        points = " ".join(f"{x:g},{flip - y:g}" for x, y in polygon.points)
        parts.append(f'<polygon points="{points}" fill="#6b7280" fill-opacity="0.45" stroke="#111827" stroke-width="1"/>')
    (gx, gy), (ox, oy) = audit.physical_grounded_end_um, audit.physical_open_end_um
    parts.append(f'<line x1="{gx:g}" y1="{flip - gy:g}" x2="{ox:g}" y2="{flip - oy:g}" stroke="#2563eb" stroke-width="3"/>')
    for index in range(sampling_stations):
        fraction = (index + 0.5) / sampling_stations
        x = gx + fraction * (ox - gx)
        y = gy + fraction * (oy - gy)
        parts.append(f'<circle cx="{x:g}" cy="{flip - y:g}" r="3" fill="#0ea5e9"/>')
    for x, y, color, label in ((gx, gy, "#16a34a", "GROUNDED"), (ox, oy, "#dc2626", "OPEN")):
        parts.append(f'<circle cx="{x:g}" cy="{flip - y:g}" r="10" fill="{color}"/>')
        parts.append(f'<text x="{x + 15:g}" y="{flip - y:g}" font-size="24" fill="{color}">{label}</text>')
    parts.append(f'<rect x="{box.xmin:g}" y="{flip - box.ymax:g}" width="{box.width:g}" height="{box.height:g}" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="10 8"/>')
    legend_x = box.xmax + 20.0
    legend_y = flip - box.ymax + 30.0
    labels = [
        "PEC: " + ",".join(str(value) for value in audit.pec_boundary_attributes),
        "SUBSTRATE: " + ",".join(str(value) for value in audit.substrate_attributes),
        "VACUUM: " + ",".join(str(value) for value in audit.vacuum_attributes),
        "CRITICAL: CPW gaps, coupling gap, endpoints, interface",
    ]
    for index, label in enumerate(labels):
        parts.append(f'<text x="{legend_x:g}" y="{legend_y + index * 30:g}" font-size="20" fill="#111827">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)
