"""Compatibility imports for :mod:`textlayout.solvers.palace`.

New implementation belongs in ``textlayout.solvers.palace``. This module keeps
the pre-existing import path stable for downstream users and older tests.
"""

from __future__ import annotations

from pathlib import Path

from textlayout.evidence.canonical import sha256_file
from textlayout.simulation.runners import find_executable
from textlayout.solvers.palace.capability import (
    _VERSION_RE as _VERSION_RE,  # noqa: F401 - compatibility for existing imports
    detect_palace as _detect_palace,
)
from textlayout.solvers.palace.config import write_config
from textlayout.solvers.palace.models import (
    Eigenmode,
    PalaceCapability,
    PalaceOutputError,
    PalaceRun,
    PalaceUnavailable,
)
from textlayout.solvers.palace.parser import (
    parse_domain_energy,
    parse_eigenmodes as _parse_eigenmodes,
)
from textlayout.solvers.palace.runner import run_palace


def detect_palace(
    explicit: str | None = None,
    *,
    container_digest: str | None = None,
    probe_version: bool = True,
) -> PalaceCapability:
    return _detect_palace(
        explicit,
        container_digest=container_digest,
        probe_version=probe_version,
        finder=find_executable,
    )


def parse_eigenmodes(path: Path) -> list[Eigenmode]:
    """Compatibility view predating explicit eigenpair-error fields."""
    return [
        mode.model_copy(update={"backward_error": None, "absolute_error": None})
        for mode in _parse_eigenmodes(path)
    ]


__all__ = [
    "Eigenmode",
    "PalaceCapability",
    "PalaceOutputError",
    "PalaceRun",
    "PalaceUnavailable",
    "detect_palace",
    "parse_domain_energy",
    "parse_eigenmodes",
    "run_palace",
    "sha256_file",
    "write_config",
]
