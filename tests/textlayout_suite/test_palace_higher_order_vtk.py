from pathlib import Path

import pytest

from textlayout.solvers.palace.models import MaterialOverlapEntry, MaterialOverlapMap
from textlayout.solvers.palace.overlap import (
    _integration_mesh,
    reference_interpolated_energy_mac,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "palace_0_17_p2_tetra"


def _cavity_material_map() -> MaterialOverlapMap:
    scalar_identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    permittivity = ((2.08, 0.0, 0.0), (0.0, 2.08, 0.0), (0.0, 0.0, 2.08))
    return MaterialOverlapMap(
        model_sha256="a" * 64,
        palace_config_sha256="b" * 64,
        entries=[
            MaterialOverlapEntry(
                attribute=1,
                material_name="cavity_dielectric",
                permittivity=permittivity,
                permeability=scalar_identity,
                source="Palace resolved configuration fixture",
                model_sha256="a" * 64,
                critical_region=True,
            )
        ],
        map_sha256="c" * 64,
    )


@pytest.mark.parametrize("kind", ["electric", "magnetic"])
def test_real_palace_p2_vtk71_uses_quadratic_interpolation(kind: str) -> None:
    field = FIXTURE / "data.pvtu"
    mesh = _integration_mesh(field, kind)
    assert mesh.raw_cell_count == 288
    assert set(mesh.interpolation_orders) == {2}
    assert all(len(nodes) == 10 for nodes in mesh.interpolation_nodes)
    result = reference_interpolated_energy_mac(
        field,
        field,
        kind=kind,
        material_map=_cavity_material_map(),
        relative_mapping_distance_limit=1.0,
    )
    assert result.total_mac == pytest.approx(1.0)
    assert result.interpolation_order == 2
    assert result.global_mapped_volume_coverage == pytest.approx(1.0)
    assert result.critical_region_mapped_volume_coverage == pytest.approx(1.0)
