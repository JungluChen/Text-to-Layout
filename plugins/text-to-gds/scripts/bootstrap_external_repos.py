"""Bootstrap external Text-to-GDS backend repositories and tool locations.

This script creates ``.tools/`` and ``.tools/repos/``, clones missing public
backend repositories when requested, and prints explicit manual install steps
for tools that cannot be auto-installed on the current machine.

Run:
  uv run python scripts/bootstrap_external_repos.py --check-only
  uv run python scripts/bootstrap_external_repos.py --clone
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
REPOS = TOOLS / "repos"


@dataclass(frozen=True)
class ExternalRepo:
    name: str
    url: str
    role: str


REPOSITORIES = [
    ExternalRepo("KQCircuits", "https://github.com/iqm-finland/KQCircuits", "layout backend"),
    ExternalRepo("gdsfactory", "https://github.com/gdsfactory/gdsfactory", "layout glue"),
    ExternalRepo("qiskit-metal", "https://github.com/Qiskit/qiskit-metal", "qubit layout"),
    ExternalRepo("scqubits", "https://github.com/scqubits/scqubits", "Hamiltonian solver"),
    ExternalRepo(
        "JosephsonCircuits.jl",
        "https://github.com/kpobrien/JosephsonCircuits.jl",
        "JPA/JTWPA circuit solver",
    ),
    ExternalRepo("JoSIM", "https://github.com/JoeyDelp/JoSIM", "SFQ transient solver"),
    ExternalRepo("pyEPR", "https://github.com/zlatko-minev/pyEPR", "EPR analysis"),
    ExternalRepo("openEMS", "https://github.com/thliebig/openEMS", "FDTD EM solver"),
    ExternalRepo("palace", "https://github.com/awslabs/palace", "FEM eigenmode solver"),
    ExternalRepo("elmerfem", "https://github.com/ElmerCSC/elmerfem", "FEM electrostatics"),
    ExternalRepo("FastCap2", "https://github.com/ediloren/FastCap2", "capacitance extraction"),
    ExternalRepo("FastHenry2", "https://github.com/ediloren/FastHenry2", "inductance extraction"),
]

MANUAL_STEPS = {
    "openems": "Install openEMS and Octave, or place openEMS.exe under .tools/openEMS-*/openEMS/.",
    "palace": "Build Palace with CMake and MPI, then put palace.exe on PATH or under .tools/palace-*/.",
    "elmer": "Install ElmerFEM from https://www.csc.fi/web/elmer, then put ElmerSolver on PATH.",
    "julia": "Install Julia, then run scripts/install_julia_packages.jl for JosephsonCircuits.jl.",
    "josim": "Install JoSIM or place josim.exe under .tools/josim-*/bin/.",
    "fastcap": "Build FastCap2 and put fastcap.exe on PATH or under .tools/FastCap2/.",
    "fasthenry": "Build FastHenry2 and put fasthenry.exe on PATH or under .tools/FastHenry2/.",
}


def _git_available() -> bool:
    return shutil.which("git") is not None


def _clone(repo: ExternalRepo) -> str:
    destination = REPOS / repo.name
    if destination.is_dir():
        return "present"
    if not _git_available():
        return "missing: git not found"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo.url, str(destination)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return f"missing: git clone failed: {result.stderr.strip()[-200:]}"
    return "cloned"


def _repo_status(repo: ExternalRepo, *, clone: bool) -> str:
    destination = REPOS / repo.name
    if destination.is_dir():
        return "present"
    if clone:
        return _clone(repo)
    return f"missing: run uv run python scripts/bootstrap_external_repos.py --clone for {repo.url}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap external Text-to-GDS backend repos.")
    parser.add_argument("--clone", action="store_true", help="clone missing repositories into .tools/repos")
    parser.add_argument("--check-only", action="store_true", help="only report status")
    args = parser.parse_args()

    TOOLS.mkdir(parents=True, exist_ok=True)
    REPOS.mkdir(parents=True, exist_ok=True)

    print("Text-to-GDS external backend bootstrap")
    print(f"tools_dir: {TOOLS}")
    print(f"repos_dir: {REPOS}")
    print()

    for repo in REPOSITORIES:
        status = _repo_status(repo, clone=args.clone and not args.check_only)
        print(f"[repo] {repo.name:<22} {status:<70} {repo.role}")

    print("\nManual solver install steps")
    for tool, step in MANUAL_STEPS.items():
        print(f"- {tool}: {step}")

    print("\nNo solver is marked executed by this script. Execution evidence requires output files.")


if __name__ == "__main__":
    main()

