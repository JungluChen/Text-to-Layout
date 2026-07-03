"""Optional Gmsh-to-Palace full-chip preparation and guarded execution."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from textlayout.mesh import export_gmsh_geo
from textlayout.models import Geometry
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.models import SimulationResult
from textlayout.simulation.runners import _execution_command, find_executable
from textlayout.solvers.base import run_subprocess


def prepare_palace_fullchip(
    spec: LayoutSpec,
    geometry: Geometry,
    output_dir: str | Path,
    *,
    execute: bool = False,
    palace_executable: str | None = None,
    gmsh_executable: str | None = None,
) -> SimulationResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    geo = export_gmsh_geo(geometry, out / "full_tile.geo")
    mesh = out / "full_tile.msh"
    config = out / "palace.json"
    config.write_text(
        json.dumps(_palace_config(mesh.name), indent=2) + "\n", encoding="utf-8"
    )
    artifacts = {"gmsh_geo": str(geo), "palace_config": str(config)}
    warnings = (
        "The 3-D extrusion is a simplified research handoff, not a package or foundry model.",
        "Dielectric loss, enclosure, wirebonds, ports, and material dispersion require review.",
    )

    gmsh = find_executable(("gmsh", "gmsh.exe"), gmsh_executable, env_var="TEXTLAYOUT_GMSH")
    if gmsh:
        try:
            completed = run_subprocess(
                _execution_command(gmsh, [geo.name, "-3", "-format", "msh4", "-o", mesh.name], out),
                cwd=out,
                timeout_seconds=600,
                log_prefix="gmsh",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SimulationResult(
                status="failed",
                solver="Gmsh + Palace",
                readiness_level=2,
                reason=f"Gmsh execution failed: {exc}",
                output_dir=out,
                artifacts=artifacts,
                warnings=warnings,
            )
        artifacts.update(
            {
                "gmsh_stdout": str(completed.stdout_path),
                "gmsh_stderr": str(completed.stderr_path),
            }
        )
        if completed.returncode == 0 and mesh.is_file() and mesh.stat().st_size:
            artifacts["mesh"] = str(mesh)

    palace = find_executable(
        ("palace", "palace.exe"), palace_executable, env_var="TEXTLAYOUT_PALACE"
    )
    if not execute or palace is None or "mesh" not in artifacts:
        missing = []
        if gmsh is None:
            missing.append("Gmsh")
        if palace is None:
            missing.append("Palace")
        return SimulationResult(
            status="input_files_prepared",
            solver="Gmsh + Palace",
            readiness_level=2,
            reason=(
                "Palace full-tile inputs prepared; solver not executed"
                + (f" because {', '.join(missing)} is missing." if missing else ".")
            ),
            output_dir=out,
            artifacts=artifacts,
            warnings=warnings,
        )

    completed = run_subprocess(
        _execution_command(palace, [config.name], out),
        cwd=out,
        timeout_seconds=3600,
        log_prefix="palace",
    )
    artifacts.update(
        {"palace_stdout": str(completed.stdout_path), "palace_stderr": str(completed.stderr_path)}
    )
    result_file, frequencies = _parse_palace_frequencies(out)
    if completed.returncode != 0 or result_file is None or not frequencies:
        return SimulationResult(
            status="failed",
            solver="Palace",
            readiness_level=2,
            reason="Palace ran but no parseable eigenmode result was produced.",
            output_dir=out,
            artifacts=artifacts,
            warnings=warnings,
            command=completed.command,
            return_code=completed.returncode,
            runtime_seconds=completed.runtime_seconds,
        )
    artifacts["result"] = str(result_file)
    return SimulationResult(
        status="executed",
        solver="Palace",
        readiness_level=3,
        reason="Palace produced parseable eigenmode frequencies.",
        output_dir=out,
        artifacts=artifacts,
        extracted_quantities={"eigenmode_frequencies_ghz": frequencies},
        warnings=warnings,
        command=completed.command,
        return_code=completed.returncode,
        runtime_seconds=completed.runtime_seconds,
    )


def _palace_config(mesh_name: str) -> dict[str, Any]:
    return {
        "Problem": {"Type": "Eigenmode"},
        "Model": {"Mesh": mesh_name, "L0": 1e-6},
        "Domains": {
            "Materials": [
                {"Attributes": [1], "Permittivity": 11.9, "Permeability": 1.0},
                {"Attributes": [2], "PEC": True},
            ]
        },
        "Boundaries": {"PEC": {"Attributes": [1]}},
        "Solver": {"Order": 1, "Eigenmode": {"N": 6, "Target": 6.0e9, "Tol": 1e-8}},
    }


def _parse_palace_frequencies(root: Path) -> tuple[Path | None, list[float]]:
    for path in sorted(root.rglob("*.csv")):
        frequencies: list[float] = []
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            for token in line.replace(",", " ").split():
                try:
                    value = float(token)
                except ValueError:
                    continue
                if 1e6 <= value <= 1e12:
                    frequencies.append(value / 1e9)
                    break
        if frequencies:
            return path, frequencies
    return None, []
