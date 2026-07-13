from __future__ import annotations

from pathlib import Path

import meshio
import numpy as np
import pytest

from textlayout.solvers.palace.models import MaterialOverlapEntry, MaterialOverlapMap
from textlayout.solvers.palace.overlap import (
    centroid_projected_energy_mac,
    reference_interpolated_energy_mac,
)


def _material_map() -> MaterialOverlapMap:
    tensor = ((2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0))
    entry = MaterialOverlapEntry(
        attribute=1,
        material_name="test",
        permittivity=tensor,
        permeability=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        source="test fixture",
        model_sha256="a" * 64,
        critical_region=True,
    )
    return MaterialOverlapMap(
        model_sha256="a" * 64,
        palace_config_sha256="b" * 64,
        entries=[entry],
        map_sha256="c" * 64,
    )


def _write_tetra_field(
    path: Path,
    points: np.ndarray,
    tetra: np.ndarray,
    electric: np.ndarray,
    magnetic: np.ndarray | None = None,
) -> None:
    magnetic_values = electric if magnetic is None else magnetic
    meshio.write(
        path,
        meshio.Mesh(
            points=points,
            cells=[("tetra", tetra)],
            point_data={
                "E_real": electric.real,
                "E_imag": electric.imag,
                "B_real": magnetic_values.real,
                "B_imag": magnetic_values.imag,
            },
            cell_data={"attribute": [np.ones(len(tetra), dtype=np.int32)]},
        ),
        binary=True,
    )


def _single_tetra() -> tuple[np.ndarray, np.ndarray]:
    return np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float), np.asarray(
        [[0, 1, 2, 3]], int
    )


@pytest.mark.parametrize("scale", [2.5 + 0j, np.exp(1j * 0.73)])
def test_weighted_mac_is_invariant_to_amplitude_and_global_phase(
    tmp_path: Path, scale: complex
) -> None:
    points, tetra = _single_tetra()
    field = np.tile(np.asarray([1 + 2j, 2 - 1j, 0.5j]), (4, 1))
    left, right = tmp_path / "left.vtu", tmp_path / "right.vtu"
    _write_tetra_field(left, points, tetra, field)
    _write_tetra_field(right, points[::-1], np.asarray([[3, 2, 1, 0]]), field[::-1] * scale)
    result = reference_interpolated_energy_mac(
        left, right, kind="electric", material_map=_material_map(), relative_mapping_distance_limit=1
    )
    assert result.total_mac == pytest.approx(1.0)
    assert result.mapped_volume_coverage == pytest.approx(1.0)


def test_weighted_mac_rejects_orthogonal_fields(tmp_path: Path) -> None:
    points, tetra = _single_tetra()
    ex, ey = np.tile([1 + 0j, 0, 0], (4, 1)), np.tile([0 + 0j, 1, 0], (4, 1))
    left, right = tmp_path / "left.vtu", tmp_path / "right.vtu"
    _write_tetra_field(left, points, tetra, ex)
    _write_tetra_field(right, points, tetra, ey)
    assert centroid_projected_energy_mac(
        left, right, kind="electric", material_map=_material_map()
    ).total_mac == pytest.approx(0)


def test_weighted_mac_detects_local_perturbation(tmp_path: Path) -> None:
    points, tetra = _single_tetra()
    base = np.tile([1 + 0j, 0, 0], (4, 1))
    changed = base.copy()
    changed[0] = [0, 2, 0]
    left, right = tmp_path / "left.vtu", tmp_path / "right.vtu"
    _write_tetra_field(left, points, tetra, base)
    _write_tetra_field(right, points, tetra, changed)
    assert centroid_projected_energy_mac(
        left, right, kind="electric", material_map=_material_map()
    ).total_mac < 1


def test_weighted_mac_reports_mapping_distance_and_partial_domain(tmp_path: Path) -> None:
    points, tetra = _single_tetra()
    field = np.tile([1 + 0j, 0, 0], (4, 1))
    left, right = tmp_path / "left.vtu", tmp_path / "right.vtu"
    _write_tetra_field(left, points, tetra, field)
    _write_tetra_field(right, points + [10, 0, 0], tetra, field)
    with pytest.raises(Exception, match="mapped no integration cells"):
        reference_interpolated_energy_mac(
            left,
            right,
            kind="electric",
            material_map=_material_map(),
            relative_mapping_distance_limit=0.1,
        )


def test_real_palace_0_17_compacted_parallel_fixture() -> None:
    fixture = Path("tests/fixtures/palace_0_17_field/data.pvtu")
    result = reference_interpolated_energy_mac(
        fixture, fixture, kind="electric", material_map=_material_map()
    )
    assert result.total_mac == pytest.approx(1.0)
    assert result.integration_cell_count == 2
    assert result.mapped_volume_coverage == pytest.approx(1.0)
