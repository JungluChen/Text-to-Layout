"""Physical Gmsh projection for the quarter-wave Palace benchmark."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from textlayout.fem import FEMModel
from textlayout.models import Geometry
from textlayout.schemas.dsl import QuarterWaveResonatorSpec


@dataclass(frozen=True)
class GmshMeshResult:
    path: Path
    runtime_seconds: float
    element_count: int
    minimum_quality: float
    mean_quality: float


def _bbox_center(box: tuple[float, float, float, float, float, float]) -> tuple[float, float, float]:
    return ((box[0] + box[3]) / 2.0, (box[1] + box[4]) / 2.0, (box[2] + box[5]) / 2.0)


def mesh_quarter_wave(
    geometry: Geometry,
    params: QuarterWaveResonatorSpec,
    model: FEMModel,
    output_path: str | Path,
    *,
    domain_scale: float = 1.0,
    substrate_thickness_um: float | None = None,
    vacuum_height_um: float | None = None,
    lid_height_um: float | None = None,
    lateral_margin_um: float | None = None,
) -> GmshMeshResult:
    """Generate a real tetrahedral mesh whose attributes match ``FEMModel``.

    The four explicit extents override the legacy uniform ``domain_scale``.
    When ``lid_height_um`` exceeds ``vacuum_height_um``, an additional
    far-vacuum volume spans the gap and must exist in the model as
    attribute 5 (``vacuum_far``); the PEC lid then sits at ``lid_height_um``.
    """
    if domain_scale <= 0:
        raise ValueError("domain_scale must be positive")
    try:
        import gmsh  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("gmsh Python bindings are required for the Palace mesh") from exc

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bbox = geometry.bbox()
    substrate_depth = (
        substrate_thickness_um if substrate_thickness_um is not None else 300.0 * domain_scale
    )
    vacuum_height = vacuum_height_um if vacuum_height_um is not None else 300.0 * domain_scale
    lid_height = lid_height_um if lid_height_um is not None else vacuum_height
    y_margin = lateral_margin_um if lateral_margin_um is not None else 100.0 * domain_scale
    for label, value in (
        ("substrate_thickness_um", substrate_depth),
        ("vacuum_height_um", vacuum_height),
        ("lateral_margin_um", y_margin),
    ):
        if value <= 0:
            raise ValueError(f"{label} must be positive")
    if lid_height < vacuum_height:
        raise ValueError("lid_height_um must not be below vacuum_height_um")
    has_far_vacuum = lid_height > vacuum_height
    x0, x1 = bbox.xmin, bbox.xmax
    y0, y1 = bbox.ymin - y_margin, bbox.ymax + y_margin
    near_half_width = params.center_width_um / 2 + params.gap_um + params.ground_width_um
    near_y0 = -params.short_width_um
    near_y1 = params.length_um + params.coupling_gap_um + params.center_width_um
    near_x0, near_x1 = -near_half_width, near_half_width

    started = time.perf_counter()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.option.setNumber("Mesh.MaxNumThreads3D", 1)
        gmsh.option.setNumber("Mesh.RandomFactor", 0)
        # Palace 0.16's bundled MFEM rejects valid multi-entity MSH 4.1 files
        # with "vertices indices are not unique". MSH 2.2 preserves this
        # model's disjoint physical groups and is accepted by that reader.
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.model.add(model.name)
        occ = gmsh.model.occ

        full_substrate = occ.addBox(x0, y0, -substrate_depth, x1 - x0, y1 - y0, substrate_depth)
        near_substrate = occ.addBox(
            near_x0,
            near_y0,
            -substrate_depth,
            near_x1 - near_x0,
            near_y1 - near_y0,
            substrate_depth,
        )
        outer_substrate, _ = occ.cut(
            [(3, full_substrate)], [(3, near_substrate)], removeObject=True, removeTool=False
        )
        full_vacuum = occ.addBox(x0, y0, 0.0, x1 - x0, y1 - y0, vacuum_height)
        near_vacuum = occ.addBox(
            near_x0,
            near_y0,
            0.0,
            near_x1 - near_x0,
            near_y1 - near_y0,
            vacuum_height,
        )
        outer_vacuum, _ = occ.cut(
            [(3, full_vacuum)], [(3, near_vacuum)], removeObject=True, removeTool=False
        )
        far_vacuum: list[tuple[int, int]] = []
        if has_far_vacuum:
            far_vacuum = [
                (
                    3,
                    occ.addBox(
                        x0, y0, vacuum_height, x1 - x0, y1 - y0, lid_height - vacuum_height
                    ),
                )
            ]
        volume_inputs = [
            (3, near_substrate),
            *outer_substrate,
            (3, near_vacuum),
            *outer_vacuum,
            *far_vacuum,
        ]
        volume_attributes = [
            1,
            *([2] * len(outer_substrate)),
            3,
            *([4] * len(outer_vacuum)),
            *([5] * len(far_vacuum)),
        ]

        metal_inputs: list[tuple[int, int]] = []
        for polygon in geometry.polygons:
            points = [occ.addPoint(x, y, 0.0) for x, y in polygon.points]
            wire = occ.addWire(
                [
                    occ.addLine(
                        points[index],
                        points[(index + 1) % len(points)],
                    )
                    for index in range(len(points))
                ]
            )
            metal_inputs.append((2, occ.addPlaneSurface([wire])))

        _, mapping = occ.fragment(
            volume_inputs, metal_inputs, removeObject=True, removeTool=True
        )
        occ.synchronize()

        metal_surfaces = sorted(
            {
                tag
                for mapped in mapping[len(volume_inputs) :]
                for dim, tag in mapped
                if dim == 2
            }
        )
        volume_tags = sorted(tag for dim, tag in gmsh.model.getEntities(3) if dim == 3)
        volume_groups: dict[int, list[int]] = {
            attribute: [] for attribute in sorted(set(volume_attributes))
        }
        for attribute, mapped in zip(volume_attributes, mapping[: len(volume_inputs)]):
            volume_groups[attribute].extend(tag for dim, tag in mapped if dim == 3)
        volume_groups = {
            attribute: sorted(set(tags)) for attribute, tags in volume_groups.items()
        }

        boundary_counts: dict[int, int] = {}
        for tag in volume_tags:
            for dim, surface in gmsh.model.getBoundary([(3, tag)], oriented=False):
                if dim == 2:
                    boundary_counts[surface] = boundary_counts.get(surface, 0) + 1

        package: list[int] = []
        lid: list[int] = []
        port_in: list[int] = []
        port_out: list[int] = []
        near_interface: list[int] = []
        outer_interface: list[int] = []
        tolerance = 1e-6
        for surface, count in sorted(boundary_counts.items()):
            if surface in metal_surfaces:
                continue
            box = gmsh.model.getBoundingBox(2, surface)
            cx, cy, _ = _bbox_center(box)
            on_z0 = abs(box[2]) < tolerance and abs(box[5]) < tolerance
            if on_z0 and count >= 2:
                if near_x0 <= cx <= near_x1 and near_y0 <= cy <= near_y1:
                    near_interface.append(surface)
                else:
                    outer_interface.append(surface)
            elif count == 1 and abs(box[5] - lid_height) < tolerance:
                lid.append(surface)
            elif count == 1 and abs(box[0] - x0) < tolerance and abs(box[3] - x0) < tolerance:
                port_in.append(surface)
            elif count == 1 and abs(box[0] - x1) < tolerance and abs(box[3] - x1) < tolerance:
                port_out.append(surface)
            elif count == 1:
                package.append(surface)

        physical: list[tuple[int, int, list[int], str]] = [
            *((3, attribute, tags, model.volumes[attribute - 1].name) for attribute, tags in volume_groups.items()),
            (2, 10, metal_surfaces, "superconducting_metal"),
            (2, 11, package, "package_walls"),
            (2, 12, lid, "lid"),
            (2, 20, near_interface, "substrate_vacuum_interface"),
            (2, 21, outer_interface, "outer_substrate_vacuum_interface"),
            (2, 30, port_in, "RF_IN"),
            (2, 31, port_out, "RF_OUT"),
        ]
        for dimension, attribute, tags, name in physical:
            if not tags:
                raise RuntimeError(f"Gmsh projection produced no entities for {name}")
            gmsh.model.addPhysicalGroup(dimension, tags, attribute)
            gmsh.model.setPhysicalName(dimension, attribute, name)

        sizes = {item.target: item.characteristic_length for item in model.mesh.refinements}
        metal_curves = sorted(
            {
                tag
                for surface in metal_surfaces
                for dim, tag in gmsh.model.getBoundary([(2, surface)], oriented=False)
                if dim == 1
            }
        )
        open_curves: list[int] = []
        grounded_curves: list[int] = []
        coupler_curves: list[int] = []
        for curve in metal_curves:
            box = gmsh.model.getBoundingBox(1, curve)
            _, cy, _ = _bbox_center(box)
            if abs(cy) <= params.short_width_um * 1.5:
                grounded_curves.append(curve)
            if abs(cy - params.length_um) <= max(params.gap_um, params.coupling_gap_um) * 2:
                open_curves.append(curve)
            if abs(cy - (params.length_um + params.coupling_gap_um)) <= params.center_width_um * 2:
                coupler_curves.append(curve)

        fields: list[int] = []

        def threshold(
            *, curves: list[int] | None = None, surfaces: list[int] | None = None,
            size: float, distance: float
        ) -> None:
            if not curves and not surfaces:
                return
            distance_field = gmsh.model.mesh.field.add("Distance")
            if curves:
                gmsh.model.mesh.field.setNumbers(distance_field, "CurvesList", curves)
            if surfaces:
                gmsh.model.mesh.field.setNumbers(distance_field, "SurfacesList", surfaces)
            field = gmsh.model.mesh.field.add("Threshold")
            gmsh.model.mesh.field.setNumber(field, "InField", distance_field)
            gmsh.model.mesh.field.setNumber(field, "SizeMin", size)
            gmsh.model.mesh.field.setNumber(field, "SizeMax", model.mesh.characteristic_length)
            gmsh.model.mesh.field.setNumber(field, "DistMin", max(size * 2.0, 1.0))
            gmsh.model.mesh.field.setNumber(field, "DistMax", distance)
            fields.append(field)

        threshold(
            curves=metal_curves,
            size=sizes["cpw_conductor_edges"],
            distance=60.0,
        )
        threshold(
            surfaces=near_interface,
            size=sizes["cpw_gaps"],
            distance=50.0,
        )
        threshold(curves=coupler_curves, size=sizes["coupler_gap"], distance=40.0)
        threshold(curves=open_curves, size=sizes["open_end"], distance=40.0)
        threshold(curves=grounded_curves, size=sizes["grounded_end"], distance=40.0)
        threshold(
            surfaces=[*near_interface, *outer_interface],
            size=sizes["substrate_vacuum_interface"],
            distance=120.0,
        )
        if fields:
            minimum = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(minimum, "FieldsList", fields)
            gmsh.model.mesh.field.setAsBackgroundMesh(minimum)

        gmsh.option.setNumber("Mesh.MeshSizeMin", min(sizes.values()))
        gmsh.option.setNumber("Mesh.MeshSizeMax", model.mesh.characteristic_length)
        gmsh.option.setNumber("Mesh.Algorithm3D", 10)
        gmsh.model.mesh.generate(3)
        types, element_tags, _ = gmsh.model.mesh.getElements(3)
        tetra_tags: list[int] = []
        for element_type, tags in zip(types, element_tags):
            name = gmsh.model.mesh.getElementProperties(element_type)[0].lower()
            if "tetra" in name:
                tetra_tags.extend(int(tag) for tag in tags)
        if not tetra_tags:
            raise RuntimeError("Gmsh generated no tetrahedra")
        qualities = list(gmsh.model.mesh.getElementQualities(tetra_tags, "minSICN"))
        if not qualities:
            raise RuntimeError("Gmsh returned no tetrahedron quality metrics")
        gmsh.write(str(target))
        return GmshMeshResult(
            path=target,
            runtime_seconds=time.perf_counter() - started,
            element_count=len(tetra_tags),
            minimum_quality=float(min(qualities)),
            mean_quality=float(sum(qualities) / len(qualities)),
        )
    finally:
        gmsh.finalize()
