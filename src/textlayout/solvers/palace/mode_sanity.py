"""Physically grounded longitudinal checks for quarter-wave eigenmodes."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.solvers.palace.models import PalaceOutputError


class ResonatorEndpointMetadata(BaseModel):
    """Physical endpoint coordinates and local dimensions along the centreline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grounded_coordinate: float
    open_coordinate: float
    local_mesh_size: float = Field(gt=0.0)
    conductor_dimension: float = Field(gt=0.0)

    @model_validator(mode="after")
    def _distinct_endpoints(self) -> ResonatorEndpointMetadata:
        if self.grounded_coordinate == self.open_coordinate:
            raise ValueError("grounded and open endpoint coordinates must differ")
        return self

    @property
    def physical_length(self) -> float:
        return abs(self.open_coordinate - self.grounded_coordinate)


class QuarterWaveSanitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bins: int = Field(default=20, ge=8)
    endpoint_window_fraction: float = Field(default=0.10, gt=0.0, le=0.25)
    endpoint_exclusion_mesh_factor: float = Field(default=1.5, ge=0.0)
    endpoint_exclusion_conductor_factor: float = Field(default=0.5, ge=0.0)
    minimum_endpoint_ratio: float = Field(default=4.0, gt=1.0)
    maximum_node_residual: float = Field(default=0.25, ge=0.0, lt=1.0)
    minimum_profile_correlation: float = Field(default=0.90, ge=-1.0, le=1.0)
    minimum_phase_progression_score: float = Field(default=0.90, ge=0.0, le=1.0)


class QuarterWaveSanityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: str = Field(
        default="textlayout.palace-quarter-wave-sanity.v2", alias="schema"
    )
    selected_sample_count: int = Field(ge=1)
    bin_count: int = Field(ge=8)
    physical_length: float = Field(gt=0.0)
    grounded_coordinate: float
    open_coordinate: float
    coordinate_direction: int
    endpoint_exclusion_length: float = Field(ge=0.0)
    electric_profile: list[float]
    magnetic_profile: list[float]
    electric_open_to_ground_ratio: float = Field(ge=0.0)
    magnetic_ground_to_open_ratio: float = Field(ge=0.0)
    electric_node_residual: float = Field(ge=0.0)
    magnetic_node_residual: float = Field(ge=0.0)
    electric_quarter_wave_profile_correlation: float = Field(ge=-1.0, le=1.0)
    magnetic_quarter_wave_profile_correlation: float = Field(ge=-1.0, le=1.0)
    quarter_wave_profile_correlation: float = Field(ge=-1.0, le=1.0)
    electric_phase_progression_score: float = Field(ge=0.0, le=1.0)
    magnetic_phase_progression_score: float = Field(ge=0.0, le=1.0)
    phase_progression_score: float = Field(ge=0.0, le=1.0)
    electric_antinode_near_open_end: bool
    electric_node_near_grounded_end: bool
    magnetic_antinode_near_grounded_end: bool
    magnetic_node_near_open_end: bool
    profile_shape_passed: bool
    phase_progression_passed: bool
    passed: bool
    failure_reasons: list[str]


def _finite_vector(
    values: Sequence[float] | npt.NDArray[np.float64], *, name: str
) -> npt.NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not len(array) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a nonempty finite one-dimensional array")
    return array


def _complex_vector(
    values: Sequence[complex] | npt.NDArray[np.complex128], *, name: str
) -> npt.NDArray[np.complex128]:
    array = np.asarray(values, dtype=np.complex128)
    if array.ndim != 1 or not len(array) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a nonempty finite one-dimensional array")
    return array


def _correlation(values: npt.NDArray[np.float64], expected: npt.NDArray[np.float64]) -> float:
    if np.std(values) <= np.finfo(float).eps:
        return 0.0
    result = float(np.corrcoef(values, expected)[0, 1])
    return result if np.isfinite(result) else 0.0


def _profile(
    positions: npt.NDArray[np.float64],
    phasors: npt.NDArray[np.complex128],
    weights: npt.NDArray[np.float64],
    *,
    endpoints: ResonatorEndpointMetadata,
    settings: QuarterWaveSanitySettings,
) -> tuple[npt.NDArray[np.float64], float, float, float, int]:
    direction = 1.0 if endpoints.open_coordinate > endpoints.grounded_coordinate else -1.0
    normalized = direction * (positions - endpoints.grounded_coordinate) / endpoints.physical_length
    exclusion = max(
        settings.endpoint_exclusion_mesh_factor * endpoints.local_mesh_size,
        settings.endpoint_exclusion_conductor_factor * endpoints.conductor_dimension,
    )
    exclusion_fraction = exclusion / endpoints.physical_length
    if exclusion_fraction + settings.endpoint_window_fraction >= 0.5:
        raise ValueError("endpoint exclusion and sampling windows consume the resonator")
    selected = (normalized >= exclusion_fraction) & (normalized <= 1.0 - exclusion_fraction)
    if not np.any(selected):
        raise PalaceOutputError("quarter-wave sanity interval contains no field samples")
    u = normalized[selected]
    q = phasors[selected]
    w = weights[selected]
    energy = np.abs(q) * w
    if float(energy.sum()) <= 0.0:
        raise PalaceOutputError("quarter-wave profile has zero energy")
    scaled = (u - exclusion_fraction) / (1.0 - 2.0 * exclusion_fraction)
    indices = np.minimum((scaled * settings.bins).astype(int), settings.bins - 1)
    profile = np.bincount(indices, weights=energy, minlength=settings.bins).astype(float)
    profile /= profile.sum()
    ground = float(
        energy[u <= exclusion_fraction + settings.endpoint_window_fraction].sum()
    )
    open_end = float(
        energy[u >= 1.0 - exclusion_fraction - settings.endpoint_window_fraction].sum()
    )
    phase_score = min(
        1.0,
        float(abs(np.sum(w * q)) / max(float(np.sum(w * np.abs(q))), 1e-300)),
    )
    return profile, ground, open_end, phase_score, int(selected.sum())


def evaluate_quarter_wave_energy_profiles(
    *,
    electric_positions: Sequence[float] | npt.NDArray[np.float64],
    electric_energy_phasors: Sequence[complex] | npt.NDArray[np.complex128],
    electric_weights: Sequence[float] | npt.NDArray[np.float64],
    magnetic_positions: Sequence[float] | npt.NDArray[np.float64],
    magnetic_energy_phasors: Sequence[complex] | npt.NDArray[np.complex128],
    magnetic_weights: Sequence[float] | npt.NDArray[np.float64],
    endpoints: ResonatorEndpointMetadata,
    settings: QuarterWaveSanitySettings | None = None,
) -> QuarterWaveSanityResult:
    """Evaluate oriented complex energy profiles without sampling singular endpoints."""
    config = settings or QuarterWaveSanitySettings()
    e_position = _finite_vector(electric_positions, name="electric_positions")
    e_phasor = _complex_vector(electric_energy_phasors, name="electric_energy_phasors")
    e_weight = _finite_vector(electric_weights, name="electric_weights")
    m_position = _finite_vector(magnetic_positions, name="magnetic_positions")
    m_phasor = _complex_vector(magnetic_energy_phasors, name="magnetic_energy_phasors")
    m_weight = _finite_vector(magnetic_weights, name="magnetic_weights")
    if len({len(e_position), len(e_phasor), len(e_weight)}) != 1:
        raise ValueError("electric sample arrays must have equal length")
    if len({len(m_position), len(m_phasor), len(m_weight)}) != 1:
        raise ValueError("magnetic sample arrays must have equal length")
    if np.any(e_weight < 0.0) or np.any(m_weight < 0.0):
        raise ValueError("sample weights must be nonnegative")

    electric, electric_ground, electric_open, electric_phase, electric_count = _profile(
        e_position, e_phasor, e_weight, endpoints=endpoints, settings=config
    )
    magnetic, magnetic_ground, magnetic_open, magnetic_phase, magnetic_count = _profile(
        m_position, m_phasor, m_weight, endpoints=endpoints, settings=config
    )
    bin_positions = (np.arange(config.bins, dtype=float) + 0.5) / config.bins
    electric_reference = np.sin(0.5 * np.pi * bin_positions) ** 2
    magnetic_reference = np.cos(0.5 * np.pi * bin_positions) ** 2
    electric_correlation = _correlation(electric, electric_reference)
    magnetic_correlation = _correlation(magnetic, magnetic_reference)
    combined_correlation = min(electric_correlation, magnetic_correlation)
    combined_phase = min(electric_phase, magnetic_phase)
    electric_ratio = electric_open / max(electric_ground, 1e-300)
    magnetic_ratio = magnetic_ground / max(magnetic_open, 1e-300)
    electric_residual = electric_ground / max(electric_open, 1e-300)
    magnetic_residual = magnetic_open / max(magnetic_ground, 1e-300)
    electric_antinode = electric_ratio >= config.minimum_endpoint_ratio
    magnetic_antinode = magnetic_ratio >= config.minimum_endpoint_ratio
    electric_node = electric_residual <= config.maximum_node_residual
    magnetic_node = magnetic_residual <= config.maximum_node_residual
    profile_passed = combined_correlation >= config.minimum_profile_correlation
    phase_passed = combined_phase >= config.minimum_phase_progression_score
    checks = {
        "electric open-end antinode": electric_antinode,
        "electric grounded-end node": electric_node,
        "magnetic grounded-end antinode": magnetic_antinode,
        "magnetic open-end node": magnetic_node,
        "quarter-wave profile": profile_passed,
        "phase progression": phase_passed,
    }
    exclusion = max(
        config.endpoint_exclusion_mesh_factor * endpoints.local_mesh_size,
        config.endpoint_exclusion_conductor_factor * endpoints.conductor_dimension,
    )
    return QuarterWaveSanityResult(
        selected_sample_count=min(electric_count, magnetic_count),
        bin_count=config.bins,
        physical_length=endpoints.physical_length,
        grounded_coordinate=endpoints.grounded_coordinate,
        open_coordinate=endpoints.open_coordinate,
        coordinate_direction=(1 if endpoints.open_coordinate > endpoints.grounded_coordinate else -1),
        endpoint_exclusion_length=exclusion,
        electric_profile=electric.tolist(),
        magnetic_profile=magnetic.tolist(),
        electric_open_to_ground_ratio=electric_ratio,
        magnetic_ground_to_open_ratio=magnetic_ratio,
        electric_node_residual=electric_residual,
        magnetic_node_residual=magnetic_residual,
        electric_quarter_wave_profile_correlation=electric_correlation,
        magnetic_quarter_wave_profile_correlation=magnetic_correlation,
        quarter_wave_profile_correlation=combined_correlation,
        electric_phase_progression_score=electric_phase,
        magnetic_phase_progression_score=magnetic_phase,
        phase_progression_score=combined_phase,
        electric_antinode_near_open_end=electric_antinode,
        electric_node_near_grounded_end=electric_node,
        magnetic_antinode_near_grounded_end=magnetic_antinode,
        magnetic_node_near_open_end=magnetic_node,
        profile_shape_passed=profile_passed,
        phase_progression_passed=phase_passed,
        passed=all(checks.values()),
        failure_reasons=[name for name, passed in checks.items() if not passed],
    )
