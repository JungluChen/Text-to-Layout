"""Executable Palace eigenmode backend."""

from textlayout.solvers.palace.backend import PalaceBackend
from textlayout.solvers.palace.capability import detect_palace
from textlayout.solvers.palace.models import (
    Eigenmode,
    PalaceCapability,
    PalaceOutputError,
    PalaceUnavailable,
)
from textlayout.solvers.palace.model_audit import (
    audit_quarter_wave_model,
    QuarterWaveModelAudit,
    render_quarter_wave_audit_svg,
)
from textlayout.solvers.palace.mode_classification import (
    classify_mode,
    extract_spatial_energy_fractions,
    ModeClass,
    ModeSignature,
    select_target_mode,
    SpatialEnergyFractions,
    TargetModeSelection,
)
from textlayout.solvers.palace.mode_sanity import (
    evaluate_quarter_wave_energy_profiles,
    QuarterWaveSanityResult,
    QuarterWaveSanitySettings,
    ResonatorEndpointMetadata,
)

__all__ = [
    "Eigenmode",
    "PalaceBackend",
    "PalaceCapability",
    "PalaceOutputError",
    "PalaceUnavailable",
    "ModeClass",
    "ModeSignature",
    "QuarterWaveModelAudit",
    "QuarterWaveSanityResult",
    "QuarterWaveSanitySettings",
    "ResonatorEndpointMetadata",
    "SpatialEnergyFractions",
    "TargetModeSelection",
    "audit_quarter_wave_model",
    "classify_mode",
    "detect_palace",
    "evaluate_quarter_wave_energy_profiles",
    "extract_spatial_energy_fractions",
    "render_quarter_wave_audit_svg",
    "select_target_mode",
]
