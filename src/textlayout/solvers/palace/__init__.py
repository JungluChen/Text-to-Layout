"""Executable Palace eigenmode backend."""

from textlayout.solvers.palace.backend import PalaceBackend
from textlayout.solvers.palace.capability import detect_palace
from textlayout.solvers.palace.models import (
    Eigenmode,
    PalaceCapability,
    PalaceOutputError,
    PalaceUnavailable,
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
    "QuarterWaveSanityResult",
    "QuarterWaveSanitySettings",
    "ResonatorEndpointMetadata",
    "detect_palace",
    "evaluate_quarter_wave_energy_profiles",
]
