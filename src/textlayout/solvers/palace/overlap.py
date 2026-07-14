"""Material-resolved MPI field integration and modal overlap."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast
from xml.etree import ElementTree

import numpy as np
import numpy.typing as npt

from textlayout.evidence.canonical import sha256_file, sha256_json
from textlayout.fem import FEMModel
from textlayout.solvers.palace.models import (
    FieldOverlapResult,
    MaterialOverlapEntry,
    MaterialOverlapMap,
    classify_mac_applicability,
    PalaceOutputError,
)
from textlayout.solvers.palace.parser import _decode_vtk_array, field_artifact_files

EPSILON_0_F_PER_M = 8.8541878128e-12
MU_0_H_PER_M = 1.25663706212e-6


def _tensor(value: object, *, what: str) -> tuple[tuple[float, float, float], ...]:
    if isinstance(value, (int, float)):
        scalar = float(value)
        return ((scalar, 0.0, 0.0), (0.0, scalar, 0.0), (0.0, 0.0, scalar))
    array = np.asarray(value, dtype=float)
    if array.shape != (3, 3) or not np.all(np.isfinite(array)):
        raise PalaceOutputError(f"{what} must be a finite scalar or 3x3 tensor")
    return (
        (float(array[0, 0]), float(array[0, 1]), float(array[0, 2])),
        (float(array[1, 0]), float(array[1, 1]), float(array[1, 2])),
        (float(array[2, 0]), float(array[2, 1]), float(array[2, 2])),
    )


def build_material_overlap_map(
    model: FEMModel, palace_config: dict[str, Any]
) -> MaterialOverlapMap:
    """Cross-check FEMModel volume materials against the resolved Palace config."""
    model_hash = sha256_json(model.model_dump(mode="json"))
    config_hash = sha256_json(palace_config)
    configured: dict[int, dict[str, Any]] = {}
    for item in palace_config.get("Domains", {}).get("Materials", []):
        if isinstance(item, dict):
            for attribute in item.get("Attributes", []):
                configured[int(attribute)] = item
    materials = {item.name: item for item in model.materials}
    entries: list[MaterialOverlapEntry] = []
    for volume in sorted(model.volumes, key=lambda item: item.attribute):
        material = materials[volume.material]
        resolved = configured.get(volume.attribute)
        if resolved is None:
            raise PalaceOutputError(
                f"volume attribute {volume.attribute} has no Palace material assignment"
            )
        epsilon = _tensor(resolved.get("Permittivity"), what="permittivity")
        mu = _tensor(resolved.get("Permeability", 1.0), what="permeability")
        if epsilon != _tensor(material.permittivity, what="model permittivity"):
            raise PalaceOutputError(
                f"attribute {volume.attribute} permittivity disagrees with FEMModel"
            )
        if mu != _tensor(material.permeability, what="model permeability"):
            raise PalaceOutputError(
                f"attribute {volume.attribute} permeability disagrees with FEMModel"
            )
        entries.append(
            MaterialOverlapEntry(
                attribute=volume.attribute,
                material_name=material.name,
                permittivity=epsilon,
                permeability=mu,
                source=(
                    "FEMModel volume/material cross-checked against resolved "
                    "Palace Domains.Materials"
                ),
                model_sha256=model_hash,
                critical_region=volume.attribute in model.critical_region_attributes,
            )
        )
    payload = {
        "schema_version": "textlayout.palace-material-overlap.v1",
        "model_sha256": model_hash,
        "palace_config_sha256": config_hash,
        "length_unit_m": model.length_unit_m,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "critical_surface_attribute_ids": sorted(model.critical_surface_attributes),
        "critical_near_field_region_names": sorted(model.critical_near_field_region_names),
        "critical_region_coverage": model.critical_region_coverage(),
    }
    return MaterialOverlapMap(**payload, map_sha256=sha256_json(payload))


@dataclass(frozen=True)
class _Mesh:
    corners: npt.NDArray[np.float64]
    interpolation_nodes: list[npt.NDArray[np.float64]]
    interpolation_fields: list[npt.NDArray[np.complex128]]
    interpolation_orders: npt.NDArray[np.int32]
    centroids: npt.NDArray[np.float64]
    cell_fields: npt.NDArray[np.complex128]
    volumes: npt.NDArray[np.float64]
    attributes: npt.NDArray[np.int32]
    raw_cell_count: int
    ghost_cells_removed: int
    duplicate_cells_removed: int
    unsupported_cells: int
    raw_total_volume: float
    mesh_sha256: str


@dataclass
class _LocatorMetrics:
    build_seconds: float = 0.0
    query_seconds: float = 0.0
    query_count: int = 0
    candidate_count: int = 0
    maximum_candidates: int = 0
    failed_queries: int = 0
    material_mismatch_rejections: int = 0
    maximum_candidate_centroid_distance: float = 0.0
    peak_process_rss_bytes: int = 0


class _MaterialAABBLocator:
    """Material-partitioned cell locator with an indexed bounding-sphere broad phase."""

    def __init__(self, mesh: _Mesh, *, max_process_rss_bytes: int | None = None) -> None:
        from scipy.spatial import cKDTree  # type: ignore[import-untyped]

        started = perf_counter()
        self._mesh = mesh
        self._max_process_rss_bytes = max_process_rss_bytes
        self._groups: dict[
            int,
            tuple[
                npt.NDArray[np.int64],
                Any,
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                float,
            ],
        ] = {}
        for attribute in sorted(set(int(value) for value in mesh.attributes)):
            indices = np.flatnonzero(mesh.attributes == attribute).astype(np.int64)
            nodes = [mesh.interpolation_nodes[int(index)] for index in indices]
            lower = np.asarray([item.min(axis=0) for item in nodes], dtype=float)
            upper = np.asarray([item.max(axis=0) for item in nodes], dtype=float)
            centroids = mesh.centroids[indices]
            radii = np.linalg.norm(
                np.maximum(np.abs(lower - centroids), np.abs(upper - centroids)), axis=1
            )
            self._groups[attribute] = (
                indices,
                cKDTree(centroids),
                lower,
                upper,
                float(radii.max(initial=0.0)),
            )
        self.metrics = _LocatorMetrics(build_seconds=perf_counter() - started)

    def candidates(
        self, point: npt.NDArray[np.float64], attribute: int
    ) -> list[tuple[int, float]]:
        return self.candidate_batches(
            np.asarray([point]), np.asarray([attribute], dtype=np.int32)
        )[0]

    def candidate_batches(
        self,
        points: npt.NDArray[np.float64],
        attributes: npt.NDArray[np.int32],
    ) -> list[list[tuple[int, float]]]:
        """Query many points while preserving deterministic per-point candidates."""
        if len(points) != len(attributes):
            raise ValueError("point and material-attribute counts differ")
        started = perf_counter()
        self.metrics.query_count += len(points)
        output: list[list[tuple[int, float]]] = [[] for _ in range(len(points))]
        for attribute in sorted(set(int(value) for value in attributes)):
            rows = np.flatnonzero(attributes == attribute)
            group = self._groups.get(attribute)
            if group is None:
                continue
            indices, tree, lower, upper, maximum_radius = group
            queried = tree.query_ball_point(points[rows], maximum_radius, workers=-1)
            for row, raw_local in zip(rows, queried, strict=True):
                point = points[row]
                local = np.asarray(raw_local, dtype=np.int64)
                if local.size:
                    tolerance = 64.0 * np.finfo(float).eps * max(
                        1.0, float(np.max(np.abs(point)))
                    )
                    selected = np.all(point >= lower[local] - tolerance, axis=1) & np.all(
                        point <= upper[local] + tolerance, axis=1
                    )
                    local = local[selected]
                candidates = [
                    (
                        int(indices[index]),
                        float(
                            np.linalg.norm(
                                self._mesh.centroids[indices[index]] - point
                            )
                        ),
                    )
                    for index in local
                ]
                candidates.sort(key=lambda item: (item[1], item[0]))
                output[int(row)] = candidates
        counts = [len(item) for item in output]
        self.metrics.candidate_count += sum(counts)
        self.metrics.maximum_candidates = max(
            self.metrics.maximum_candidates, max(counts, default=0)
        )
        self.metrics.failed_queries += sum(count == 0 for count in counts)
        self.metrics.maximum_candidate_centroid_distance = max(
            self.metrics.maximum_candidate_centroid_distance,
            max((distance for items in output for _, distance in items), default=0.0),
        )
        self.metrics.query_seconds += perf_counter() - started
        try:
            import psutil  # type: ignore[import-untyped]

            rss = psutil.Process().memory_info().rss
        except (ImportError, OSError):
            rss = 0
        self.metrics.peak_process_rss_bytes = max(
            self.metrics.peak_process_rss_bytes, rss
        )
        if self._max_process_rss_bytes is not None and rss > self._max_process_rss_bytes:
            raise PalaceOutputError(
                "RESOURCE_LIMIT_TERMINATED: field projection RSS "
                f"{rss} exceeds {self._max_process_rss_bytes} bytes"
            )
        return output


def _locator_result_fields(metrics: _LocatorMetrics) -> dict[str, float | int]:
    average = metrics.candidate_count / metrics.query_count if metrics.query_count else 0.0
    return {
        "spatial_index_build_seconds": metrics.build_seconds,
        "spatial_index_query_seconds": metrics.query_seconds,
        "average_candidates_per_point": average,
        "maximum_candidates_per_point": metrics.maximum_candidates,
        "failed_point_queries": metrics.failed_queries,
        "material_mismatch_rejections": metrics.material_mismatch_rejections,
        "maximum_candidate_centroid_distance": (
            metrics.maximum_candidate_centroid_distance
        ),
        "peak_projection_process_rss_bytes": metrics.peak_process_rss_bytes,
    }


def _optional_array(
    elements: dict[str | None, ElementTree.Element], names: tuple[str, ...], source: Path
) -> npt.NDArray[Any] | None:
    element = next((elements.get(name) for name in names if elements.get(name) is not None), None)
    return _decode_vtk_array(element, source) if element is not None else None


def _integration_mesh(path: Path, kind: str) -> _Mesh:
    corners: list[npt.NDArray[np.float64]] = []
    interpolation_nodes: list[npt.NDArray[np.float64]] = []
    interpolation_fields: list[npt.NDArray[np.complex128]] = []
    interpolation_orders: list[int] = []
    volumes: list[float] = []
    attributes_out: list[int] = []
    seen: set[object] = set()
    raw_count = ghosts = duplicates = unsupported = 0
    raw_volume = 0.0
    prefix = "E" if kind == "electric" else "B"
    artifacts = field_artifact_files(path)
    for piece in (item for item in artifacts if item.suffix.lower() == ".vtu"):
        root = ElementTree.parse(piece).getroot()
        points_element = root.find(".//Points/DataArray")
        point_data = {
            item.attrib.get("Name"): item for item in root.findall(".//PointData/DataArray")
        }
        cells_data = {
            item.attrib.get("Name"): item for item in root.findall(".//Cells/DataArray")
        }
        cell_data = {
            item.attrib.get("Name"): item for item in root.findall(".//CellData/DataArray")
        }
        attributes_element = cell_data.get("attribute")
        if points_element is None or attributes_element is None:
            raise PalaceOutputError(f"{piece}: missing points or material attributes")
        points = np.asarray(_decode_vtk_array(points_element, piece), dtype=float)
        real = np.asarray(_decode_vtk_array(point_data[f"{prefix}_real"], piece), dtype=float)
        imag = np.asarray(_decode_vtk_array(point_data[f"{prefix}_imag"], piece), dtype=float)
        fields = real.astype(np.complex128) + 1j * imag
        connectivity = np.asarray(_decode_vtk_array(cells_data["connectivity"], piece), dtype=np.int64)
        offsets = np.asarray(_decode_vtk_array(cells_data["offsets"], piece), dtype=np.int64)
        types = np.asarray(_decode_vtk_array(cells_data["types"], piece), dtype=np.uint8)
        attributes = np.asarray(_decode_vtk_array(attributes_element, piece), dtype=np.int32)
        ghost = _optional_array(cell_data, ("vtkGhostType",), piece)
        global_ids = _optional_array(
            cell_data, ("GlobalCellIds", "global_cell_ids", "GlobalElementId"), piece
        )
        starts = np.concatenate((np.asarray([0]), offsets[:-1]))
        raw_count += len(types)
        for index, cell_type in enumerate(types):
            if ghost is not None and int(ghost[index]) != 0:
                ghosts += 1
                continue
            node_ids = connectivity[starts[index] : offsets[index]]
            if int(cell_type) == 10 and len(node_ids) == 4:
                interpolation_order = 1
            elif int(cell_type) == 71 and len(node_ids) in (4, 10):
                interpolation_order = 2 if len(node_ids) == 10 else 1
            else:
                unsupported += 1
                continue
            # VTK Lagrange tetrahedra list the four vertices first. Palace's
            # quadratic output then supplies the six edge nodes.
            vertex_ids = node_ids[:4]
            xyz = points[vertex_ids]
            cell_nodes = points[node_ids]
            volume = _cell_volume(cell_nodes, interpolation_order)
            raw_volume += volume
            if global_ids is not None:
                key: object = ("global", int(global_ids[index]))
            else:
                key = tuple(
                    sorted(
                        tuple(float(cell) for cell in row)
                        for row in np.round(cell_nodes, 12)
                    )
                )
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            corners.append(xyz)
            interpolation_nodes.append(cell_nodes)
            interpolation_fields.append(fields[node_ids])
            interpolation_orders.append(interpolation_order)
            volumes.append(volume)
            attributes_out.append(int(attributes[index]))
    if not corners:
        raise PalaceOutputError(f"{path}: no supported tetrahedra available for integration")
    corner_array = np.asarray(corners)
    orders = np.asarray(interpolation_orders, dtype=np.int32)
    centroids = np.asarray(
        [
            _physical_point(nodes, int(order), np.full(4, 0.25))
            for nodes, order in zip(interpolation_nodes, orders, strict=True)
        ]
    )
    cell_fields = np.asarray(
        [
            _interpolate_cell(nodes, values, order, np.full(4, 0.25))
            for nodes, values, order in zip(
                interpolation_nodes, interpolation_fields, orders, strict=True
            )
        ]
    )
    artifact_hashes = {
        str(index): sha256_file(item) for index, item in enumerate(artifacts)
    }
    return _Mesh(
        corners=corner_array,
        interpolation_nodes=interpolation_nodes,
        interpolation_fields=interpolation_fields,
        interpolation_orders=orders,
        centroids=centroids,
        cell_fields=cell_fields,
        volumes=np.asarray(volumes),
        attributes=np.asarray(attributes_out, dtype=np.int32),
        raw_cell_count=raw_count,
        ghost_cells_removed=ghosts,
        duplicate_cells_removed=duplicates,
        unsupported_cells=unsupported,
        raw_total_volume=raw_volume,
        mesh_sha256=sha256_json(artifact_hashes),
    )


def _interpolate_cell(
    nodes: npt.NDArray[np.float64],
    values: npt.NDArray[np.complex128],
    order: int,
    barycentric: npt.NDArray[np.float64],
) -> npt.NDArray[np.complex128]:
    if order == 1:
        return cast(npt.NDArray[np.complex128], np.einsum("n,nj->j", barycentric, values[:4]))
    if order != 2 or len(nodes) != 10:
        raise PalaceOutputError(f"unsupported tetra interpolation order {order}")
    return cast(
        npt.NDArray[np.complex128],
        np.einsum("n,nj->j", _shape_weights(barycentric), values),
    )


_VTK_P2_TETRA_EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))


def _shape_weights(barycentric: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    weights = np.empty(10, dtype=float)
    weights[:4] = barycentric * (2.0 * barycentric - 1.0)
    for index, (left, right) in enumerate(_VTK_P2_TETRA_EDGES, start=4):
        weights[index] = 4.0 * barycentric[left] * barycentric[right]
    return weights


def _physical_point(
    nodes: npt.NDArray[np.float64], order: int, barycentric: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    weights = barycentric if order == 1 else _shape_weights(barycentric)
    return np.asarray(np.einsum("n,nj->j", weights, nodes))


def _geometry_jacobian(
    nodes: npt.NDArray[np.float64], order: int, local: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    step = 1e-7
    jacobian = np.empty((3, 3), dtype=float)
    for axis in range(3):
        plus, minus = local.copy(), local.copy()
        plus[axis] += step
        minus[axis] -= step
        plus_bary = np.asarray([1.0 - plus.sum(), *plus])
        minus_bary = np.asarray([1.0 - minus.sum(), *minus])
        jacobian[:, axis] = (
            _physical_point(nodes, order, plus_bary)
            - _physical_point(nodes, order, minus_bary)
        ) / (2.0 * step)
    return jacobian


def _cell_volume(nodes: npt.NDArray[np.float64], order: int) -> float:
    if order == 1:
        edges = nodes[1:4] - nodes[0]
        determinant = float(np.linalg.det(edges))
        if determinant <= np.finfo(float).eps:
            raise PalaceOutputError("tetrahedron has a non-positive or degenerate Jacobian")
        return determinant / 6.0
    high, low = 0.5854101966249685, 0.1381966011250105
    barycentric_points = [
        np.asarray([high if index == axis else low for index in range(4)])
        for axis in range(4)
    ]
    determinants = [
        float(np.linalg.det(_geometry_jacobian(nodes, order, barycentric[1:])))
        for barycentric in barycentric_points
    ]
    if min(determinants) <= np.finfo(float).eps:
        raise PalaceOutputError("quadratic tetrahedron has a non-positive Jacobian")
    return float(sum(determinants) / 24.0)


def _locate_point(
    nodes: npt.NDArray[np.float64], order: int, point: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64] | None:
    corners = nodes[:4]
    matrix = np.column_stack(
        (corners[1] - corners[0], corners[2] - corners[0], corners[3] - corners[0])
    )
    try:
        local = np.linalg.solve(matrix, point - corners[0])
    except np.linalg.LinAlgError:
        return None
    if order == 2:
        for _ in range(12):
            barycentric = np.asarray([1.0 - local.sum(), *local])
            residual = _physical_point(nodes, order, barycentric) - point
            if np.linalg.norm(residual) <= 1e-10:
                break
            try:
                local -= np.linalg.solve(_geometry_jacobian(nodes, order, local), residual)
            except np.linalg.LinAlgError:
                return None
    barycentric = np.asarray([1.0 - local.sum(), *local])
    return barycentric if np.all(barycentric >= -1e-8) and np.all(barycentric <= 1.0 + 1e-8) else None


def _tensors(
    material_map: MaterialOverlapMap, attributes: npt.NDArray[np.int32], kind: str
) -> npt.NDArray[np.float64]:
    entries = {entry.attribute: entry for entry in material_map.entries}
    missing = sorted(set(int(value) for value in attributes) - set(entries))
    if missing:
        raise PalaceOutputError(f"integration attributes lack material assignments: {missing}")
    result = []
    for attribute in attributes:
        entry = entries[int(attribute)]
        tensor = np.asarray(entry.permittivity if kind == "electric" else entry.permeability)
        result.append(tensor if kind == "electric" else np.linalg.inv(tensor))
    return np.asarray(result)


def _mac(
    a: npt.NDArray[np.complex128],
    b: npt.NDArray[np.complex128],
    volumes: npt.NDArray[np.float64],
    tensors: npt.NDArray[np.float64],
) -> float:
    wa = np.einsum("nij,nj->ni", tensors, a)
    wb = np.einsum("nij,nj->ni", tensors, b)
    inner = np.sum(volumes * np.einsum("ni,ni->n", np.conjugate(a), wb))
    norm_a = float(np.real(np.sum(volumes * np.einsum("ni,ni->n", np.conjugate(a), wa))))
    norm_b = float(np.real(np.sum(volumes * np.einsum("ni,ni->n", np.conjugate(b), wb))))
    if norm_a <= 0.0 or norm_b <= 0.0:
        raise PalaceOutputError("zero energy norm in projected field comparison")
    return max(0.0, min(1.0, float(abs(inner) ** 2 / (norm_a * norm_b))))


def _mac_from_samples(
    a: npt.NDArray[np.complex128],
    b: npt.NDArray[np.complex128],
    weights: npt.NDArray[np.float64],
    tensors: npt.NDArray[np.float64],
) -> float:
    wa = np.einsum("nij,nj->ni", tensors, a)
    wb = np.einsum("nij,nj->ni", tensors, b)
    inner = np.sum(weights * np.einsum("ni,ni->n", np.conjugate(a), wb))
    norm_a = float(np.real(np.sum(weights * np.einsum("ni,ni->n", np.conjugate(a), wa))))
    norm_b = float(np.real(np.sum(weights * np.einsum("ni,ni->n", np.conjugate(b), wb))))
    if norm_a <= 0.0 or norm_b <= 0.0:
        raise PalaceOutputError("zero energy norm in quadrature field comparison")
    return max(0.0, min(1.0, float(abs(inner) ** 2 / (norm_a * norm_b))))


def reconstruct_field_energy_j(
    field: Path,
    *,
    kind: Literal["electric", "magnetic"],
    material_map: MaterialOverlapMap,
    quadrature_order: int = 2,
) -> float:
    """Reconstruct time-averaged field energy from Palace's complex VTK field."""
    mesh = _integration_mesh(field, kind)
    entries = {entry.attribute: entry for entry in material_map.entries}
    missing = sorted(set(int(value) for value in mesh.attributes) - set(entries))
    if missing:
        raise PalaceOutputError(f"integration attributes lack material assignments: {missing}")
    total = 0.0
    if np.all(mesh.interpolation_orders == 1):
        fields = np.asarray(mesh.interpolation_fields, dtype=np.complex128)
        tensors = _tensors(material_map, mesh.attributes, kind)
        determinants = 6.0 * mesh.volumes
        for barycentric, base_weight in _tetra_quadrature(quadrature_order):
            values = np.einsum("nvc,v->nc", fields, barycentric)
            weighted = np.einsum("nij,nj->ni", tensors, values)
            density = np.real(np.einsum("ni,ni->n", np.conjugate(values), weighted))
            total += float(np.sum(density * determinants * base_weight))
        physical_scale = (
            EPSILON_0_F_PER_M if kind == "electric" else 1.0 / MU_0_H_PER_M
        )
        return 0.5 * physical_scale * total * material_map.length_unit_m**3
    for nodes, field_values, order, attribute in zip(
        mesh.interpolation_nodes,
        mesh.interpolation_fields,
        mesh.interpolation_orders,
        mesh.attributes,
        strict=True,
    ):
        entry = entries[int(attribute)]
        tensor = np.asarray(
            entry.permittivity if kind == "electric" else entry.permeability,
            dtype=float,
        )
        if kind == "magnetic":
            tensor = np.linalg.inv(tensor)
        for barycentric, base_weight in _tetra_quadrature(quadrature_order):
            jacobian = _geometry_jacobian(nodes, int(order), barycentric[1:])
            determinant = float(np.linalg.det(jacobian))
            if determinant <= 0.0:
                raise PalaceOutputError("non-positive Jacobian during energy reconstruction")
            value = _interpolate_cell(nodes, field_values, int(order), barycentric)
            density = float(np.real(np.vdot(value, tensor @ value)))
            total += density * determinant * base_weight
    physical_scale = (
        EPSILON_0_F_PER_M if kind == "electric" else 1.0 / MU_0_H_PER_M
    )
    # Palace's complex fields use its energy normalization convention. Mesh
    # coordinates remain in the FEM model's declared length unit.
    return 0.5 * physical_scale * total * material_map.length_unit_m**3


def quarter_wave_longitudinal_sanity(
    field: Path,
    *,
    material_map: MaterialOverlapMap,
    electrical_length: float,
    corridor_half_width: float = 100.0,
    interface_half_height: float = 100.0,
    bins: int = 20,
) -> dict[str, Any]:
    """Measure quarter-wave electric and magnetic energy profiles near the CPW."""
    if electrical_length <= 0.0 or bins < 4:
        raise ValueError("electrical_length must be positive and bins must be at least four")
    profiles: dict[str, npt.NDArray[np.float64]] = {}
    selected_cells = 0
    for kind in ("electric", "magnetic"):
        mesh = _integration_mesh(field, kind)
        selected = (
            (np.abs(mesh.centroids[:, 0]) <= corridor_half_width)
            & (np.abs(mesh.centroids[:, 2]) <= interface_half_height)
            & (mesh.centroids[:, 1] >= 0.0)
            & (mesh.centroids[:, 1] <= electrical_length)
        )
        if not np.any(selected):
            raise PalaceOutputError("quarter-wave sanity corridor contains no field cells")
        selected_cells = max(selected_cells, int(selected.sum()))
        values = mesh.cell_fields[selected]
        tensors = _tensors(material_map, mesh.attributes[selected], kind)
        weighted = np.einsum("nij,nj->ni", tensors, values)
        density = np.real(np.einsum("ni,ni->n", np.conjugate(values), weighted))
        energy = density * mesh.volumes[selected]
        indices = np.minimum(
            (mesh.centroids[selected, 1] / electrical_length * bins).astype(int), bins - 1
        )
        profile = np.bincount(indices, weights=energy, minlength=bins).astype(float)
        if profile.sum() <= 0.0:
            raise PalaceOutputError(f"quarter-wave {kind} profile has zero energy")
        profiles[kind] = profile / profile.sum()
    electric = profiles["electric"]
    magnetic = profiles["magnetic"]
    positions = (np.arange(bins, dtype=float) + 0.5) / bins
    electric_reference = np.sin(0.5 * np.pi * positions) ** 2
    magnetic_reference = np.cos(0.5 * np.pi * positions) ** 2

    def correlation(values: npt.NDArray[np.float64], expected: npt.NDArray[np.float64]) -> float:
        return float(np.corrcoef(values, expected)[0, 1])

    endpoint_bins = max(1, bins // 10)
    electric_ground = float(electric[:endpoint_bins].sum())
    electric_open = float(electric[-endpoint_bins:].sum())
    magnetic_ground = float(magnetic[:endpoint_bins].sum())
    magnetic_open = float(magnetic[-endpoint_bins:].sum())
    return {
        "schema": "textlayout.palace-quarter-wave-sanity.v1",
        "selected_cell_count": selected_cells,
        "bin_count": bins,
        "electric_profile": electric.tolist(),
        "magnetic_profile": magnetic.tolist(),
        "electric_open_to_ground_ratio": electric_open / max(electric_ground, 1e-300),
        "magnetic_ground_to_open_ratio": magnetic_ground / max(magnetic_open, 1e-300),
        "electric_quarter_wave_profile_correlation": correlation(
            electric, electric_reference
        ),
        "magnetic_quarter_wave_profile_correlation": correlation(
            magnetic, magnetic_reference
        ),
        "electric_antinode_near_open_end": electric_open > electric_ground,
        "electric_node_near_grounded_end": electric_ground < electric_open,
        "magnetic_antinode_near_grounded_end": magnetic_ground > magnetic_open,
        "magnetic_node_near_open_end": magnetic_open < magnetic_ground,
    }


def _tetra_quadrature(order: int) -> list[tuple[npt.NDArray[np.float64], float]]:
    if order == 1:
        return [(np.asarray([0.25, 0.25, 0.25, 0.25]), 1.0 / 6.0)]
    if order == 2:
        high, low = 0.5854101966249685, 0.1381966011250105
        return [
            (
                np.asarray([high if index == axis else low for index in range(4)]),
                1.0 / 24.0,
            )
            for axis in range(4)
        ]
    raise PalaceOutputError(f"unsupported tetrahedral quadrature order {order}")


def _mesh_pair(left: Path, right: Path, kind: str) -> tuple[_Mesh, _Mesh]:
    left_mesh, right_mesh = _integration_mesh(left, kind), _integration_mesh(right, kind)
    left_volume, right_volume = float(left_mesh.volumes.sum()), float(right_mesh.volumes.sum())
    relative = abs(left_volume - right_volume) / max(left_volume, right_volume)
    if relative > 1e-6:
        raise PalaceOutputError(
            f"deduplicated domain volumes disagree by {relative:.3e}; "
            f"left={left_volume:.12g}, right={right_volume:.12g}"
        )
    return (left_mesh, right_mesh) if len(left_mesh.volumes) <= len(right_mesh.volumes) else (right_mesh, left_mesh)


def _result(
    reference: _Mesh,
    projected: npt.NDArray[np.complex128],
    mapped: npt.NDArray[np.bool_],
    distances: npt.NDArray[np.float64],
    *,
    kind: Literal["electric", "magnetic"],
    material_map: MaterialOverlapMap,
    method: str,
    implementation: str,
    interpolation_order: int,
    minimum_coverage: float,
    distance_limit: float,
    locator_metrics: _LocatorMetrics | None = None,
) -> FieldOverlapResult:
    total_volume = float(reference.volumes.sum())
    mapped_volume = float(reference.volumes[mapped].sum())
    coverage = mapped_volume / total_volume
    entries = {entry.attribute: entry for entry in material_map.entries}
    missing = sorted(set(int(value) for value in reference.attributes) - set(entries))
    if missing:
        raise PalaceOutputError(f"integration attributes lack material assignments: {missing}")
    critical = np.asarray([entries[int(value)].critical_region for value in reference.attributes])
    critical_volume = float(reference.volumes[critical].sum())
    mapped_critical = float(reference.volumes[mapped & critical].sum())
    critical_coverage = mapped_critical / critical_volume if critical_volume else 1.0
    if not np.any(mapped):
        raise PalaceOutputError("field projection mapped no integration cells")
    tensors = _tensors(material_map, reference.attributes[mapped], kind)
    total_mac = _mac(
        reference.cell_fields[mapped], projected[mapped], reference.volumes[mapped], tensors
    )
    per_region: dict[str, float] = {}
    for attribute in np.unique(reference.attributes[mapped]):
        selected = mapped & (reference.attributes == attribute)
        per_region[str(int(attribute))] = _mac(
            reference.cell_fields[selected],
            projected[selected],
            reference.volumes[selected],
            _tensors(material_map, reference.attributes[selected], kind),
        )
    normalized = distances / np.cbrt(np.maximum(reference.volumes, np.finfo(float).tiny))
    applicability = classify_mac_applicability("closed_lossless_hermitian")
    return FieldOverlapResult(
        field_kind=kind,
        projection_method=method,
        projection_implementation=implementation,
        integration_method=(
            "isoparametric quadratic tetrahedral centroid field quadrature"
            if int(reference.interpolation_orders.max()) == 2
            else "linear tetrahedral centroid quadrature"
        ),
        interpolation_order=interpolation_order,
        quadrature_order=1,
        material_weighting="epsilon tensor" if kind == "electric" else "inverse-mu tensor",
        material_map_sha256=material_map.map_sha256,
        common_mesh_sha256=reference.mesh_sha256,
        total_mac=total_mac,
        per_region_mac=per_region,
        global_mapped_volume_coverage=coverage,
        global_unmapped_volume_coverage=1.0 - coverage,
        critical_region_mapped_volume_coverage=critical_coverage,
        critical_region_unmapped_volume_coverage=1.0 - critical_coverage,
        critical_region_mapped_surface_coverage=float(
            material_map.critical_region_coverage.get("mapped_surface_coverage", 1.0)
        ),
        critical_region_unmapped_surface_coverage=(
            1.0
            - float(material_map.critical_region_coverage.get("mapped_surface_coverage", 1.0))
        ),
        mapped_volume=mapped_volume,
        expected_domain_volume=total_volume,
        maximum_mapping_distance=float(distances.max(initial=0.0)),
        average_mapping_distance=float(np.average(distances, weights=reference.volumes)),
        maximum_normalized_mapping_distance=float(normalized.max(initial=0.0)),
        interpolation_failures=int((~mapped).sum()),
        unmapped_critical_region_cell_count=int((~mapped & critical).sum()),
        raw_cell_count=reference.raw_cell_count,
        ghost_cells_removed=reference.ghost_cells_removed,
        duplicate_cells_removed=reference.duplicate_cells_removed,
        unsupported_cells=reference.unsupported_cells,
        integration_cell_count=len(reference.volumes),
        raw_total_volume=reference.raw_total_volume,
        deduplicated_total_volume=total_volume,
        **_locator_result_fields(locator_metrics or _LocatorMetrics()),
        passed_projection_quality=(
            coverage >= minimum_coverage
            and critical_coverage == 1.0
            and float(material_map.critical_region_coverage.get("mapped_surface_coverage", 1.0))
            == 1.0
            and float(material_map.critical_region_coverage.get("mapped_near_field_coverage", 1.0))
            == 1.0
            and float(normalized.max(initial=0.0)) <= distance_limit
            and reference.unsupported_cells == 0
        ),
        problem_class=applicability.problem_class,
        ordinary_energy_mac_use=applicability.ordinary_energy_mac_use,
        promotion_allowed_from_ordinary_mac=(
            applicability.promotion_allowed_from_ordinary_mac
        ),
    )


def reference_quadrature_energy_mac(
    left: Path,
    right: Path,
    *,
    kind: Literal["electric", "magnetic"],
    material_map: MaterialOverlapMap,
    quadrature_order: int = 2,
    relative_mapping_distance_limit: float = 0.25,
    minimum_coverage: float = 0.99,
    candidate_cells: int = 24,
    max_process_rss_bytes: int | None = None,
) -> FieldOverlapResult:
    """Reference quadrature integration over interpolated tetrahedral fields.

    This is still a nodal-field transfer reference, not a native H(curl) FEM
    overlap. It evaluates both complex vector fields at tetrahedral quadrature
    points and applies epsilon or inverse-mu material weighting at each sample.
    """
    reference, source = _mesh_pair(left, right, kind)
    samples = _tetra_quadrature(quadrature_order)
    locator = _MaterialAABBLocator(
        source, max_process_rss_bytes=max_process_rss_bytes
    )
    entries = {entry.attribute: entry for entry in material_map.entries}
    missing = sorted(set(int(value) for value in reference.attributes) - set(entries))
    if missing:
        raise PalaceOutputError(f"integration attributes lack material assignments: {missing}")

    reference_values: list[npt.NDArray[np.complex128]] = []
    projected_values: list[npt.NDArray[np.complex128]] = []
    integration_weights: list[float] = []
    integration_attributes: list[int] = []
    mapped_weight = 0.0
    critical_weight = 0.0
    mapped_critical_weight = 0.0
    failures = 0
    distances: list[float] = []

    del candidate_cells  # Compatibility-only; the AABB locator has no arbitrary k limit.
    sample_points: list[npt.NDArray[np.float64]] = []
    sample_cells: list[int] = []
    sample_barycentric: list[npt.NDArray[np.float64]] = []
    sample_weights: list[float] = []
    sample_attributes: list[int] = []
    for cell_index, (nodes, _field_values, order, attribute) in enumerate(
        zip(
            reference.interpolation_nodes,
            reference.interpolation_fields,
            reference.interpolation_orders,
            reference.attributes,
            strict=True,
        )
    ):
        cell_weight = 0.0
        for barycentric, base_weight in samples:
            point = _physical_point(nodes, int(order), barycentric)
            jacobian = _geometry_jacobian(nodes, int(order), barycentric[1:])
            determinant = float(np.linalg.det(jacobian))
            if determinant <= 0.0:
                raise PalaceOutputError("non-positive quadrature Jacobian")
            weight = determinant * base_weight
            cell_weight += weight
            attribute_int = int(attribute)
            is_critical = entries[attribute_int].critical_region
            if is_critical:
                critical_weight += weight
            sample_points.append(point)
            sample_cells.append(cell_index)
            sample_barycentric.append(barycentric)
            sample_weights.append(weight)
            sample_attributes.append(attribute_int)
        if cell_weight <= 0.0:
            raise PalaceOutputError("non-positive quadrature cell weight")

    point_array = np.asarray(sample_points, dtype=float)
    attribute_array = np.asarray(sample_attributes, dtype=np.int32)
    chunk_size = 4096
    for start in range(0, len(point_array), chunk_size):
        end = min(start + chunk_size, len(point_array))
        candidate_batches = locator.candidate_batches(
            point_array[start:end], attribute_array[start:end]
        )
        for point, cell_index, barycentric, weight, attribute_int, candidates in zip(
            point_array[start:end],
            sample_cells[start:end],
            sample_barycentric[start:end],
            sample_weights[start:end],
            sample_attributes[start:end],
            candidate_batches,
            strict=True,
        ):
            mapped_value: npt.NDArray[np.complex128] | None = None
            selected_distance = float("inf")
            for candidate_index, _distance in candidates:
                bary = _locate_point(
                    source.interpolation_nodes[candidate_index],
                    int(source.interpolation_orders[candidate_index]),
                    point,
                )
                if bary is None:
                    continue
                mapped_value = _interpolate_cell(
                    source.interpolation_nodes[candidate_index],
                    source.interpolation_fields[candidate_index],
                    int(source.interpolation_orders[candidate_index]),
                    bary,
                )
                reconstructed = _physical_point(
                    source.interpolation_nodes[candidate_index],
                    int(source.interpolation_orders[candidate_index]),
                    bary,
                )
                selected_distance = float(np.linalg.norm(reconstructed - point))
                break
            limit = relative_mapping_distance_limit * np.cbrt(
                max(reference.volumes[cell_index], np.finfo(float).tiny)
            )
            if mapped_value is None or selected_distance > limit:
                failures += 1
                continue
            nodes = reference.interpolation_nodes[cell_index]
            field_values = reference.interpolation_fields[cell_index]
            order = int(reference.interpolation_orders[cell_index])
            reference_values.append(
                _interpolate_cell(nodes, field_values, order, barycentric)
            )
            projected_values.append(mapped_value)
            integration_weights.append(weight)
            integration_attributes.append(attribute_int)
            distances.append(selected_distance)
            mapped_weight += weight
            if entries[attribute_int].critical_region:
                mapped_critical_weight += weight

    if not reference_values:
        raise PalaceOutputError("field projection mapped no quadrature points")

    value_a = np.asarray(reference_values, dtype=np.complex128)
    value_b = np.asarray(projected_values, dtype=np.complex128)
    weights = np.asarray(integration_weights, dtype=float)
    attributes = np.asarray(integration_attributes, dtype=np.int32)
    tensors = _tensors(material_map, attributes, kind)
    total_mac = _mac_from_samples(value_a, value_b, weights, tensors)

    per_region: dict[str, float] = {}
    for attribute in np.unique(attributes):
        selected = attributes == attribute
        per_region[str(int(attribute))] = _mac_from_samples(
            value_a[selected],
            value_b[selected],
            weights[selected],
            _tensors(material_map, attributes[selected], kind),
        )
    total_volume = float(reference.volumes.sum())
    coverage = min(1.0, max(0.0, mapped_weight / total_volume))
    critical_coverage = (
        min(1.0, max(0.0, mapped_critical_weight / critical_weight))
        if critical_weight > 0.0
        else 1.0
    )
    distance_array = np.asarray(distances, dtype=float)
    normalized = distance_array / np.cbrt(np.maximum(weights, np.finfo(float).tiny))
    applicability = classify_mac_applicability("closed_lossless_hermitian")
    surface_coverage = float(
        material_map.critical_region_coverage.get("mapped_surface_coverage", 1.0)
    )
    near_field_coverage = float(
        material_map.critical_region_coverage.get("mapped_near_field_coverage", 1.0)
    )
    return FieldOverlapResult(
        field_kind=kind,
        projection_method="reference_quadrature_energy_mac",
        projection_implementation=(
            "attribute-constrained tetra point location with nodal FEM interpolation "
            "at quadrature points"
        ),
        integration_method=f"tetrahedral quadrature order {quadrature_order}",
        interpolation_order=int(source.interpolation_orders.max()),
        quadrature_order=quadrature_order,
        material_weighting="epsilon tensor" if kind == "electric" else "inverse-mu tensor",
        material_map_sha256=material_map.map_sha256,
        common_mesh_sha256=reference.mesh_sha256,
        total_mac=total_mac,
        per_region_mac=per_region,
        global_mapped_volume_coverage=coverage,
        global_unmapped_volume_coverage=1.0 - coverage,
        critical_region_mapped_volume_coverage=critical_coverage,
        critical_region_unmapped_volume_coverage=1.0 - critical_coverage,
        critical_region_mapped_surface_coverage=surface_coverage,
        critical_region_unmapped_surface_coverage=1.0 - surface_coverage,
        mapped_volume=mapped_weight,
        expected_domain_volume=total_volume,
        maximum_mapping_distance=float(distance_array.max(initial=0.0)),
        average_mapping_distance=float(np.average(distance_array, weights=weights)),
        maximum_normalized_mapping_distance=float(normalized.max(initial=0.0)),
        interpolation_failures=failures,
        unmapped_critical_region_cell_count=0 if critical_coverage == 1.0 else failures,
        raw_cell_count=reference.raw_cell_count,
        ghost_cells_removed=reference.ghost_cells_removed,
        duplicate_cells_removed=reference.duplicate_cells_removed,
        unsupported_cells=reference.unsupported_cells,
        integration_cell_count=len(weights),
        raw_total_volume=reference.raw_total_volume,
        deduplicated_total_volume=total_volume,
        **_locator_result_fields(locator.metrics),
        passed_projection_quality=(
            coverage >= minimum_coverage
            and critical_coverage == 1.0
            and surface_coverage == 1.0
            and near_field_coverage == 1.0
            and float(normalized.max(initial=0.0)) <= relative_mapping_distance_limit
            and reference.unsupported_cells == 0
        ),
        problem_class=applicability.problem_class,
        ordinary_energy_mac_use=applicability.ordinary_energy_mac_use,
        promotion_allowed_from_ordinary_mac=(
            applicability.promotion_allowed_from_ordinary_mac
        ),
    )


def centroid_projected_energy_mac(
    left: Path,
    right: Path,
    *,
    kind: Literal["electric", "magnetic"],
    material_map: MaterialOverlapMap,
    relative_mapping_distance_limit: float = 0.25,
    minimum_coverage: float = 0.99,
) -> FieldOverlapResult:
    """Fast diagnostic using nearest-cell value copying."""
    from scipy.spatial import cKDTree

    reference, source = _mesh_pair(left, right, kind)
    distances, indices = cKDTree(source.centroids).query(reference.centroids, workers=-1)
    mapped = distances / np.cbrt(reference.volumes) <= relative_mapping_distance_limit
    return _result(
        reference,
        source.cell_fields[indices],
        mapped,
        distances,
        kind=kind,
        material_map=material_map,
        method="centroid_projected_energy_mac",
        implementation="nearest-cell centroid value copying (diagnostic only)",
        interpolation_order=0,
        minimum_coverage=minimum_coverage,
        distance_limit=relative_mapping_distance_limit,
    )


def reference_interpolated_energy_mac(
    left: Path,
    right: Path,
    *,
    kind: Literal["electric", "magnetic"],
    material_map: MaterialOverlapMap,
    relative_mapping_distance_limit: float = 0.25,
    minimum_coverage: float = 0.99,
    candidate_cells: int = 24,
    max_process_rss_bytes: int | None = None,
) -> FieldOverlapResult:
    """Reference point-location and linear FEM interpolation onto a common mesh."""
    reference, source = _mesh_pair(left, right, kind)
    locator = _MaterialAABBLocator(
        source, max_process_rss_bytes=max_process_rss_bytes
    )
    del candidate_cells  # Compatibility-only; the AABB locator has no arbitrary k limit.
    projected = np.zeros_like(reference.cell_fields)
    mapped = np.zeros(len(reference.centroids), dtype=bool)
    selected_distance = np.zeros(len(reference.centroids), dtype=float)
    chunk_size = 4096
    for start in range(0, len(reference.centroids), chunk_size):
        end = min(start + chunk_size, len(reference.centroids))
        candidate_batches = locator.candidate_batches(
            reference.centroids[start:end], reference.attributes[start:end]
        )
        for offset, (point, candidates) in enumerate(
            zip(reference.centroids[start:end], candidate_batches, strict=True)
        ):
            row = start + offset
            for candidate, _distance in candidates:
                barycentric = _locate_point(
                    source.interpolation_nodes[candidate],
                    int(source.interpolation_orders[candidate]),
                    point,
                )
                if barycentric is not None:
                    projected[row] = _interpolate_cell(
                        source.interpolation_nodes[candidate],
                        source.interpolation_fields[candidate],
                        int(source.interpolation_orders[candidate]),
                        barycentric,
                    )
                    mapped[row] = True
                    reconstructed = _physical_point(
                        source.interpolation_nodes[candidate],
                        int(source.interpolation_orders[candidate]),
                        barycentric,
                    )
                    selected_distance[row] = float(
                        np.linalg.norm(reconstructed - point)
                    )
                    break
    mapped &= selected_distance / np.cbrt(reference.volumes) <= relative_mapping_distance_limit
    return _result(
        reference,
        projected,
        mapped,
        selected_distance,
        kind=kind,
        material_map=material_map,
        method="reference_interpolated_energy_mac",
        implementation=(
            "attribute-constrained tetra point location with barycentric FEM interpolation"
        ),
        interpolation_order=int(source.interpolation_orders.max()),
        minimum_coverage=minimum_coverage,
        distance_limit=relative_mapping_distance_limit,
        locator_metrics=locator.metrics,
    )
