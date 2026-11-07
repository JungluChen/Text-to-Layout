"""Headless Gmsh pipeline: 2-D layout geometry + substrate stack -> Palace ``.msh``.

The pipeline is generic (any :class:`~textlayout.models.Geometry`), unlike
:mod:`textlayout.fem.gmsh_physical`, which is tuned to the quarter-wave
benchmark. Metal polygons become infinitely thin PEC surfaces on the
substrate/vacuum interface; the substrate and vacuum are conformally fragmented
boxes. Physical attribute ids are fixed so a Palace configuration can be
written from the manifest without inspecting the mesh:

===========  ===  =======================================================
substrate      1  3-D volume, dielectric with ``SubstrateStack.epsilon_r``
vacuum         2  3-D volume above the chip
metal         10  2-D PEC surfaces projected from ``Geometry.polygons``
enclosure     11  2-D PEC outer box (walls, lid, back-side ground)
interface     20  2-D non-metal substrate/vacuum interface (energy probe)
===========  ===  =======================================================

``gmsh`` is imported lazily. If it is absent the pipeline writes a ``.geo``
script (so a user with Gmsh elsewhere can mesh it) and reports
``SKIPPED_SOLVER_ABSENT``; it never fabricates a mesh.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.models import Geometry

MESH_MANIFEST_SCHEMA = "textlayout.gmsh-mesh-manifest.v1"

MeshStatus = Literal["MESH_GENERATED", "SKIPPED_SOLVER_ABSENT", "FAILED"]

SUBSTRATE_ATTRIBUTE = 1
VACUUM_ATTRIBUTE = 2
METAL_ATTRIBUTE = 10
ENCLOSURE_ATTRIBUTE = 11
INTERFACE_ATTRIBUTE = 20


class SubstrateStack(BaseModel):
    """Vertical stack metadata consumed by the mesher (all lengths in µm)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate_material: str = Field(default="silicon")
    epsilon_r: float = Field(default=11.45, gt=1.0)
    loss_tangent: float = Field(default=0.0, ge=0.0)
    substrate_thickness_um: float = Field(default=500.0, gt=0)
    vacuum_height_um: float = Field(default=500.0, gt=0)
    lateral_margin_um: float = Field(default=100.0, ge=0)
    metal_layers: tuple[str, ...] = Field(
        default=(), description="Layer names treated as superconducting metal; empty = all."
    )

    @model_validator(mode="after")
    def _sane_aspect(self) -> SubstrateStack:
        if self.vacuum_height_um < 0.1 * self.substrate_thickness_um:
            raise ValueError("vacuum_height_um should be at least 10% of substrate thickness")
        return self


class MeshControls(BaseModel):
    """Deterministic element-size controls (µm)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    characteristic_length_um: float = Field(default=50.0, gt=0)
    metal_edge_length_um: float = Field(default=4.0, gt=0)
    metal_edge_distance_um: float = Field(default=40.0, gt=0)
    element_order: int = Field(default=1, ge=1, le=2)
    msh_version: float = Field(default=2.2)

    @model_validator(mode="after")
    def _ordered(self) -> MeshControls:
        if self.metal_edge_length_um > self.characteristic_length_um:
            raise ValueError("metal_edge_length_um must not exceed characteristic_length_um")
        return self

    def refined(self, factor: float) -> MeshControls:
        if factor <= 0:
            raise ValueError("refinement factor must be positive")
        return self.model_copy(
            update={
                "characteristic_length_um": self.characteristic_length_um / factor,
                "metal_edge_length_um": self.metal_edge_length_um / factor,
            }
        )


class MeshManifest(BaseModel):
    """Everything a solver backend needs to reference the mesh honestly."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: str = Field(default=MESH_MANIFEST_SCHEMA, alias="schema")
    status: MeshStatus
    mesh_path: Path | None = None
    geo_path: Path | None = None
    mesh_sha256: str | None = None
    gmsh_version: str | None = None
    reason: str | None = None
    runtime_seconds: float = Field(default=0.0, ge=0.0)
    element_count: int | None = Field(default=None, ge=0)
    node_count: int | None = Field(default=None, ge=0)
    minimum_quality: float | None = None
    mean_quality: float | None = None
    length_unit_m: float = 1e-6
    stack: SubstrateStack
    controls: MeshControls
    attributes: dict[str, int] = Field(
        default_factory=lambda: {
            "substrate": SUBSTRATE_ATTRIBUTE,
            "vacuum": VACUUM_ATTRIBUTE,
            "metal": METAL_ATTRIBUTE,
            "enclosure": ENCLOSURE_ATTRIBUTE,
            "interface": INTERFACE_ATTRIBUTE,
        }
    )
    metal_polygon_count: int = 0
    domain_bbox_um: dict[str, float] = Field(default_factory=dict)

    @property
    def mesh_available(self) -> bool:
        return self.status == "MESH_GENERATED" and self.mesh_path is not None


def gmsh_available() -> bool:
    """True when the ``gmsh`` Python SDK can be located (not imported)."""
    import importlib.util

    try:
        return importlib.util.find_spec("gmsh") is not None
    except (ImportError, ValueError):
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metal_polygons(
    geometry: Geometry, stack: SubstrateStack
) -> list[tuple[str, tuple[tuple[float, float], ...]]]:
    selected: list[tuple[str, tuple[tuple[float, float], ...]]] = []
    for polygon in geometry.polygons:
        if stack.metal_layers and polygon.layer not in stack.metal_layers:
            continue
        selected.append((polygon.layer, polygon.points))
    return selected


def _domain_bbox(geometry: Geometry, stack: SubstrateStack) -> dict[str, float]:
    bbox = geometry.bbox()
    m = stack.lateral_margin_um
    return {
        "xmin": bbox.xmin - m,
        "xmax": bbox.xmax + m,
        "ymin": bbox.ymin - m,
        "ymax": bbox.ymax + m,
        "zmin": -stack.substrate_thickness_um,
        "zmax": stack.vacuum_height_um,
    }


def write_geo_script(
    geometry: Geometry, stack: SubstrateStack, controls: MeshControls, path: Path
) -> Path:
    """Write an OpenCASCADE ``.geo`` reproducing the pipeline for external Gmsh."""
    box = _domain_bbox(geometry, stack)
    lines = [
        "// Generated by textlayout.mesh.gmsh_pipeline (lengths in micrometres)",
        'SetFactory("OpenCASCADE");',
        f"Mesh.CharacteristicLengthMax = {controls.characteristic_length_um};",
        f"Mesh.MshFileVersion = {controls.msh_version};",
        f"Mesh.ElementOrder = {controls.element_order};",
        "Mesh.RandomFactor = 0;",
        f"sub = newv; Box(sub) = {{{box['xmin']}, {box['ymin']}, {box['zmin']}, "
        f"{box['xmax'] - box['xmin']}, {box['ymax'] - box['ymin']}, {stack.substrate_thickness_um}}};",
        f"vac = newv; Box(vac) = {{{box['xmin']}, {box['ymin']}, 0, "
        f"{box['xmax'] - box['xmin']}, {box['ymax'] - box['ymin']}, {stack.vacuum_height_um}}};",
    ]
    metal_ids: list[str] = []
    for index, (_layer, points) in enumerate(_metal_polygons(geometry, stack)):
        point_ids: list[str] = []
        for x, y in points:
            pid = f"p{index}_{len(point_ids)}"
            lines.append(
                f"{pid} = newp; Point({pid}) = {{{x}, {y}, 0, {controls.metal_edge_length_um}}};"
            )
            point_ids.append(pid)
        line_ids: list[str] = []
        for i, pid in enumerate(point_ids):
            lid = f"l{index}_{i}"
            lines.append(
                f"{lid} = newl; Line({lid}) = {{{pid}, {point_ids[(i + 1) % len(point_ids)]}}};"
            )
            line_ids.append(lid)
        lines.append(f"cl{index} = newll; Curve Loop(cl{index}) = {{{', '.join(line_ids)}}};")
        lines.append(f"s{index} = news; Plane Surface(s{index}) = {{cl{index}}};")
        metal_ids.append(f"s{index}")
    if metal_ids:
        lines.append(
            f"BooleanFragments{{ Volume{{sub, vac}}; Delete; }}{{ Surface{{{', '.join(metal_ids)}}}; Delete; }}"
        )
        lines.append(f'Physical Surface("metal", {METAL_ATTRIBUTE}) = {{{", ".join(metal_ids)}}};')
    lines.append(f'Physical Volume("substrate", {SUBSTRATE_ATTRIBUTE}) = {{sub}};')
    lines.append(f'Physical Volume("vacuum", {VACUUM_ATTRIBUTE}) = {{vac}};')
    lines.append(
        "// Enclosure and interface physical surfaces are assigned by the Python pipeline."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _bbox_center(box: Iterable[float]) -> tuple[float, float, float]:
    x0, y0, z0, x1, y1, z1 = list(box)
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)


def mesh_geometry(
    geometry: Geometry,
    stack: SubstrateStack,
    output_path: str | Path,
    *,
    controls: MeshControls | None = None,
    model_name: str = "textlayout",
) -> MeshManifest:
    """Mesh ``geometry`` on ``stack`` into ``output_path`` (``.msh``).

    Returns a :class:`MeshManifest`; when Gmsh is absent the manifest carries
    ``status="SKIPPED_SOLVER_ABSENT"`` and a ``.geo`` path. Never raises for a
    missing solver.
    """
    controls = controls or MeshControls()
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if geometry.is_empty:
        return MeshManifest(
            status="FAILED", reason="geometry has no polygons", stack=stack, controls=controls
        )
    geo_path = write_geo_script(geometry, stack, controls, target.with_suffix(".geo"))
    base = {
        "stack": stack,
        "controls": controls,
        "geo_path": geo_path,
        "metal_polygon_count": len(_metal_polygons(geometry, stack)),
        "domain_bbox_um": _domain_bbox(geometry, stack),
    }
    try:
        import gmsh
    except ImportError:
        return MeshManifest(
            status="SKIPPED_SOLVER_ABSENT",
            reason="gmsh Python SDK not installed; .geo script prepared instead",
            **base,
        )

    started = time.perf_counter()
    box = base["domain_bbox_um"]
    assert isinstance(box, dict)
    process_path = os.environ.get("PATH")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads3D", 1)
        gmsh.option.setNumber("Mesh.RandomFactor", 0)
        gmsh.option.setNumber("Mesh.MshFileVersion", controls.msh_version)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.ElementOrder", controls.element_order)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", controls.characteristic_length_um)
        gmsh.model.add(model_name)
        occ = gmsh.model.occ
        dx, dy = box["xmax"] - box["xmin"], box["ymax"] - box["ymin"]
        substrate = occ.addBox(
            box["xmin"], box["ymin"], box["zmin"], dx, dy, stack.substrate_thickness_um
        )
        vacuum = occ.addBox(box["xmin"], box["ymin"], 0.0, dx, dy, stack.vacuum_height_um)
        volume_inputs = [(3, substrate), (3, vacuum)]
        metal_inputs: list[tuple[int, int]] = []
        for _layer, points in _metal_polygons(geometry, stack):
            tags = [occ.addPoint(x, y, 0.0) for x, y in points]
            wire = occ.addWire(
                [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
            )
            metal_inputs.append((2, occ.addPlaneSurface([wire])))
        _, mapping = occ.fragment(volume_inputs, metal_inputs, removeObject=True, removeTool=True)
        occ.synchronize()

        substrate_tags = sorted({tag for dim, tag in mapping[0] if dim == 3})
        vacuum_tags = sorted({tag for dim, tag in mapping[1] if dim == 3})
        metal_surfaces = sorted(
            {tag for mapped in mapping[len(volume_inputs) :] for dim, tag in mapped if dim == 2}
        )
        boundary_counts: dict[int, int] = {}
        for dim, tag in gmsh.model.getEntities(3):
            for sdim, surface in gmsh.model.getBoundary([(dim, tag)], oriented=False):
                if sdim == 2:
                    boundary_counts[surface] = boundary_counts.get(surface, 0) + 1
        enclosure: list[int] = []
        interface: list[int] = []
        tol = 1e-6
        for surface, count in sorted(boundary_counts.items()):
            if surface in metal_surfaces:
                continue
            sbox = gmsh.model.getBoundingBox(2, surface)
            on_z0 = abs(sbox[2]) < tol and abs(sbox[5]) < tol
            if count >= 2 and on_z0:
                interface.append(surface)
            elif count == 1:
                enclosure.append(surface)
        groups = [
            (3, SUBSTRATE_ATTRIBUTE, substrate_tags, "substrate"),
            (3, VACUUM_ATTRIBUTE, vacuum_tags, "vacuum"),
            (2, METAL_ATTRIBUTE, metal_surfaces, "metal"),
            (2, ENCLOSURE_ATTRIBUTE, enclosure, "enclosure"),
            (2, INTERFACE_ATTRIBUTE, interface, "interface"),
        ]
        for dimension, attribute, tags, name in groups:
            if not tags and name != "interface":
                raise RuntimeError(f"Gmsh fragment produced no entities for {name}")
            if tags:
                gmsh.model.addPhysicalGroup(dimension, tags, attribute)
                gmsh.model.setPhysicalName(dimension, attribute, name)

        metal_curves = sorted(
            {
                tag
                for surface in metal_surfaces
                for dim, tag in gmsh.model.getBoundary([(2, surface)], oriented=False)
                if dim == 1
            }
        )
        if metal_curves:
            distance = gmsh.model.mesh.field.add("Distance")
            gmsh.model.mesh.field.setNumbers(distance, "CurvesList", metal_curves)
            threshold = gmsh.model.mesh.field.add("Threshold")
            gmsh.model.mesh.field.setNumber(threshold, "InField", distance)
            gmsh.model.mesh.field.setNumber(threshold, "SizeMin", controls.metal_edge_length_um)
            gmsh.model.mesh.field.setNumber(threshold, "SizeMax", controls.characteristic_length_um)
            gmsh.model.mesh.field.setNumber(
                threshold, "DistMin", controls.metal_edge_length_um * 2.0
            )
            gmsh.model.mesh.field.setNumber(threshold, "DistMax", controls.metal_edge_distance_um)
            gmsh.model.mesh.field.setAsBackgroundMesh(threshold)
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

        gmsh.model.mesh.generate(3)
        element_types, element_tags, _ = gmsh.model.mesh.getElements(3)
        element_count = sum(len(tags) for tags in element_tags)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        qualities: list[float] = []
        for etype, tags in zip(element_types, element_tags, strict=True):
            if len(tags):
                qualities.extend(
                    float(q) for q in gmsh.model.mesh.getElementQualities(list(tags), "minSICN")
                )
        gmsh.write(str(target))
        version = str(gmsh.option.getString("General.Version") or "") or None
    except Exception as exc:  # noqa: BLE001 - report honest failure, never a fake mesh
        return MeshManifest(
            status="FAILED",
            reason=f"gmsh pipeline failed: {type(exc).__name__}: {exc}",
            runtime_seconds=time.perf_counter() - started,
            **base,
        )
    finally:
        gmsh.finalize()
        if process_path is not None:
            os.environ["PATH"] = process_path

    return MeshManifest(
        status="MESH_GENERATED",
        mesh_path=target,
        mesh_sha256=_sha256(target),
        gmsh_version=version,
        runtime_seconds=time.perf_counter() - started,
        element_count=element_count,
        node_count=len(node_tags),
        minimum_quality=min(qualities) if qualities else None,
        mean_quality=sum(qualities) / len(qualities) if qualities else None,
        **base,
    )


def write_manifest(manifest: MeshManifest, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = manifest.model_dump(mode="json", by_alias=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


__all__ = [
    "ENCLOSURE_ATTRIBUTE",
    "INTERFACE_ATTRIBUTE",
    "MESH_MANIFEST_SCHEMA",
    "METAL_ATTRIBUTE",
    "SUBSTRATE_ATTRIBUTE",
    "VACUUM_ATTRIBUTE",
    "MeshControls",
    "MeshManifest",
    "MeshStatus",
    "SubstrateStack",
    "gmsh_available",
    "mesh_geometry",
    "write_geo_script",
    "write_manifest",
]
