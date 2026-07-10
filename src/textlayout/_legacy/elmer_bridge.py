"""Elmer FEM electrostatic capacitance extraction (open-source Q3D analog).

Elmer's StatElecSolver computes the Maxwell capacitance matrix from an
electrostatic FEM solve - the open-source counterpart to Ansys Q3D. This adapter
generates a real gmsh mesh plus an Elmer `.sif` solver-input deck and runs
`ElmerSolver` when it is on PATH (Windows installer available), skipping cleanly
otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textlayout._legacy.meshing import mesh_available, write_stack_mesh
from textlayout._legacy.pyaedt_bridge import build_pyaedt_config


def elmer_available() -> bool:
    """Return whether an ElmerSolver executable is on PATH."""
    return any(shutil.which(name) for name in ("ElmerSolver", "ElmerSolver_mpi", "elmersolver"))


def build_elmer_sif(*, relative_permittivity: float, capacitance_bodies: int) -> str:
    """Build an Elmer `.sif` electrostatic capacitance-matrix deck."""
    bodies = max(int(capacitance_bodies), 1)
    lines = [
        "! Text-to-GDS Elmer electrostatic capacitance deck",
        'Header',
        '  Mesh DB "." "mesh"',
        'End',
        '',
        'Simulation',
        '  Coordinate System = Cartesian 3D',
        '  Simulation Type = Steady State',
        '  Steady State Max Iterations = 1',
        '  Output File = "case.result"',
        'End',
        '',
        'Constants',
        '  Permittivity Of Vacuum = 8.8541878128e-12',
        'End',
        '',
        'Body 1',
        '  Equation = 1',
        '  Material = 1',
        'End',
        '',
        'Material 1',
        f'  Relative Permittivity = {relative_permittivity:.6g}',
        'End',
        '',
        'Equation 1',
        '  Active Solvers(1) = 1',
        'End',
        '',
        'Solver 1',
        '  Equation = Electrostatics',
        '  Procedure = "StatElecSolve" "StatElecSolver"',
        '  Variable = Potential',
        '  Calculate Capacitance Matrix = True',
        '  Capacitance Matrix Filename = "CapacitanceMatrix.dat"',
        '  Linear System Solver = Iterative',
        '  Linear System Iterative Method = BiCGStab',
        '  Linear System Max Iterations = 1000',
        '  Linear System Convergence Tolerance = 1.0e-8',
        'End',
    ]
    for index in range(1, bodies + 1):
        lines += [
            '',
            f'Boundary Condition {index}',
            f'  Target Boundaries(1) = {index}',
            f'  Capacitance Body = {index}',
            'End',
        ]
    return "\n".join(lines) + "\n"


def _parse_capacitance_matrix_pf(path: Path) -> list[list[float]] | None:
    if not path.exists():
        return None
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        cells = line.split()
        try:
            rows.append([float(c) * 1e12 for c in cells])  # F -> pF
        except ValueError:
            continue
    return rows or None


def write_elmer_project(
    gds_path: str | Path,
    *,
    sif_path: str | Path,
    report_path: str | Path,
    mesh_path: str | Path,
    mesh_report_path: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    run: bool = False,
) -> dict[str, Any]:
    """Generate an Elmer capacitance project (mesh + .sif) and optionally run ElmerSolver."""
    stack = build_pyaedt_config(
        gds_path, outputs={}, sidecar_path=sidecar_path, process_path=process_path
    )
    mesh = write_stack_mesh(
        gds_path,
        mesh_path=mesh_path,
        report_path=mesh_report_path,
        sidecar_path=sidecar_path,
        process_path=process_path,
    )
    metal_layers = [
        spec
        for spec in stack["layer_mapping"].values()
        if str(spec.get("process_material", "")).lower() in {"nb", "al", "tin", "nbtin"}
    ]
    bodies = max(len(metal_layers), 2)
    sif = build_elmer_sif(
        relative_permittivity=float(stack["substrate"].get("relative_permittivity", 11.45)),
        capacitance_bodies=bodies,
    )
    sif_file = Path(sif_path)
    sif_file.parent.mkdir(parents=True, exist_ok=True)
    sif_file.write_text(sif, encoding="utf-8")

    result: dict[str, Any] = {
        "schema": "text-to-gds.elmer-project.v1",
        "backend": "Elmer FEM (StatElecSolver)",
        "status": "prepared",
        "source_gds": str(gds_path),
        "sif_path": str(sif_file),
        "mesh": {"status": mesh.get("status"), "path": str(mesh_path), "tetrahedra": mesh.get("tetrahedra")},
        "capacitance_bodies": bodies,
        "expected_results": ["capacitance_matrix_pf"],
        "review_gates": [
            "Map gmsh physical-group boundaries to the Capacitance Body numbers in the .sif.",
            "Convert the gmsh mesh with ElmerGrid before solving (ElmerGrid 14 2 mesh.msh).",
        ],
        "model_validity": (
            "Generated Elmer electrostatic capacitance deck plus a real gmsh mesh; the "
            "open-source Q3D analog for the conductor capacitance matrix."
        ),
    }
    if run:
        if not mesh_available():
            result["status"] = "skipped"
            result.setdefault("warnings", []).append("gmsh is required to mesh before Elmer.")
        elif not elmer_available():
            result["status"] = "skipped"
            result.setdefault("warnings", []).append(
                "ElmerSolver not on PATH; install Elmer FEM to solve."
            )
        else:
            completed = subprocess.run(
                ["ElmerSolver", sif_file.name],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(sif_file.parent),
            )
            result["returncode"] = completed.returncode
            matrix = _parse_capacitance_matrix_pf(sif_file.parent / "CapacitanceMatrix.dat")
            if matrix is not None:
                result["capacitance_matrix_pf"] = matrix
            result["status"] = "executed" if completed.returncode == 0 else "failed"

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result
