"""gmsh meshing of the GDS-on-process-stack geometry for FEM solvers.

Produces the 3D tetrahedral mesh (.msh) that Palace and Elmer consume. gmsh is
pip-installable on Windows, so this adapter actually runs locally when `gmsh` is
importable and skips cleanly otherwise. The mesh is a process-stack model: one
conformal solid per populated metal layer at its real elevation/thickness, on a
(mesh-truncated) substrate slab. Per-polygon meshing is a future refinement.
"""

from __future__ import annotations

import json
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from textlayout._legacy.extraction import layer_bounding_boxes_from_gds
from textlayout._legacy.pyaedt_bridge import build_pyaedt_config

# Substrate is mesh-truncated so a 500 um wafer does not blow up the element count.
SUBSTRATE_MESH_DEPTH_UM = 30.0


def mesh_available() -> bool:
    """Return whether the gmsh Python module can be imported."""
    try:
        return find_spec("gmsh") is not None
    except ModuleNotFoundError:
        return False


def _layer_footprints(gds_path: str | Path) -> dict[str, list[float]]:
    """Union bounding box (x0, y0, x1, y1) of every shape on each GDS layer number."""
    footprints: dict[str, list[float]] = {}
    for shape in layer_bounding_boxes_from_gds(gds_path):
        number = str(int(shape["layer"][0]))
        x0, y0, x1, y1 = shape["bbox_um"]
        if number not in footprints:
            footprints[number] = [x0, y0, x1, y1]
        else:
            box = footprints[number]
            box[0], box[1] = min(box[0], x0), min(box[1], y0)
            box[2], box[3] = max(box[2], x1), max(box[3], y1)
    return footprints


def build_stack_mesh(
    *,
    gds_path: str | Path,
    layer_mapping: dict[str, Any],
    footprints: dict[str, list[float]],
    bbox_um: list[float],
    substrate: dict[str, Any],
    mesh_path: str | Path,
    mesh_size_um: float | None = None,
    min_thickness_um: float = 0.05,
) -> dict[str, Any]:
    """Build and write a 3D tetrahedral mesh of the process stack with gmsh."""
    import gmsh

    lateral = max(bbox_um[2] - bbox_um[0], bbox_um[3] - bbox_um[1], 1.0)
    margin = float(substrate.get("lateral_margin_um", 50.0))
    size = float(mesh_size_um) if mesh_size_um else max(lateral / 18.0, 4.0)

    process_path = os.environ.get("PATH")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("text_to_gds_stack")
        occ = gmsh.model.occ

        volumes: list[tuple[int, int]] = []
        layer_tags: dict[str, int] = {}
        sub_depth = min(float(substrate.get("thickness_um", 500.0)), SUBSTRATE_MESH_DEPTH_UM)
        sub_tag = occ.addBox(
            bbox_um[0] - margin,
            bbox_um[1] - margin,
            -sub_depth,
            (bbox_um[2] - bbox_um[0]) + 2 * margin,
            (bbox_um[3] - bbox_um[1]) + 2 * margin,
            sub_depth,
        )
        volumes.append((3, sub_tag))

        for number, spec in layer_mapping.items():
            box = footprints.get(number)
            if box is None:
                continue
            thickness = max(float(spec["thickness_um"]), min_thickness_um)
            elevation = float(spec["elevation_um"])
            dx, dy = box[2] - box[0], box[3] - box[1]
            if dx <= 0 or dy <= 0:
                continue
            tag = occ.addBox(box[0], box[1], elevation, dx, dy, thickness)
            volumes.append((3, tag))
            layer_tags[number] = tag

        occ.synchronize()
        if len(volumes) > 1:
            occ.fragment(volumes, volumes)
            occ.synchronize()

        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        gmsh.option.setNumber("Mesh.MeshSizeMin", size / 8.0)
        gmsh.model.mesh.generate(3)

        node_tags = gmsh.model.mesh.getNodes()[0]
        n_nodes = len(node_tags)
        _, elem_tags, _ = gmsh.model.mesh.getElements(dim=3)
        n_tets = int(sum(len(tags) for tags in elem_tags))

        mesh_file = Path(mesh_path)
        mesh_file.parent.mkdir(parents=True, exist_ok=True)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.write(str(mesh_file))
    finally:
        try:
            gmsh.finalize()
        finally:
            if process_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = process_path

    return {
        "nodes": n_nodes,
        "tetrahedra": n_tets,
        "meshed_layers": sorted(layer_tags),
        "mesh_size_um": size,
        "substrate_mesh_depth_um": sub_depth,
    }


def write_stack_mesh(
    gds_path: str | Path,
    *,
    mesh_path: str | Path,
    report_path: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    mesh_size_um: float | None = None,
) -> dict[str, Any]:
    """Mesh the GDS-on-process-stack geometry with gmsh; skip cleanly if unavailable."""
    config = build_pyaedt_config(
        gds_path,
        outputs={},
        sidecar_path=sidecar_path,
        process_path=process_path,
    )
    result: dict[str, Any] = {
        "schema": "text-to-gds.gmsh-mesh.v1",
        "backend": "gmsh",
        "source_gds": str(gds_path),
        "mesh_path": str(mesh_path),
        "layer_mapping": {
            number: {
                "name": spec["name"],
                "elevation_um": spec["elevation_um"],
                "thickness_um": spec["thickness_um"],
            }
            for number, spec in config["layer_mapping"].items()
        },
    }
    if not mesh_available():
        result["status"] = "skipped"
        result["warnings"] = ["gmsh is not installed; run: uv pip install gmsh"]
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["report_path"] = str(report_path)
        return result

    footprints = _layer_footprints(gds_path)
    try:
        mesh_stats = build_stack_mesh(
            gds_path=gds_path,
            layer_mapping=config["layer_mapping"],
            footprints=footprints,
            bbox_um=config["bbox_um"],
            substrate=config["substrate"],
            mesh_path=mesh_path,
            mesh_size_um=mesh_size_um,
        )
        result["status"] = "executed"
        result.update(mesh_stats)
    except Exception as exc:  # pragma: no cover - depends on local gmsh/geometry
        result["status"] = "failed"
        result["error"] = str(exc)

    result["model_validity"] = (
        "Process-stack mesh: one conformal solid per populated metal layer at its real "
        "elevation/thickness on a mesh-truncated substrate. Refine to per-polygon geometry "
        "and calibrated mesh sizing before FEM signoff."
    )
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result
