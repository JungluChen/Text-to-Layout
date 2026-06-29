"""Install and configure all optional external tool backends.

Run: uv run python scripts/setup_external_tools.py [--check-only]

Steps performed:
  1. Check Python package availability and install missing ones via pip.
  2. Verify .tools/ binaries (julia, josim, openEMS) are present.
  3. Install JosephsonCircuits.jl via the embedded Julia binary.
  4. Print a final status table.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CHECK_ONLY = "--check-only" in sys.argv

PYTHON_PACKAGES = [
    ("gdsfactory",   "gdsfactory",    ">=8.0"),
    ("kqcircuits",   "kqcircuits",    ""),
    ("scqubits",     "scqubits",      ">=4.0"),
    ("pyEPR",        "pyEPR-quantum", ""),
]

JULIA_PACKAGES = ["JosephsonCircuits"]


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _install_python(package_spec: str) -> bool:
    print(f"  Installing {package_spec} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package_spec],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _julia_bin() -> Path | None:
    for d in sorted((ROOT / ".tools").glob("julia-*")):
        for candidate in [d / "bin" / "julia.exe", d / "bin" / "julia"]:
            if candidate.is_file():
                return candidate
    return None


def _install_julia_package(julia: Path, package: str) -> bool:
    script = ROOT / "scripts" / "install_julia_packages.jl"
    result = subprocess.run(
        [str(julia), str(script)],
        capture_output=True, text=True,
        env={
            **__import__("os").environ,
            "JULIA_DEPOT_PATH": str(ROOT / ".tools" / "julia-depot"),
        },
    )
    if result.returncode == 0:
        print(f"    {package}: OK")
        return True
    print(f"    {package}: FAILED\n{result.stderr[-500:]}")
    return False


def main() -> None:
    print("=" * 60)
    print("Text-to-GDS — External Tool Setup")
    print("=" * 60)

    print("\n[1/3] Python packages")
    for module, package, version in PYTHON_PACKAGES:
        spec = f"{package}{version}" if version else package
        if _installed(module):
            print(f"  [OK] {package} already installed")
        elif CHECK_ONLY:
            print(f"  [--] {package} missing (run without --check-only to install)")
        else:
            ok = _install_python(spec)
            print(f"  {'[OK]' if ok else '[!!]'} {package}")

    print("\n[2/3] Binary tools in .tools/")
    from text_to_gds.tool_discovery import discover
    tools = discover()
    for name, path in tools.summary().items():
        if path:
            print(f"  [OK] {name}: {path}")
        else:
            print(f"  [--] {name}: not found (install manually or download to .tools/)")

    print("\n[3/3] Julia packages")
    julia = _julia_bin()
    if julia is None:
        print("  [--] Julia not found in .tools/ — skipping Julia package install")
        print("       Download Julia from https://julialang.org/downloads/")
        print("       and place it under .tools/julia-<version>/")
    elif CHECK_ONLY:
        print(f"  [OK] Julia found at {julia}")
        print(f"       Run without --check-only to install: {', '.join(JULIA_PACKAGES)}")
    else:
        print(f"  Julia: {julia}")
        for pkg in JULIA_PACKAGES:
            _install_julia_package(julia, pkg)

    print("\n" + "=" * 60)
    print("Done. Run scripts/check_external_tools.py for full status.")
    print("=" * 60)


if __name__ == "__main__":
    main()
