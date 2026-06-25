"""Check availability of every external backend and report explicit status.

Run: uv run python scripts/check_external_tools.py
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text_to_gds.backends import BACKEND_CLASSES  # noqa: E402
from text_to_gds.tool_discovery import tool_paths  # noqa: E402

SEP = "-" * 72

MANUAL_STEPS = {
    "julia": "Install Julia, then run uv run python scripts/setup_external_tools.py.",
    "josim": "Install JoSIM or place josim.exe under .tools/josim-*/bin/.",
    "openems": "Install openEMS and Octave or place openEMS.exe under .tools/openEMS-*/openEMS/.",
    "klayout": "Install KLayout or rely on the Python klayout package for local DRC.",
    "ngspice": "Install ngspice and put ngspice.exe on PATH for SPICE runs.",
    "palace": "Build Palace with CMake and MPI, then put palace.exe on PATH.",
    "elmer": "Install ElmerFEM and put ElmerSolver on PATH.",
}


def _python(module: str) -> tuple[bool, str]:
    spec = importlib.util.find_spec(module)
    if spec is None:
        return False, "not installed"
    try:
        mod = importlib.import_module(module)
        version = getattr(mod, "__version__", None) or getattr(mod, "version", None)
        return True, str(version) if version else "installed"
    except Exception as exc:  # noqa: BLE001 - diagnostic script must keep running
        return False, f"import error: {exc}"


def _relative(path: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    tools = tool_paths()
    print(SEP)
    print("Text-to-GDS External Backend Status")
    print(SEP)

    print("\n[Python packages]")
    checks = [
        ("gdsfactory", "gdsfactory", "GDS glue / boolean ops / export"),
        ("kqcircuits", "kqcircuits", "Superconducting CPW, resonators, airbridges"),
        ("qiskit_metal", "qiskit_metal", "Transmon, CPW routing, launch pads"),
        ("scqubits", "scqubits", "Qubit Hamiltonian spectra, anharmonicity"),
        ("pyEPR", "pyEPR", "Energy participation ratios"),
    ]
    for label, module, role in checks:
        ok, info = _python(module)
        mark = "OK" if ok else "--"
        print(f"  [{mark}] {label:<18} {info:<24} {role}")

    print("\n[Binary tools]")
    available = tools.summary()
    roles = {
        "julia": "JosephsonCircuits.jl runtime",
        "josim": "JoSIM SFQ circuit simulator",
        "openems": "openEMS FDTD",
        "klayout": "KLayout DRC",
        "ngspice": "ngspice SPICE simulator",
        "palace": "Palace eigenmode FEM",
        "elmer": "Elmer FEM electrostatics",
    }
    for name, path in available.items():
        mark = "OK" if path else "--"
        info = _relative(path) if path else "not found"
        print(f"  [{mark}] {name:<10} {info:<48} {roles.get(name, '')}")
        if not path:
            print(f"       install: {MANUAL_STEPS.get(name, 'See backend documentation.')}")

    print("\n[Backend registry]")
    for name, cls in BACKEND_CLASSES.items():
        backend = cls()
        availability = backend.available()
        mark = "OK" if availability.available else "--"
        version = f" v{availability.version}" if availability.version else ""
        print(f"  [{mark}] {name:<22} {availability.reason}{version}")

    print("\n[External repos]")
    repos_dir = ROOT / ".tools" / "repos"
    expected = [
        "KQCircuits",
        "gdsfactory",
        "qiskit-metal",
        "JosephsonCircuits.jl",
        "JoSIM",
        "scqubits",
        "openEMS",
        "palace",
        "elmerfem",
        "pyEPR",
        "FastCap2",
        "FastHenry2",
    ]
    for repo in expected:
        path = repos_dir / repo
        mark = "OK" if path.is_dir() else "--"
        print(f"  [{mark}] {repo}")
        if not path.is_dir():
            print("       install: uv run python scripts/bootstrap_external_repos.py --clone")

    all_py = all(_python(module)[0] for _, module, _ in checks)
    any_binary = any(path for path in available.values())
    all_repos = all((repos_dir / repo).is_dir() for repo in expected)
    print(f"\n{SEP}")
    print(f"  Python packages : {'all installed' if all_py else 'some missing'}")
    print(f"  Binary tools    : {'at least one found' if any_binary else 'none found'}")
    print(f"  Cloned repos    : {'all present' if all_repos else 'some missing'}")
    print("  Missing tools are SKIPPED until installed; they are never counted as executed.")
    print(SEP)


if __name__ == "__main__":
    main()
