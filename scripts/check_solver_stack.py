"""Print the complete local solver stack without promoting missing tools to evidence."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.simulation.fastercap import _find_solver as find_fastercap  # noqa: E402
from textlayout.simulation.josim import _find as find_josim  # noqa: E402
from textlayout.simulation.runners import (  # noqa: E402
    _FASTHENRY_NAMES,
    discover_openems_stack,
    find_executable,
)
from textlayout.simulation.wrspice import find_wrspice  # noqa: E402


def _module(name: str) -> str | None:
    return name if importlib.util.find_spec(name) is not None else None


def main() -> int:
    stack = discover_openems_stack()
    checks = (
        ("FasterCap", find_fastercap(None)),
        ("FastHenry", find_executable(_FASTHENRY_NAMES, env_var="TEXTLAYOUT_FASTHENRY")),
        ("openEMS binary", stack.get("openems")),
        ("CSXCAD", stack.get("csxcad")),
        ("Octave", stack.get("octave")),
        ("Octave openEMS path", stack.get("octave_openems_path")),
        ("Octave CSXCAD path", stack.get("octave_csxcad_path")),
        ("scikit-rf", _module("skrf")),
        ("Gmsh", find_executable(("gmsh", "gmsh.exe"), env_var="TEXTLAYOUT_GMSH")),
        ("meshio", _module("meshio")),
        ("Palace", find_executable(("palace", "palace.exe"), env_var="TEXTLAYOUT_PALACE")),
        ("JoSIM", find_josim(None)),
        ("WRspice", find_wrspice(None)),
    )
    for name, value in checks:
        print(f"{name}: {'ok' if value else 'missing'}" + (f" ({value})" if value else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
