"""The typed FEM model, and the two projections that must never disagree.

The grounding test: build the cavity as an FEMModel, project it onto a Palace
configuration, and require the result to equal the JSON that a *real* Palace 0.16
accepted and solved. A schema that cannot reproduce a config the solver already
consumed is a schema that does not describe the solver.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.fem import (
    CriticalRegion,
    EigenmodeSolve,
    FEMModel,
    Interface,
    LocalRefinement,
    LumpedPort,
    Material,
    MeshControl,
    MeshRegion,
    Surface,
    Volume,
    WavePort,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = REPO_ROOT / "examples" / "solver_benchmarks" / "palace_cavity_te101" / "configs"

VACUUM = Material(name="vacuum", permittivity=1.0, permeability=1.0)
SILICON = Material(name="silicon", permittivity=11.45, loss_tangent=1e-6)


def _cavity(**overrides) -> FEMModel:
    payload = {
        "name": "pec_cavity",
        "length_unit_m": 1e-3,
        "materials": [VACUUM],
        "volumes": [Volume(name="cavity", attribute=1, material="vacuum", postprocess_energy=True)],
        "surfaces": [Surface(name="walls", attribute=2, kind="pec")],
        "mesh": MeshControl(characteristic_length=1.472120),
        "eigenmode": EigenmodeSolve(
            mode_count=2, target_frequency_ghz=3.0, tolerance=1e-10, element_order=1
        ),
    }
    payload.update(overrides)
    return FEMModel(**payload)  # type: ignore[arg-type]


def _two_domain() -> FEMModel:
    return FEMModel(
        name="pec_cavity_split",
        length_unit_m=1e-3,
        materials=[VACUUM],
        volumes=[
            Volume(name="near", attribute=1, material="vacuum", postprocess_energy=True),
            Volume(name="far", attribute=2, material="vacuum", postprocess_energy=True),
        ],
        surfaces=[Surface(name="walls", attribute=3, kind="pec")],
        mesh=MeshControl(characteristic_length=1.104090),
        eigenmode=EigenmodeSolve(
            mode_count=3, target_frequency_ghz=3.0, tolerance=1e-10, element_order=1
        ),
    )


class TestReproducesAConfigPalaceAccepted:
    """Ground truth: these JSON files were solved by a real Palace 0.16."""

    def test_the_single_domain_cavity_config_is_reproduced_exactly(self) -> None:
        committed = json.loads((CONFIGS / "cavity_N24.json").read_text(encoding="utf-8"))
        projected = _cavity().to_palace_eigenmode_config(
            mesh_filename="cavN24.msh", output_dir="pp24"
        )
        assert projected == committed

    def test_the_two_domain_cavity_config_is_reproduced_exactly(self) -> None:
        committed = json.loads((CONFIGS / "twodomain_N32.json").read_text(encoding="utf-8"))
        projected = _two_domain().to_palace_eigenmode_config(
            mesh_filename="cav2dom_N32.msh", output_dir="pp32"
        )
        assert projected == committed

    def test_the_projection_is_deterministic(self) -> None:
        first = _cavity().to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")
        second = _cavity().to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


class TestAttributesCannotCollide:
    """One attribute space per dimension; the model is the only place tags are set."""

    def test_two_volumes_may_not_share_an_attribute(self) -> None:
        with pytest.raises(ValidationError, match="volume attributes must be unique"):
            _cavity(
                volumes=[
                    Volume(name="a", attribute=1, material="vacuum"),
                    Volume(name="b", attribute=1, material="vacuum"),
                ]
            )

    def test_a_port_may_not_reuse_a_surface_attribute(self) -> None:
        """A port that overwrote a wall's tag would silently unbind the cavity."""
        with pytest.raises(ValidationError, match="surface/interface/port attributes"):
            _cavity(
                lumped_ports=[
                    LumpedPort(name="p1", index=1, attribute=2, direction="+Z")
                ]
            )

    def test_an_interface_may_not_reuse_a_surface_attribute(self) -> None:
        with pytest.raises(ValidationError, match="surface/interface/port attributes"):
            _cavity(
                volumes=[
                    Volume(name="sub", attribute=1, material="vacuum"),
                    Volume(name="air", attribute=2, material="vacuum"),
                ],
                interfaces=[
                    Interface(
                        name="ms", attribute=2, between=("sub", "air"),
                        thickness_nm=2.0, permittivity=10.0, loss_tangent=1e-3,
                    )
                ],
            )

    def test_ports_may_not_share_an_index(self) -> None:
        with pytest.raises(ValidationError, match="port indices must be unique"):
            _cavity(
                lumped_ports=[LumpedPort(name="p1", index=1, attribute=3, direction="+Z")],
                wave_ports=[WavePort(name="w1", index=1, attribute=4)],
            )


class TestPhysicalCoherence:
    def test_a_volume_must_name_a_material_that_exists(self) -> None:
        with pytest.raises(ValidationError, match="which is not defined"):
            _cavity(volumes=[Volume(name="cavity", attribute=1, material="unobtainium")])

    def test_an_interface_must_separate_volumes_that_exist(self) -> None:
        with pytest.raises(ValidationError, match="separates unknown volume"):
            _cavity(
                interfaces=[
                    Interface(
                        name="ms", attribute=9, between=("cavity", "ghost"),
                        thickness_nm=2.0, permittivity=10.0, loss_tangent=1e-3,
                    )
                ]
            )

    def test_an_interface_may_not_separate_a_volume_from_itself(self) -> None:
        with pytest.raises(ValidationError, match="from itself"):
            Interface(
                name="ms", attribute=9, between=("cavity", "cavity"),
                thickness_nm=2.0, permittivity=10.0, loss_tangent=1e-3,
            )

    def test_an_eigenmode_problem_needs_a_bounding_surface(self) -> None:
        """Symmetry planes alone leave the domain unbounded."""
        with pytest.raises(ValidationError, match="needs a bounding surface"):
            _cavity(surfaces=[Surface(name="sym", attribute=2, kind="pmc_symmetry")])

    def test_a_model_needs_a_volume(self) -> None:
        with pytest.raises(ValidationError, match="at least one volume"):
            _cavity(volumes=[])

    def test_a_lossy_sheet_with_no_loss_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires resistance_ohm_per_square"):
            Surface(name="metal", attribute=1, kind="impedance")

    def test_a_resistance_on_a_pec_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="meaningless for kind"):
            Surface(name="metal", attribute=1, kind="pec", resistance_ohm_per_square=0.1)

    def test_a_refinement_must_target_a_named_entity(self) -> None:
        with pytest.raises(ValidationError, match="unknown entity"):
            _cavity(
                mesh=MeshControl(
                    characteristic_length=1.0,
                    refinements=[
                        LocalRefinement(
                            target="cpw_gap", characteristic_length=0.1, growth_distance=0.5
                        )
                    ],
                )
            )

    def test_critical_surface_region_may_not_be_represented_as_volume(self) -> None:
        with pytest.raises(ValidationError, match="may not be represented as a volume"):
            _cavity(
                critical_regions=[
                    CriticalRegion(
                        name="metal_substrate_interface",
                        kind="metal_substrate_interface",
                        region_type="surface",
                        attribute_ids=[1],
                        surface_attribute_ids=[2],
                    )
                ]
            )

    def test_critical_regions_must_name_declared_surfaces_and_near_fields(self) -> None:
        with pytest.raises(ValidationError, match="surface-region attributes"):
            _cavity(
                critical_regions=[
                    CriticalRegion(
                        name="missing_interface",
                        kind="metal_air_interface",
                        region_type="surface",
                        surface_attribute_ids=[99],
                    )
                ]
            )
        with pytest.raises(ValidationError, match="near-field regions"):
            _cavity(
                critical_regions=[
                    CriticalRegion(
                        name="missing_junction_box",
                        kind="junction_near_field",
                        region_type="near_field",
                        mesh_region_names=["jj_box"],
                    )
                ]
            )


class TestProjections:
    def test_physical_groups_cover_every_declared_entity(self) -> None:
        model = _cavity(
            volumes=[
                Volume(name="sub", attribute=1, material="silicon"),
                Volume(name="air", attribute=2, material="vacuum"),
            ],
            materials=[VACUUM, SILICON],
            interfaces=[
                Interface(
                    name="sa", attribute=3, between=("sub", "air"),
                    thickness_nm=2.0, permittivity=4.0, loss_tangent=1e-3,
                )
            ],
            surfaces=[Surface(name="walls", attribute=4, kind="pec")],
        )
        groups = model.physical_groups()
        assert groups[3] == [(1, "sub"), (2, "air")]
        assert groups[2] == [(4, "walls"), (3, "sa")]

    def test_critical_region_coverage_reports_volume_surface_and_near_field(self) -> None:
        model = _cavity(
            volumes=[
                Volume(name="left_gap", attribute=1, material="vacuum"),
                Volume(name="right_gap", attribute=2, material="vacuum"),
            ],
            surfaces=[Surface(name="grounded_end", attribute=3, kind="pec")],
            mesh_regions=[
                MeshRegion(name="junction_box", kind="custom", dimension=3),
            ],
            critical_regions=[
                CriticalRegion(
                    name="left_gap",
                    kind="left_cpw_gap",
                    region_type="volume",
                    volume_attribute_ids=[1],
                ),
                CriticalRegion(
                    name="grounded_end",
                    kind="resonator_grounded_end",
                    region_type="surface",
                    surface_attribute_ids=[3],
                ),
                CriticalRegion(
                    name="junction_box",
                    kind="junction_near_field",
                    region_type="near_field",
                    mesh_region_names=["junction_box"],
                ),
            ],
        )
        coverage = model.critical_region_coverage()
        assert coverage["mapped_volume_coverage"] == pytest.approx(1.0)
        assert coverage["mapped_surface_coverage"] == pytest.approx(1.0)
        assert coverage["mapped_near_field_coverage"] == pytest.approx(1.0)

    def test_energy_regions_are_indexed_in_declaration_order(self) -> None:
        assert _two_domain().energy_regions() == {1: "near", 2: "far"}

    def test_a_volume_without_energy_postprocessing_produces_no_participation(self) -> None:
        model = _cavity(volumes=[Volume(name="cavity", attribute=1, material="vacuum")])
        assert model.energy_regions() == {}
        config = model.to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")
        assert "Postprocessing" not in config["Domains"]

    def test_a_lossy_material_emits_a_loss_tangent(self) -> None:
        model = _cavity(
            materials=[SILICON],
            volumes=[Volume(name="cavity", attribute=1, material="silicon")],
        )
        config = model.to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")
        assert config["Domains"]["Materials"][0]["LossTan"] == pytest.approx(1e-6)

    def test_absorbing_and_impedance_boundaries_project(self) -> None:
        model = _cavity(
            surfaces=[
                Surface(name="walls", attribute=2, kind="pec"),
                Surface(name="open", attribute=3, kind="absorbing"),
                Surface(name="metal", attribute=4, kind="impedance", resistance_ohm_per_square=0.05),
            ]
        )
        boundaries = model.to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")[
            "Boundaries"
        ]
        assert boundaries["PEC"]["Attributes"] == [2]
        assert boundaries["Absorbing"]["Attributes"] == [3]
        assert boundaries["Impedance"] == [{"Attributes": [4], "Rs": 0.05}]

    def test_ports_project_with_their_indices(self) -> None:
        model = _cavity(
            lumped_ports=[LumpedPort(name="p1", index=1, attribute=3, direction="+Z")],
            wave_ports=[WavePort(name="w1", index=2, attribute=4, mode_count=1)],
        )
        boundaries = model.to_palace_eigenmode_config(mesh_filename="m.msh", output_dir="o")[
            "Boundaries"
        ]
        assert boundaries["LumpedPort"][0]["Index"] == 1
        assert boundaries["WavePort"][0]["Index"] == 2


class TestRefinement:
    def test_refining_scales_every_length_so_levels_stay_nested(self) -> None:
        model = _cavity(
            mesh=MeshControl(
                characteristic_length=4.0,
                refinements=[
                    LocalRefinement(target="walls", characteristic_length=0.4, growth_distance=2.0)
                ],
            )
        )
        finer = model.refined(0.5)
        assert finer.mesh.characteristic_length == 2.0
        assert finer.mesh.refinements[0].characteristic_length == 0.2
        # Growth distance is geometry, not discretisation: it must not scale.
        assert finer.mesh.refinements[0].growth_distance == 2.0

    def test_refining_leaves_the_geometry_untouched(self) -> None:
        model = _cavity()
        assert model.refined(0.5).volumes == model.volumes

    def test_a_non_positive_factor_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="factor must be positive"):
            _cavity().refined(0.0)

    def test_the_formal_order_follows_the_element_order(self) -> None:
        """Nedelec order p converges in the eigenvalue at h^(2p)."""
        assert EigenmodeSolve(target_frequency_ghz=6.0, element_order=1).formal_order == 2.0
        assert EigenmodeSolve(target_frequency_ghz=6.0, element_order=2).formal_order == 4.0
