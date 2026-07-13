import pytest

from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
from textlayout.solvers.palace.config import build_eigenmode_config, quarter_wave_fem_model
from textlayout.solvers.palace.models import PalaceOutputError
from textlayout.solvers.palace.overlap import build_material_overlap_map


def test_material_map_is_resolved_from_model_and_palace_config() -> None:
    model = quarter_wave_fem_model(DEFAULT_LAYOUT)
    config = build_eigenmode_config(model, mesh_filename="mesh.msh", output_dir="postpro")
    material_map = build_material_overlap_map(model, config)
    assert {entry.attribute for entry in material_map.entries} == {1, 2, 3, 4}
    assert {entry.attribute for entry in material_map.entries if entry.critical_region} == {1, 3}
    assert material_map.critical_region_coverage["mapped_volume_coverage"] == pytest.approx(1.0)
    assert material_map.critical_region_coverage["mapped_surface_coverage"] == pytest.approx(1.0)
    assert material_map.critical_region_coverage["mapped_near_field_coverage"] == pytest.approx(1.0)
    assert material_map.entries[0].permittivity[0][0] == pytest.approx(11.45)
    assert len(material_map.map_sha256) == 64


def test_material_map_fails_closed_for_missing_assignment() -> None:
    model = quarter_wave_fem_model(DEFAULT_LAYOUT)
    config = build_eigenmode_config(model, mesh_filename="mesh.msh", output_dir="postpro")
    config["Domains"]["Materials"] = config["Domains"]["Materials"][1:]
    with pytest.raises(PalaceOutputError, match="attribute 1 has no Palace material"):
        build_material_overlap_map(model, config)


def test_material_map_hash_changes_with_model() -> None:
    model_a = quarter_wave_fem_model(DEFAULT_LAYOUT, substrate_permittivity=11.45)
    model_b = quarter_wave_fem_model(DEFAULT_LAYOUT, substrate_permittivity=11.7)
    map_a = build_material_overlap_map(
        model_a, build_eigenmode_config(model_a, mesh_filename="mesh.msh", output_dir="postpro")
    )
    map_b = build_material_overlap_map(
        model_b, build_eigenmode_config(model_b, mesh_filename="mesh.msh", output_dir="postpro")
    )
    assert map_a.map_sha256 != map_b.map_sha256
