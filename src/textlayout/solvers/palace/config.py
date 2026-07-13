"""Deterministic Palace configuration and quarter-wave FEM model generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.fem import (
    EigenmodeSolve,
    FEMModel,
    Interface,
    LocalRefinement,
    Material,
    MeshControl,
    MeshRegion,
    Surface,
    Volume,
    WavePort,
)
from textlayout.schemas.dsl import LayoutSpec, QuarterWaveResonatorSpec


class DomainExtents(BaseModel):
    """Independent computational-domain extents for the quarter-wave benchmark.

    ``vacuum_height_um`` bounds the refined, participation-tracked vacuum
    region above the chip; ``lid_height_um`` places the real PEC package lid.
    When the lid sits above the vacuum region a ``vacuum_far`` volume spans
    the gap, so the two heights are genuinely independent sweep parameters.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate_thickness_um: float = Field(default=300.0, gt=0)
    vacuum_height_um: float = Field(default=300.0, gt=0)
    lid_height_um: float = Field(default=450.0, gt=0)
    lateral_margin_um: float = Field(default=100.0, gt=0)

    @model_validator(mode="after")
    def _lid_above_vacuum(self) -> DomainExtents:
        if self.lid_height_um < self.vacuum_height_um:
            raise ValueError("lid_height_um must not be below vacuum_height_um")
        return self

    @property
    def has_far_vacuum(self) -> bool:
        return self.lid_height_um > self.vacuum_height_um


def deterministic_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(payload: Any, path: str | Path) -> str:
    """Write stable LF-only JSON and return its SHA-256."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = deterministic_json_bytes(payload)
    target.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def write_config(config: dict[str, Any], path: str | Path) -> str:
    return write_json(config, path)


def load_quarter_wave_layout(path: str | Path) -> tuple[LayoutSpec, QuarterWaveResonatorSpec]:
    source = Path(path)
    spec = LayoutSpec.model_validate_json(source.read_text(encoding="utf-8"))
    if spec.component != "QuarterWaveResonator":
        raise ValueError(f"expected QuarterWaveResonator, got {spec.component!r}")
    return spec, QuarterWaveResonatorSpec.model_validate(spec.parameters)


def quarter_wave_fem_model(
    layout_path: str | Path,
    *,
    mesh_scale: float = 1.0,
    domain_scale: float = 1.0,
    extents: DomainExtents | None = None,
    substrate_permittivity: float = 11.45,
) -> FEMModel:
    """Build the physical FEM IR from the committed 6 GHz layout parameters."""
    if mesh_scale <= 0 or domain_scale <= 0:
        raise ValueError("mesh_scale and domain_scale must be positive")
    if substrate_permittivity <= 1.0:
        raise ValueError("substrate_permittivity must exceed 1")
    spec, params = load_quarter_wave_layout(layout_path)
    target = float(spec.target.get("frequency_ghz", 6.0))

    mesh = MeshControl(
        characteristic_length=220.0 * mesh_scale,
        min_element_quality=0.01,
        refinements=[
            LocalRefinement(
                target="cpw_conductor_edges",
                characteristic_length=3.0 * mesh_scale,
                growth_distance=80.0,
            ),
            LocalRefinement(
                target="cpw_gaps",
                characteristic_length=max(params.gap_um / 3.0, 1.0) * mesh_scale,
                growth_distance=70.0,
            ),
            LocalRefinement(
                target="coupler_gap",
                characteristic_length=max(params.coupling_gap_um / 3.0, 1.0)
                * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="open_end",
                characteristic_length=max(params.coupling_gap_um / 3.0, 1.0)
                * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="grounded_end",
                characteristic_length=max(params.gap_um / 3.0, 1.0) * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="substrate_vacuum_interface",
                characteristic_length=10.0 * mesh_scale,
                growth_distance=160.0,
            ),
            LocalRefinement(
                target="mesh_transition_buffer",
                characteristic_length=40.0 * mesh_scale,
                growth_distance=300.0,
            ),
        ],
    )

    volumes = [
        Volume(
            name="substrate_resonator",
            attribute=1,
            material="silicon",
            role="substrate",
            postprocess_energy=True,
        ),
        Volume(
            name="substrate_outer",
            attribute=2,
            material="silicon",
            role="substrate",
            postprocess_energy=True,
        ),
        Volume(
            name="vacuum_resonator",
            attribute=3,
            material="vacuum",
            role="vacuum",
            postprocess_energy=True,
        ),
        Volume(
            name="vacuum_outer",
            attribute=4,
            material="vacuum",
            role="vacuum",
            postprocess_energy=True,
        ),
    ]
    if extents is not None and extents.has_far_vacuum:
        volumes.append(
            Volume(
                name="vacuum_far",
                attribute=5,
                material="vacuum",
                role="vacuum",
                postprocess_energy=True,
            )
        )
    name = (
        f"quarter_wave_resonator_{target:g}ghz_domain_{domain_scale:g}"
        if extents is None
        else (
            f"quarter_wave_resonator_{target:g}ghz"
            f"_sub{extents.substrate_thickness_um:g}"
            f"_vac{extents.vacuum_height_um:g}"
            f"_lid{extents.lid_height_um:g}"
            f"_lat{extents.lateral_margin_um:g}"
        )
    )
    if substrate_permittivity != 11.45:
        name += f"_eps{substrate_permittivity:g}"
    return FEMModel(
        name=name,
        length_unit_m=1e-6,
        materials=[
            Material(name="silicon", permittivity=substrate_permittivity, loss_tangent=1e-6),
            Material(name="vacuum", permittivity=1.0),
        ],
        volumes=volumes,
        surfaces=[
            Surface(
                name="superconducting_metal",
                attribute=10,
                kind="pec",
                role="superconducting_metal",
            ),
            Surface(
                name="package_walls",
                attribute=11,
                kind="pec",
                role="package_wall",
            ),
            Surface(name="lid", attribute=12, kind="pec", role="lid"),
        ],
        interfaces=[
            Interface(
                name="substrate_vacuum_interface",
                attribute=20,
                between=("substrate_resonator", "vacuum_resonator"),
                thickness_nm=2.0,
                permittivity=4.0,
                loss_tangent=1e-3,
            ),
            Interface(
                name="outer_substrate_vacuum_interface",
                attribute=21,
                between=("substrate_outer", "vacuum_outer"),
                thickness_nm=2.0,
                permittivity=4.0,
                loss_tangent=1e-3,
            ),
        ],
        wave_ports=[
            WavePort(name="RF_IN", index=1, attribute=30, mode_count=1),
            WavePort(name="RF_OUT", index=2, attribute=31, mode_count=1),
        ],
        mesh_regions=[
            MeshRegion(name="cpw_conductor_edges", kind="conductor_edge", dimension=1),
            MeshRegion(name="cpw_gaps", kind="cpw_gap", dimension=2),
            MeshRegion(name="coupler_gap", kind="coupler_gap", dimension=2),
            MeshRegion(name="open_end", kind="open_end", dimension=1),
            MeshRegion(name="mesh_transition_buffer", kind="custom", dimension=3),
            MeshRegion(name="grounded_end", kind="grounded_end", dimension=1),
            MeshRegion(
                name="substrate_vacuum_interface",
                kind="dielectric_interface",
                dimension=2,
            ),
        ],
        mesh=mesh,
        eigenmode=EigenmodeSolve(
            mode_count=4,
            target_frequency_ghz=max(target * 0.45, 0.001),
            tolerance=1e-9,
            element_order=1,
            linear_tolerance=1e-9,
            linear_max_iterations=1000,
        ),
    )


def build_eigenmode_config(
    model: FEMModel,
    *,
    mesh_filename: str,
    output_dir: str,
    activate_ports: bool = False,
) -> dict[str, Any]:
    """Project one FEM model into a Palace eigenmode run configuration."""
    config = model.to_palace_eigenmode_config(
        mesh_filename=mesh_filename, output_dir=output_dir
    )
    problem = config["Problem"]
    problem["OutputFormats"] = {"GridFunction": True, "Paraview": True}
    config["Solver"]["Eigenmode"]["Save"] = model.eigenmode.mode_count
    if not activate_ports:
        boundaries = config["Boundaries"]
        inactive_attributes = [port.attribute for port in model.lumped_ports]
        inactive_attributes.extend(port.attribute for port in model.wave_ports)
        boundaries.pop("LumpedPort", None)
        boundaries.pop("WavePort", None)
        if inactive_attributes:
            pec = boundaries.setdefault("PEC", {"Attributes": []})
            pec["Attributes"] = sorted(
                set(pec.get("Attributes", [])) | set(inactive_attributes)
            )
    return config


def write_fem_model(model: FEMModel, path: str | Path) -> str:
    return write_json(model.model_dump(mode="json"), path)
