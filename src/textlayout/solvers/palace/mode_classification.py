"""Explainable physical classification of Palace eigenmode candidates."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

from textlayout.solvers.palace.mode_sanity import QuarterWaveSanityResult
from textlayout.solvers.palace.models import MaterialOverlapMap, PalaceOutputError


class ModeClass(StrEnum):
    QUARTER_WAVE_RESONATOR = "QUARTER_WAVE_RESONATOR"
    HALF_WAVE_RESONATOR = "HALF_WAVE_RESONATOR"
    PACKAGE_MODE = "PACKAGE_MODE"
    SUBSTRATE_MODE = "SUBSTRATE_MODE"
    SLOTLINE_MODE = "SLOTLINE_MODE"
    COUPLING_STRUCTURE_MODE = "COUPLING_STRUCTURE_MODE"
    LOCALIZED_EDGE_MODE = "LOCALIZED_EDGE_MODE"
    UNKNOWN = "UNKNOWN"


class SpatialEnergyFractions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cpw_gap_participation: float = Field(ge=0.0, le=1.0)
    coupling_region_participation: float = Field(ge=0.0, le=1.0)
    substrate_bulk_fraction: float = Field(ge=0.0, le=1.0)
    package_energy_fraction: float = Field(ge=0.0, le=1.0)
    boundary_energy_fraction: float = Field(ge=0.0, le=1.0)
    slotline_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ModeSignature(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_index: int = Field(ge=1)
    frequency_ghz: float = Field(gt=0.0)
    electric_open_end_score: float = Field(ge=0.0, le=1.0)
    electric_ground_node_score: float = Field(ge=0.0, le=1.0)
    magnetic_ground_end_score: float = Field(ge=0.0, le=1.0)
    quarter_wave_profile_score: float = Field(ge=0.0, le=1.0)
    resonator_localization: float = Field(ge=0.0, le=1.0)
    cpw_gap_participation: float = Field(ge=0.0, le=1.0)
    coupling_region_participation: float = Field(ge=0.0, le=1.0)
    substrate_bulk_fraction: float = Field(ge=0.0, le=1.0)
    package_energy_fraction: float = Field(ge=0.0, le=1.0)
    boundary_energy_fraction: float = Field(ge=0.0, le=1.0)
    longitudinal_phase_score: float = Field(ge=0.0, le=1.0)
    mode_class: ModeClass
    classification_confidence: float = Field(ge=0.0, le=1.0)
    quarter_wave_weighted_score: float = Field(ge=0.0, le=1.0)
    half_wave_profile_score: float = Field(ge=0.0, le=1.0)
    frequency_prior_score: float = Field(ge=0.0, le=1.0)
    hard_quarter_wave_gates_passed: bool
    score_components: dict[str, float]
    rejection_reasons: list[str]


class TargetModeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    target_mode: int | None
    target_frequency_ghz: float | None
    confidence: float | None
    rejection_reasons_by_mode: dict[int, list[str]]


def extract_spatial_energy_fractions(
    field: Path,
    *,
    material_map: MaterialOverlapMap,
    center_width: float,
    gap: float,
    coupling_gap: float,
    electrical_length: float,
    interface_half_height: float = 20.0,
    boundary_distance: float = 20.0,
) -> SpatialEnergyFractions:
    """Integrate electric energy over physical resonator, package, and boundary masks."""
    from textlayout.solvers.palace.overlap import _integration_mesh, _tensors

    if min(center_width, gap, coupling_gap, electrical_length) <= 0.0:
        raise ValueError("resonator dimensions must be positive")
    mesh = _integration_mesh(field, "electric")
    tensors = _tensors(material_map, mesh.attributes, "electric")
    weighted = np.einsum("nij,nj->ni", tensors, mesh.cell_fields)
    density = np.real(np.einsum("ni,ni->n", np.conjugate(mesh.cell_fields), weighted))
    energy = np.maximum(density, 0.0) * mesh.volumes
    total = float(energy.sum())
    if total <= 0.0:
        raise PalaceOutputError("mode classification field has zero electric energy")
    x = mesh.centroids[:, 0]
    y = mesh.centroids[:, 1]
    z = mesh.centroids[:, 2]
    half_signal = center_width / 2.0
    cpw_gap = (
        (np.abs(x) >= half_signal)
        & (np.abs(x) <= half_signal + gap)
        & (y >= 0.0)
        & (y <= electrical_length)
        & (np.abs(z) <= interface_half_height)
    )
    coupling = (
        (np.abs(x) <= half_signal + gap)
        & (y >= electrical_length)
        & (y <= electrical_length + coupling_gap)
        & (np.abs(z) <= interface_half_height)
    )
    entries = {entry.attribute: entry for entry in material_map.entries}
    substrate = np.asarray(
        [entries[int(attribute)].material_name != "vacuum" for attribute in mesh.attributes]
    )
    package = np.asarray(
        [not entries[int(attribute)].critical_region for attribute in mesh.attributes]
    )
    lower = mesh.centroids.min(axis=0)
    upper = mesh.centroids.max(axis=0)
    boundary = np.any(
        (mesh.centroids <= lower + boundary_distance)
        | (mesh.centroids >= upper - boundary_distance),
        axis=1,
    )

    def fraction(mask: npt.NDArray[np.bool_]) -> float:
        return min(1.0, max(0.0, float(energy[mask].sum()) / total))

    return SpatialEnergyFractions(
        cpw_gap_participation=fraction(cpw_gap),
        coupling_region_participation=fraction(coupling),
        substrate_bulk_fraction=fraction(substrate),
        package_energy_fraction=fraction(package),
        boundary_energy_fraction=fraction(boundary),
        slotline_score=0.0,
    )


def _profile_correlation(
    values: list[float], expected: npt.NDArray[np.float64]
) -> float:
    array = np.asarray(values, dtype=float)
    if np.std(array) <= np.finfo(float).eps:
        return 0.0
    correlation = float(np.corrcoef(array, expected)[0, 1])
    return max(0.0, min(1.0, correlation if np.isfinite(correlation) else 0.0))


def _ratio_score(ratio: float) -> float:
    return max(0.0, min(1.0, ratio / (1.0 + ratio)))


def classify_mode(
    *,
    mode_index: int,
    frequency_ghz: float,
    search_window_ghz: tuple[float, float],
    sanity: QuarterWaveSanityResult,
    resonator_localization: float,
    spatial: SpatialEnergyFractions,
) -> ModeSignature:
    """Classify one mode; frequency is a 5% prior and never overrides hard gates."""
    low, high = search_window_ghz
    if not 0.0 < low < high:
        raise ValueError("search window must be finite, positive, and increasing")
    center = 0.5 * (low + high)
    half_width = 0.5 * (high - low)
    frequency_prior = max(0.0, 1.0 - abs(frequency_ghz - center) / half_width)
    electric_open = _ratio_score(sanity.electric_open_to_ground_ratio)
    electric_ground = 1.0 / (1.0 + sanity.electric_node_residual)
    magnetic_ground = _ratio_score(sanity.magnetic_ground_to_open_ratio)
    profile = max(0.0, sanity.quarter_wave_profile_correlation)
    positions = (np.arange(sanity.bin_count, dtype=float) + 0.5) / sanity.bin_count
    half_electric = np.sin(np.pi * positions) ** 2
    half_magnetic = np.cos(np.pi * positions) ** 2
    half_wave = min(
        _profile_correlation(sanity.electric_profile, half_electric),
        _profile_correlation(sanity.magnetic_profile, half_magnetic),
    )
    components = {
        "endpoint_shape": 0.20 * min(electric_open, electric_ground, magnetic_ground),
        "quarter_wave_profile": 0.25 * profile,
        "resonator_localization": 0.20 * resonator_localization,
        "cpw_gap_participation": 0.10 * spatial.cpw_gap_participation,
        "package_rejection": 0.10 * (1.0 - spatial.package_energy_fraction),
        "phase_progression": 0.10 * sanity.phase_progression_score,
        "frequency_prior": 0.05 * frequency_prior,
    }
    weighted_score = sum(components.values())
    hard_checks = {
        "electric open-end antinode failed": sanity.electric_antinode_near_open_end,
        "electric grounded-end node failed": sanity.electric_node_near_grounded_end,
        "magnetic grounded-end antinode failed": sanity.magnetic_antinode_near_grounded_end,
        "magnetic open-end node failed": sanity.magnetic_node_near_open_end,
        "quarter-wave profile failed": sanity.profile_shape_passed,
        "longitudinal phase failed": sanity.phase_progression_passed,
        "resonator localization below 0.5": resonator_localization >= 0.5,
        "package energy fraction above 0.5": spatial.package_energy_fraction <= 0.5,
    }
    hard_passed = all(hard_checks.values())
    rejection_reasons = [reason for reason, passed in hard_checks.items() if not passed]

    if hard_passed:
        mode_class = ModeClass.QUARTER_WAVE_RESONATOR
        confidence = weighted_score
    elif spatial.coupling_region_participation >= 0.4:
        mode_class = ModeClass.COUPLING_STRUCTURE_MODE
        confidence = spatial.coupling_region_participation
    elif spatial.package_energy_fraction >= 0.6:
        mode_class = ModeClass.PACKAGE_MODE
        confidence = spatial.package_energy_fraction
    elif spatial.substrate_bulk_fraction >= 0.8 and resonator_localization < 0.5:
        mode_class = ModeClass.SUBSTRATE_MODE
        confidence = spatial.substrate_bulk_fraction
    elif spatial.slotline_score >= 0.7:
        mode_class = ModeClass.SLOTLINE_MODE
        confidence = spatial.slotline_score
    elif spatial.boundary_energy_fraction >= 0.4:
        mode_class = ModeClass.LOCALIZED_EDGE_MODE
        confidence = spatial.boundary_energy_fraction
    elif half_wave >= 0.9:
        mode_class = ModeClass.HALF_WAVE_RESONATOR
        confidence = half_wave
    else:
        mode_class = ModeClass.UNKNOWN
        confidence = max(weighted_score, half_wave)
    return ModeSignature(
        mode_index=mode_index,
        frequency_ghz=frequency_ghz,
        electric_open_end_score=electric_open,
        electric_ground_node_score=electric_ground,
        magnetic_ground_end_score=magnetic_ground,
        quarter_wave_profile_score=profile,
        resonator_localization=resonator_localization,
        cpw_gap_participation=spatial.cpw_gap_participation,
        coupling_region_participation=spatial.coupling_region_participation,
        substrate_bulk_fraction=spatial.substrate_bulk_fraction,
        package_energy_fraction=spatial.package_energy_fraction,
        boundary_energy_fraction=spatial.boundary_energy_fraction,
        longitudinal_phase_score=sanity.phase_progression_score,
        mode_class=mode_class,
        classification_confidence=confidence,
        quarter_wave_weighted_score=weighted_score,
        half_wave_profile_score=half_wave,
        frequency_prior_score=frequency_prior,
        hard_quarter_wave_gates_passed=hard_passed,
        score_components=components,
        rejection_reasons=rejection_reasons,
    )


def select_target_mode(
    signatures: list[ModeSignature], *, minimum_confidence_margin: float = 0.05
) -> TargetModeSelection:
    """Select only a physically accepted quarter-wave candidate."""
    candidates = sorted(
        (
            signature
            for signature in signatures
            if signature.mode_class == ModeClass.QUARTER_WAVE_RESONATOR
            and signature.hard_quarter_wave_gates_passed
        ),
        key=lambda item: (-item.classification_confidence, item.mode_index),
    )
    rejected = {signature.mode_index: signature.rejection_reasons for signature in signatures}
    if not candidates:
        return TargetModeSelection(
            status="TARGET_MODE_NOT_FOUND",
            target_mode=None,
            target_frequency_ghz=None,
            confidence=None,
            rejection_reasons_by_mode=rejected,
        )
    if (
        len(candidates) > 1
        and candidates[0].classification_confidence - candidates[1].classification_confidence
        < minimum_confidence_margin
    ):
        return TargetModeSelection(
            status="MODE_CLASSIFICATION_AMBIGUOUS",
            target_mode=None,
            target_frequency_ghz=None,
            confidence=None,
            rejection_reasons_by_mode=rejected,
        )
    selected = candidates[0]
    return TargetModeSelection(
        status="TARGET_MODE_IDENTIFIED",
        target_mode=selected.mode_index,
        target_frequency_ghz=selected.frequency_ghz,
        confidence=selected.classification_confidence,
        rejection_reasons_by_mode=rejected,
    )


def signature_report(signature: ModeSignature) -> dict[str, Any]:
    """Return an explicitly weighted, JSON-ready explanation."""
    return signature.model_dump(mode="json")
