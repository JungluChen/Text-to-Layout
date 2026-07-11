"""Typed runtime records for the Palace eigenmode backend."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.simulation.mesh_convergence import SolverIdentity

ExecutionKind = Literal["executable", "container"]


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
