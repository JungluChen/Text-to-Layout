from pathlib import Path

import pytest

from textlayout.solvers.palace.models import MaterialOverlapEntry, MaterialOverlapMap
from textlayout.solvers.palace.overlap import (
    centroid_projected_energy_mac,
    reference_interpolated_energy_mac,
)
from textlayout.solvers.palace.parser import nearest_node_sampled_mac

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "palace_0_17_cross_amr"


def _material_map() -> MaterialOverlapMap:
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    entries = []
    for attribute, name, permittivity in (
        (1, "silicon", 11.45),
        (2, "silicon", 11.45),
        (4, "vacuum", 1.0),
    ):
        epsilon = (
            (permittivity, 0.0, 0.0),
            (0.0, permittivity, 0.0),
            (0.0, 0.0, permittivity),
        )
        entries.append(
            MaterialOverlapEntry(
                attribute=attribute,
                material_name=name,
                permittivity=epsilon,
                permeability=identity,
                source="resolved Palace/FEMModel fixture material map",
                model_sha256="a" * 64,
                critical_region=attribute == 1,
            )
        )
    return MaterialOverlapMap(
        model_sha256="a" * 64,
        palace_config_sha256="b" * 64,
        entries=entries,
        map_sha256="c" * 64,
    )


@pytest.mark.parametrize(
    ("kind", "expected", "nearest_expected"),
    [
        ("electric", 0.8915366893689118, 0.42471624276579323),
        ("magnetic", 0.9407440953483914, 0.7928440443664696),
    ],
)
def test_real_cross_amr_reference_projection(
    kind: str, expected: float, nearest_expected: float
) -> None:
    left, right = FIXTURE / "iteration_00.vtu", FIXTURE / "iteration_01.vtu"
    material_map = _material_map()
    diagnostic = centroid_projected_energy_mac(
        left, right, kind=kind, material_map=material_map, relative_mapping_distance_limit=1.0
    )
    reference = reference_interpolated_energy_mac(
        left, right, kind=kind, material_map=material_map, relative_mapping_distance_limit=1.0
    )
    nearest = nearest_node_sampled_mac(left, right, kind=kind)
    assert nearest == pytest.approx(nearest_expected)
    assert reference.total_mac == pytest.approx(expected)
    assert diagnostic.total_mac == pytest.approx(reference.total_mac, abs=1e-12)
    assert reference.global_mapped_volume_coverage == pytest.approx(1.0)
    assert reference.critical_region_mapped_volume_coverage == pytest.approx(1.0)
    assert reference.projection_implementation != diagnostic.projection_implementation
