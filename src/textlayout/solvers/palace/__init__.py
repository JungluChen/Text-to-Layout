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
    "QuarterWaveModelAudit",
    "QuarterWaveSanityResult",
    "QuarterWaveSanitySettings",
    "ResonatorEndpointMetadata",
    "audit_quarter_wave_model",
    "detect_palace",
    "evaluate_quarter_wave_energy_profiles",
    "render_quarter_wave_audit_svg",
]
