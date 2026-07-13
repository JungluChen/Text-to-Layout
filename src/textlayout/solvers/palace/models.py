"""Typed runtime records for the Palace eigenmode backend."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.simulation.mesh_convergence import SolverIdentity

ExecutionKind = Literal["executable", "container"]
ModeProblemClass = Literal[
    "closed_lossless_hermitian",
    "lossy",
    "radiative",
    "pml",
    "dispersive",
    "non_hermitian",
]
MacUse = Literal["mandatory_gate", "diagnostic_only"]


class PalaceUnavailable(RuntimeError):
    """No runnable Palace installation could be identified."""


class PalaceOutputError(RuntimeError):
    """Palace ran, but a required solver-owned output is missing or invalid."""


class PalaceCapability(BaseModel):
    """A runnable Palace executable or container and its exact identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_kind: ExecutionKind | None = None
    executable: str | None = None
    version: str | None = None
    executable_sha256: str | None = None
    container_engine: str | None = None
    container_image: str | None = None
    container_digest: str | None = None
    mpi_launcher: str | None = None
    unavailable_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _infer_execution_kind(cls, value: object) -> object:
        if not isinstance(value, dict) or value.get("execution_kind") is not None:
            return value
        updated = dict(value)
        if updated.get("executable"):
            updated["execution_kind"] = "executable"
        elif updated.get("container_engine") and updated.get("container_image"):
            updated["execution_kind"] = "container"
        return updated

    @property
    def available(self) -> bool:
        return self.execution_kind is not None and bool(
            self.executable or (self.container_engine and self.container_image)
        )

    @property
    def identified(self) -> bool:
        return bool(self.executable_sha256 or self.container_digest)

    def require(self) -> PalaceCapability:
        if not self.available:
            raise PalaceUnavailable(self.unavailable_reason or "Palace was not found")
        return self

    def solver_identity(self, command: list[str]) -> SolverIdentity:
        return SolverIdentity(
            name="Palace",
            version=self.version,
            executable_sha256=self.executable_sha256,
            container_digest=self.container_digest,
            command=list(command),
        )


class Eigenmode(BaseModel):
    """One eigenpair parsed from Palace's ``eig.csv``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=1)
    frequency_ghz: float
    frequency_imag_ghz: float | None = None
    quality_factor: float | None = None
    backward_error: float | None = None
    absolute_error: float | None = None


class ModeFieldData(BaseModel):
    """Solver-owned field and energy artifacts for one mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_index: int = Field(ge=1)
    electric_participation: dict[str, float]
    magnetic_participation: dict[str, float]
    resonator_localization: float = Field(ge=0.0, le=1.0)
    energy_normalization_error_percent: float = Field(ge=0.0)
    field_file: Path | None = None


class MacApplicability(BaseModel):
    """Whether ordinary energy MAC is valid as a promotion gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    problem_class: ModeProblemClass
    ordinary_energy_mac_use: MacUse
    promotion_allowed_from_ordinary_mac: bool
    required_method: str | None = None
    reason: str


def classify_mac_applicability(problem_class: ModeProblemClass) -> MacApplicability:
    if problem_class == "closed_lossless_hermitian":
        return MacApplicability(
            problem_class=problem_class,
            ordinary_energy_mac_use="mandatory_gate",
            promotion_allowed_from_ordinary_mac=True,
            reason="closed lossless Hermitian eigenproblem has an energy inner product",
        )
    return MacApplicability(
        problem_class=problem_class,
        ordinary_energy_mac_use="diagnostic_only",
        promotion_allowed_from_ordinary_mac=False,
        required_method="documented biorthogonal left/right eigenmode overlap",
        reason=(
            "ordinary right-eigenvector energy MAC is not a promotion gate for "
            f"{problem_class} problems"
        ),
    )


class FieldOverlapResult(BaseModel):
    """Auditable energy-weighted overlap on a common integration mesh."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_kind: Literal["electric", "magnetic"]
    projection_method: str
    projection_implementation: str
    integration_method: str
    interpolation_order: int = Field(ge=0)
    quadrature_order: int = Field(ge=1)
    material_weighting: str
    material_map_sha256: str = Field(min_length=64, max_length=64)
    common_mesh_sha256: str = Field(min_length=64, max_length=64)
    total_mac: float = Field(ge=0.0, le=1.0)
    per_region_mac: dict[str, float]
    global_mapped_volume_coverage: float = Field(ge=0.0, le=1.0)
    global_unmapped_volume_coverage: float = Field(ge=0.0, le=1.0)
    critical_region_mapped_volume_coverage: float = Field(ge=0.0, le=1.0)
    critical_region_unmapped_volume_coverage: float = Field(ge=0.0, le=1.0)
    critical_region_mapped_surface_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    critical_region_unmapped_surface_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    mapped_volume: float = Field(ge=0.0)
    expected_domain_volume: float = Field(gt=0.0)
    maximum_mapping_distance: float = Field(ge=0.0)
    average_mapping_distance: float = Field(ge=0.0)
    maximum_normalized_mapping_distance: float = Field(ge=0.0)
    interpolation_failures: int = Field(ge=0)
    unmapped_critical_region_cell_count: int = Field(ge=0)
    raw_cell_count: int = Field(ge=0)
    ghost_cells_removed: int = Field(ge=0)
    duplicate_cells_removed: int = Field(ge=0)
    unsupported_cells: int = Field(ge=0)
    integration_cell_count: int = Field(gt=0)
    raw_total_volume: float = Field(ge=0.0)
    deduplicated_total_volume: float = Field(gt=0.0)
    passed_projection_quality: bool
    problem_class: ModeProblemClass = "closed_lossless_hermitian"
    ordinary_energy_mac_use: MacUse = "mandatory_gate"
    promotion_allowed_from_ordinary_mac: bool = True

    @property
    def mapped_volume_coverage(self) -> float:
        """Compatibility name for pre-v2 callers."""
        return self.global_mapped_volume_coverage

    @property
    def unmapped_point_count(self) -> int:
        """Compatibility name for pre-v2 callers."""
        return self.interpolation_failures


Tensor3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


class MaterialOverlapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attribute: int = Field(ge=1)
    material_name: str
    permittivity: Tensor3
    permeability: Tensor3
    source: str
    model_sha256: str = Field(min_length=64, max_length=64)
    critical_region: bool = False


class MaterialOverlapMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-material-overlap.v1"
    model_sha256: str = Field(min_length=64, max_length=64)
    palace_config_sha256: str = Field(min_length=64, max_length=64)
    entries: list[MaterialOverlapEntry]
    critical_surface_attribute_ids: list[int] = Field(default_factory=list)
    critical_near_field_region_names: list[str] = Field(default_factory=list)
    critical_region_coverage: dict[str, float | int] = Field(default_factory=dict)
    map_sha256: str = Field(min_length=64, max_length=64)


class PalaceRun(BaseModel):
    """One retained Palace subprocess result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: list[str]
    return_code: int
    runtime_seconds: float = Field(ge=0.0)
    stdout_path: Path
    stderr_path: Path
    output_dir: Path
    timed_out: bool = False
    cancelled: bool = False
    input_file_hashes: dict[str, str] = Field(default_factory=dict)
    output_file_hashes: dict[str, str] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0 and not self.timed_out and not self.cancelled


class MeshLevelResult(BaseModel):
    """Measured mesh and Palace observables for one refinement level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str = Field(min_length=1)
    characteristic_length_um: float = Field(gt=0.0)
    local_characteristic_lengths_um: dict[str, float]
    element_count: int = Field(gt=0)
    degrees_of_freedom: int = Field(gt=0)
    minimum_quality: float = Field(ge=0.0, le=1.0)
    mean_quality: float = Field(ge=0.0, le=1.0)
    mesh_path: Path
    mesh_sha256: str = Field(min_length=64, max_length=64)
    mesh_runtime_seconds: float = Field(ge=0.0)
    solver_runtime_seconds: float = Field(ge=0.0)
    command: list[str]
    return_code: int
    stdout_path: Path
    stderr_path: Path
    config_path: Path
    eig_path: Path
    domain_energy_path: Path
    error_indicator_path: Path
    modes: list[Eigenmode]
    mode_fields: list[ModeFieldData]
    global_error_indicator_percent: float = Field(ge=0.0)
    output_file_hashes: dict[str, str]


class ModeMatchResult(BaseModel):
    """Identity match between adjacent mesh levels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_level: str
    to_level: str
    from_mode: int = Field(ge=1)
    to_mode: int = Field(ge=1)
    frequency_proximity: float = Field(ge=0.0, le=1.0)
    electric_field_overlap: float = Field(ge=0.0, le=1.0)
    magnetic_field_overlap: float = Field(ge=0.0, le=1.0)
    localization_similarity: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    runner_up_score: float = Field(ge=0.0, le=1.0)

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


class DomainSweepPoint(BaseModel):
    """One genuine solve used to assess computational-domain sensitivity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scale: float = Field(gt=0.0)
    frequency_ghz: float = Field(gt=0.0)
    output_file_hashes: dict[str, str]


class ConvergenceGate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    value: float | int | None = None
    threshold: float | int | None = None
    detail: str


class ConvergenceReport(BaseModel):
    """The complete gate result used to construct canonical evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gates: list[ConvergenceGate]
    tracked_mode_indices: list[int] = Field(default_factory=list)
    matches: list[ModeMatchResult] = Field(default_factory=list)
    finest_frequency_ghz: float | None = None
    converged: bool
    simulation_invalid: bool = False
    invalidation_reason: str | None = None

    @property
    def blockers(self) -> list[str]:
        return [gate.name for gate in self.gates if not gate.passed]


class PalaceBenchmarkResult(BaseModel):
    """Paths and status returned by the executable quarter-wave workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    status: str
    output_dir: Path
    capability: PalaceCapability
    fem_model_path: Path
    mesh_manifest_path: Path | None = None
    mesh_levels: list[MeshLevelResult] = Field(default_factory=list)
    evidence_path: Path | None = None
    mode_tracking_report_path: Path | None = None
    mesh_convergence_report_path: Path | None = None
    domain_convergence_report_path: Path | None = None
    engineering_report_path: Path | None = None
    reason: str | None = None
