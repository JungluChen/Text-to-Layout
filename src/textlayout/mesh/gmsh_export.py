"""Export a simplified substrate/metal extrusion as deterministic Gmsh GEO."""

from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry


def export_smoke_test_gmsh_geo(
    geometry: Geometry,
    path: str | Path,
    *,
    substrate_thickness_um: float = 500.0,
    metal_thickness_um: float = 0.2,
    characteristic_length_um: float = 50.0,
) -> Path:
    """Write an explicit preparation model, not a claim of full-chip accuracy.

    ``characteristic_length_um`` is Gmsh's ``lc``. It was hard-coded at 50 um,
    which made a mesh-refinement study impossible: every level would have
    produced the identical mesh, so any "convergence" it reported would have
    been a tautology rather than evidence.
    """
    if not characteristic_length_um > 0:
        raise ValueError(
            f"characteristic_length_um must be positive, got {characteristic_length_um!r}"
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    bbox = geometry.bbox()
    margin = max(bbox.width, bbox.height) * 0.1 + 50.0
    lines = [
        'SetFactory("OpenCASCADE");',
        "Mesh.MshFileVersion = 4.1;",
        f"lc = {characteristic_length_um:.9g};",
        (
            f"substrate = newv; Box(substrate) = "
            f"{{{bbox.xmin-margin:.9g}, {bbox.ymin-margin:.9g}, {-substrate_thickness_um:.9g}, "
            f"{bbox.width+2*margin:.9g}, {bbox.height+2*margin:.9g}, {substrate_thickness_um:.9g}}};"
        ),
    ]
    volumes: list[str] = []
    point_id = 1
    line_id = 1
    loop_id = 1
    surface_id = 1
    for index, polygon in enumerate(geometry.polygons, 1):
        point_ids: list[int] = []
        for x, y in polygon.points:
            lines.append(f"Point({point_id}) = {{{x:.9g}, {y:.9g}, 0, lc}};")
            point_ids.append(point_id)
            point_id += 1
        edge_ids: list[int] = []
        for offset, start in enumerate(point_ids):
            stop = point_ids[(offset + 1) % len(point_ids)]
            lines.append(f"Line({line_id}) = {{{start}, {stop}}};")
            edge_ids.append(line_id)
            line_id += 1
        edges = ", ".join(str(value) for value in edge_ids)
        lines.append(f"Curve Loop({loop_id}) = {{{edges}}};")
        lines.append(f"Plane Surface({surface_id}) = {{{loop_id}}};")
        name = f"metal_{index}"
        lines.append(
            f"{name}[] = Extrude {{0, 0, {metal_thickness_um:.9g}}} "
            f"{{ Surface{{{surface_id}}}; Layers{{1}}; Recombine; }};"
        )
        volumes.append(f"{name}[1]")
        loop_id += 1
        surface_id += 1
    lines.append("Physical Volume(1) = {substrate};")
    if volumes:
        lines.append(f"Physical Volume(2) = {{{', '.join(volumes)}}};")
    lines.extend(
        (
            "outer[] = Boundary{ Volume{substrate}; };",
            "Physical Surface(1) = {outer[]};",
        )
    )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


# Compatibility name. Production Palace work uses ``mesh_quarter_wave`` from
# ``textlayout.fem.gmsh_physical``; this exporter remains a preparation smoke test.
export_gmsh_geo = export_smoke_test_gmsh_geo
