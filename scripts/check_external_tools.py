"""Check availability of every external backend and report status.

Run: uv run python scripts/check_external_tools.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text_to_gds.tool_discovery import tool_paths  # noqa: E402
from text_to_gds.backends import BACKEND_CLASSES     # noqa: E402

SEP = "-" * 60

def _python(module: str) -> tuple[bool, str]:
    spec = importlib.util.find_spec(module)
    if spec is None:
        return False, "not installed"
    try:
        mod = importlib.import_module(module)
        ver = getattr(mod, "__version__", None) or getattr(mod, "version", None)
        return True, str(ver) if ver else "installed"
    except Exception as exc:
        return False, f"import error: {exc}"


def main() -> None:
    tools = tool_paths()
    print(SEP)
    print("Text-to-GDS — External Backend Status")
    print(SEP)

    print("\n[Python packages]")
    checks = [
        ("gdsfactory",     "gdsfactory",    "GDS glue / boolean ops / export"),
        ("kqcircuits",     "kqcircuits",    "Superconducting CPW, resonators, airbridges"),
        ("qiskit_metal",   "qiskit_metal",  "Transmon, CPW routing, launch pads"),
        ("scqubits",       "scqubits",      "Qubit Hamiltonian spectra, anharmonicity"),
        ("pyEPR",          "pyEPR",         "Energy participation ratios"),
    ]
    for label, module, role in checks:
        ok, info = _python(module)
        mark = "OK" if ok else "--"
        print(f"  [{mark}] {label:<18} {info:<22}  {role}")

    print("\n[Binary tools]")
    avail = tools.summary()
    roles = {
        "julia":   "JosephsonCircuits.jl runtime (JPA/JTWPA harmonic balance)",
        "josim":   "JoSIM SFQ circuit simulator",
        "openems": "openEMS FDTD (RF S-parameters, CPW Z0, .s2p output)",
        "klayout": "KLayout (DRC, process rules)",
        "ngspice": "ngspice SPICE simulator",
        "palace":  "Palace eigenmode FEM (f0, Q factor)",
        "elmer":   "Elmer FEM (electrostatic capacitance)",
    }
    for name, path in avail.items():
        mark = "OK" if path else "--"
        role = roles.get(name, "")
        info = str(Path(path).relative_to(ROOT)) if path else "not found"
        print(f"  [{mark}] {name:<10} {info:<45}  {role}")

    print("\n[Backend registry]")
    for name, cls in BACKEND_CLASSES.items():
        backend = cls()
        av = backend.available()
        mark = "OK" if av.available else "--"
        ver = f" v{av.version}" if av.version else ""
        print(f"  [{mark}] {name:<22} {av.reason}{ver}")

    print("\n[External repos]")
    repos_dir = ROOT / "external_repos"
    expected = [
        "KQCircuits", "qiskit-metal", "JosephsonCircuits",
        "scqubits", "openEMS", "palace", "elmerfem", "pyEPR",
    ]
    for repo in expected:
        path = repos_dir / repo
        mark = "OK" if path.is_dir() else "--"
        print(f"  [{mark}] {repo}")

    print(f"\n{SEP}")
    all_py = all(_python(m)[0] for _, m, _ in checks)
    all_bin = any(v for v in avail.values())
    all_repos = all((repos_dir / r).is_dir() for r in expected)
    print(f"  Python packages : {'all installed' if all_py else 'some missing'}")
    print(f"  Binary tools    : {'at least one found' if all_bin else 'none found'}")
    print(f"  Cloned repos    : {'all present' if all_repos else 'some missing'}")
    print(SEP)


if __name__ == "__main__":
    main()
