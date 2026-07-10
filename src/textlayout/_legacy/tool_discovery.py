"""Discover optional external tool binaries from .tools/ and system PATH.

Call ``discover()`` once at import time to get a ``ToolPaths`` instance.
Every adapter that needs an executable should call ``tool_paths()`` rather
than hard-coding a binary name.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / ".tools"


def _find(candidates: list[str | Path]) -> str | None:
    """Return the first existing executable from a list of candidates."""
    for c in candidates:
        p = Path(c)
        if p.is_file():
            return str(p)
    for c in candidates:
        found = shutil.which(str(c))
        if found:
            return found
    return None


@dataclass
class ToolPaths:
    julia: str | None
    josim: str | None
    openems: str | None
    klayout: str | None
    ngspice: str | None
    palace: str | None
    elmer: str | None

    def summary(self) -> dict[str, str | None]:
        return {
            "julia": self.julia,
            "josim": self.josim,
            "openems": self.openems,
            "klayout": self.klayout,
            "ngspice": self.ngspice,
            "palace": self.palace,
            "elmer": self.elmer,
        }

    def available(self) -> dict[str, bool]:
        return {k: v is not None for k, v in self.summary().items()}


def discover() -> ToolPaths:
    """Scan .tools/ subdirectories and PATH for known external executables."""
    tools_subdirs = sorted(_TOOLS.glob("julia-*"))
    julia_bins = [d / "bin" / "julia.exe" for d in tools_subdirs] + [
        d / "bin" / "julia" for d in tools_subdirs
    ]
    julia = _find(julia_bins + ["julia"])

    josim_bins = list(_TOOLS.glob("josim-*/bin/josim-cli.exe")) + list(
        _TOOLS.glob("josim-*/bin/josim-cli")
    )
    josim = _find(josim_bins + ["josim-cli", "josim"])

    openems_bins = (
        list(_TOOLS.glob("openEMS-*/openEMS/openEMS.exe"))
        + list(_TOOLS.glob("openEMS-*/openEMS.exe"))
        + list(_TOOLS.glob("openems-*/openEMS.exe"))
    )
    openems = _find(openems_bins + ["openEMS", "openems"])

    klayout_bins = (
        list(_TOOLS.glob("klayout-*/klayout.exe"))
        + list(_TOOLS.glob("klayout-*/klayout"))
    )
    klayout = _find(klayout_bins + ["klayout"])

    ngspice = _find(["ngspice"])

    palace = _find(
        list(_TOOLS.glob("palace-*/bin/palace"))
        + list(_TOOLS.glob("palace-*/bin/palace.exe"))
        + ["palace"]
    )

    elmer = _find(
        list(_TOOLS.glob("Elmer-*/bin/ElmerSolver.exe"))
        + list(_TOOLS.glob("elmer-*/bin/ElmerSolver"))
        + ["ElmerSolver"]
    )

    return ToolPaths(
        julia=julia,
        josim=josim,
        openems=openems,
        klayout=klayout,
        ngspice=ngspice,
        palace=palace,
        elmer=elmer,
    )


_cached: ToolPaths | None = None


def tool_paths() -> ToolPaths:
    global _cached
    if _cached is None:
        _cached = discover()
    return _cached
