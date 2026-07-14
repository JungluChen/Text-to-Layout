import numpy as np
import pytest

from textlayout.solvers.palace.models import PalaceOutputError
from textlayout.solvers.palace.overlap import (
    _VTK_P2_TETRA_EDGES,
    _cell_volume,
    _geometry_jacobian,
    _interpolate_cell,
    _locate_point,
    _physical_point,
)


def _p2_nodes(*, curved: bool = False) -> np.ndarray:
    corners = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    edges = np.asarray(
        [(corners[left] + corners[right]) / 2 for left, right in _VTK_P2_TETRA_EDGES]
    )
    if curved:
        edges[3] += np.asarray([0.08, 0.0, 0.0])
    return np.vstack((corners, edges))


def _values(nodes: np.ndarray, function) -> np.ndarray:
    scalar = np.asarray([function(point) for point in nodes])
    return np.column_stack((scalar, 2.0 * scalar, -scalar)).astype(np.complex128)


def test_p2_constant_field_exactness() -> None:
    nodes = _p2_nodes()
    values = np.tile(np.asarray([1.0, 2.0, 3.0]), (10, 1)).astype(np.complex128)
    barycentric = np.asarray([0.1, 0.2, 0.3, 0.4])
    assert _interpolate_cell(nodes, values, 2, barycentric) == pytest.approx(values[0])


def test_p2_linear_field_exactness() -> None:
    nodes = _p2_nodes(curved=True)

    def function(point: np.ndarray) -> float:
        return 1.0 + 2.0 * point[0] - point[1] + 0.5 * point[2]

    barycentric = np.asarray([0.15, 0.25, 0.35, 0.25])
    physical = _physical_point(nodes, 2, barycentric)
    actual = _interpolate_cell(nodes, _values(nodes, function), 2, barycentric)
    expected = function(physical)
    assert actual == pytest.approx([expected, 2.0 * expected, -expected])


def test_p2_quadratic_field_improves_over_linear() -> None:
    nodes = _p2_nodes()

    def function(point: np.ndarray) -> float:
        return point[0] ** 2 + 2.0 * point[1] * point[2]

    barycentric = np.asarray([0.1, 0.2, 0.3, 0.4])
    physical = _physical_point(nodes, 2, barycentric)
    expected = function(physical)
    quadratic = _interpolate_cell(nodes, _values(nodes, function), 2, barycentric)[0].real
    linear = _interpolate_cell(nodes, _values(nodes, function), 1, barycentric)[0].real
    assert quadratic == pytest.approx(expected, abs=1e-14)
    assert abs(quadratic - expected) < abs(linear - expected)


def test_p2_curved_geometry_and_point_inversion() -> None:
    nodes = _p2_nodes(curved=True)
    barycentric = np.asarray([0.2, 0.3, 0.1, 0.4])
    point = _physical_point(nodes, 2, barycentric)
    assert point != pytest.approx(_physical_point(nodes[:4], 1, barycentric))
    recovered = _locate_point(nodes, 2, point)
    assert recovered == pytest.approx(barycentric, abs=1e-9)
    assert _locate_point(nodes, 2, np.asarray([2.0, 2.0, 2.0])) is None


def test_p2_positive_jacobian_and_volume() -> None:
    nodes = _p2_nodes(curved=True)
    jacobian = _geometry_jacobian(nodes, 2, np.asarray([0.2, 0.3, 0.1]))
    assert np.linalg.det(jacobian) > 0.0
    assert _cell_volume(nodes, 2) > 0.0


def test_p2_degenerate_cell_rejected() -> None:
    nodes = _p2_nodes()
    nodes[:, 2] = 0.0
    with pytest.raises(PalaceOutputError, match="non-positive"):
        _cell_volume(nodes, 2)
