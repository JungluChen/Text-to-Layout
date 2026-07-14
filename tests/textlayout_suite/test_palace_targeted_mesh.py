from __future__ import annotations

from pathlib import Path

from textlayout.solvers.palace.config import (
    quarter_wave_fem_model,
    TargetedMeshControls,
)


ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "examples" / "showcase" / "05_quarter_wave_resonator_6ghz" / "layout.json"


def test_targeted_mesh_controls_project_to_independent_fem_regions() -> None:
    controls = TargetedMeshControls(
        bulk_mesh_size=180.0,
        conductor_edge_mesh_size=2.5,
        cpw_gap_mesh_size=2.0,
        coupling_gap_mesh_size=1.0,
        open_end_mesh_size=1.25,
        grounded_end_mesh_size=1.5,
        interface_normal_mesh_size=6.0,
        transition_mesh_size=30.0,
    )
    model = quarter_wave_fem_model(LAYOUT, targeted_mesh=controls)
    sizes = {
        refinement.target: refinement.characteristic_length
        for refinement in model.mesh.refinements
    }
    assert model.mesh.characteristic_length == 180.0
    assert sizes["cpw_gaps"] == 2.0
    assert sizes["coupling_gap"] == 1.0
    assert sizes["open_end"] == 1.25
    assert sizes["grounded_end"] == 1.5
    assert sizes["substrate_vacuum_interface"] == 6.0
    assert sizes["metal_substrate_interface"] == 6.0
    assert sizes["metal_air_interface"] == 6.0


def test_targeted_mesh_scaling_preserves_independent_ratios() -> None:
    model = quarter_wave_fem_model(
        LAYOUT,
        mesh_scale=0.5,
        targeted_mesh=TargetedMeshControls(
            bulk_mesh_size=200.0,
            cpw_gap_mesh_size=4.0,
            coupling_gap_mesh_size=2.0,
            open_end_mesh_size=3.0,
            grounded_end_mesh_size=2.0,
        ),
    )
    sizes = {
        refinement.target: refinement.characteristic_length
        for refinement in model.mesh.refinements
    }
    assert model.mesh.characteristic_length == 100.0
    assert sizes["cpw_gaps"] == 2.0
    assert sizes["coupling_gap"] == 1.0
    assert sizes["open_end"] == 1.5
    assert sizes["grounded_end"] == 1.0
