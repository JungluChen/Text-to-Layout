"""Probe declared Python dependencies; imports are not solver/scientific acceptance."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tomllib
from packaging.requirements import Requirement

# Distribution names differ from import names. Keep each probe in a subprocess:
# a native extension crash must be retained as a failed package, not lose the report.
PACKAGES = {
    "gdsfactory": "gdsfactory",
    "klayout": "klayout.db",
    "langgraph": "langgraph",
    "matplotlib": "matplotlib",
    "mcp": "mcp",
    "numpy": "numpy",
    "scipy": "scipy",
    "pillow": "PIL",
    "pydantic": "pydantic",
    "pyyaml": "yaml",
    "trimesh": "trimesh",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "kqcircuits": "kqcircuits",
    "quantum-metal": "qiskit_metal",
    "gdstk": "gdstk",
    "optuna": "optuna",
    "scikit-rf": "skrf",
    "qcodes": "qcodes",
    "scqubits": "scqubits",
    "gmsh": "gmsh",
    "meshio": "meshio",
    "mkdocs": "mkdocs",
    "mkdocs-material": "material",
    "pytest": "pytest",
    "ruff": "ruff",
    "mypy": "mypy",
    "pytest-cov": "pytest_cov",
    "build": "build",
    "hatchling": "hatchling",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["QISKIT_METAL_HEADLESS"] = "1"
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    requirements = list(project["project"]["dependencies"])
    for group in project["project"]["optional-dependencies"].values():
        requirements.extend(group)
    declared = {Requirement(value).name.lower().replace("_", "-") for value in requirements}
    unmapped = sorted(declared - PACKAGES.keys())
    results = []
    for distribution, module in PACKAGES.items():
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        command = [
            sys.executable,
            "-c",
            "import importlib; importlib.import_module(" + repr(module) + ")",
        ]
        try:
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
            code, log = run.returncode, run.stdout + run.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, log = -1, str(exc)
        (args.out / (distribution + ".log")).write_text(log, encoding="utf-8")
        results.append(
            {
                "distribution": distribution,
                "module": module,
                "version": version,
                "exit_code": code,
                "passed": version is not None and code == 0,
            }
        )
        print(distribution, version, code, flush=True)
    passed = not unmapped and all(row["passed"] for row in results)
    report = {
        "schema": "textlayout.python-package-imports.v1",
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "results": results,
        "passed": passed,
        "unmapped_distributions": unmapped,
        "scope": "package metadata and imports only; no solver acceptance",
    }
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
