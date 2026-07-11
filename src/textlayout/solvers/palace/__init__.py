"""Executable Palace eigenmode backend."""

from textlayout.solvers.palace.backend import PalaceBackend
from textlayout.solvers.palace.capability import detect_palace
from textlayout.solvers.palace.models import (
    Eigenmode,
    PalaceCapability,
    PalaceOutputError,
    PalaceUnavailable,
)

__all__ = [
    "Eigenmode",
    "PalaceBackend",
    "PalaceCapability",
    "PalaceOutputError",
    "PalaceUnavailable",
    "detect_palace",
]
