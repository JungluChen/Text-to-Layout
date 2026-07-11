"""Deterministic Palace configuration and quarter-wave FEM model generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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
) -> FEMModel:
    """Build the physical FEM IR from the committed 6 GHz layout parameters."""
    if mesh_scale <= 0 or domain_scale <= 0:
        raise ValueError("mesh_scale and domain_scale must be positive")
    spec, params = load_quarter_wave_layout(layout_path)
    target = float(spec.target.get("frequency_ghz", 6.0))

    mesh = MeshControl(
        characteristic_length=220.0 * mesh_scale,
        min_element_quality=0.01,
        refinements=[
            LocalRefinement(
                target="cpw_conductor_edges",
                characteristic_length=6.0 * mesh_scale,
                growth_distance=60.0,
            ),
            LocalRefinement(
                target="cpw_gaps",
                characteristic_length=max(params.gap_um / 2.0, 1.0) * mesh_scale,
                growth_distance=50.0,
            ),
            LocalRefinement(
                target="coupler_gap",
                characteristic_length=max(params.coupling_gap_um / 2.0, 1.0)
                * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="open_end",
                characteristic_length=max(params.coupling_gap_um / 2.0, 1.0)
                * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="grounded_end",
                characteristic_length=max(params.gap_um / 2.0, 1.0) * mesh_scale,
                growth_distance=40.0,
            ),
            LocalRefinement(
                target="substrate_vacuum_interface",
                characteristic_length=20.0 * mesh_scale,
                growth_distance=120.0,
            ),
        ],
    )

    return FEMModel(
        name=f"quarter_wave_resonator_{target:g}ghz_domain_{domain_scale:g}",
        length_unit_m=1e-6,
        materials=[
            Material(name="silicon", permittivity=11.45, loss_tangent=1e-6),
            Material(name="vacuum", permittivity=1.0),
        ],
        volumes=[
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
        ],
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
