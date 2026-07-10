"""Palace (AWS open-source FEM) eigenmode/driven project generation.

Palace is the closest open-source analog to HFSS eigenmode: it returns resonant
frequencies, quality factors, field energies, and dielectric participation. It is
a C++/MPI FEM code (Linux/HPC; on Windows it runs under WSL or a container), so
this adapter generates the Palace JSON config plus a real gmsh mesh and executes
`palace` only when the binary is on PATH, skipping cleanly otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textlayout._legacy.meshing import mesh_available, write_stack_mesh
from textlayout._legacy.pyaedt_bridge import build_pyaedt_config


def palace_available() -> bool:
    """Return whether the `palace` executable is on PATH."""
    return shutil.which("palace") is not None


def build_palace_config(
    *,
    mesh_path: str | Path,
    substrate: dict[str, Any],
    problem_type: str = "Eigenmode",
    target_frequency_ghz: float = 6.0,
    num_modes: int = 4,
    order: int = 2,
) -> dict[str, Any]:
    """Build a Palace JSON config for an eigenmode or driven run.

    Domain attributes follow the gmsh mesh: attribute 1 is the substrate volume,
    attribute 2+ are the metal layers. These must be reviewed against the actual
    mesh physical groups before solving.
    """
    if problem_type not in {"Eigenmode", "Driven"}:
        raise ValueError("problem_type must be 'Eigenmode' or 'Driven'")
    config: dict[str, Any] = {
        "Problem": {
            "Type": problem_type,
            "Verbose": 2,
            "Output": "postpro",
        },
        "Model": {
            "Mesh": str(Path(mesh_path).name),
            "L0": 1.0e-6,
        },
        "Domains": {
            "Materials": [
                {
                    "Attributes": [1],
                    "Permittivity": float(substrate.get("relative_permittivity", 11.45)),
                    "LossTan": float(substrate.get("loss_tangent", 1e-6)),
                },
                {
                    "Attributes": [2],
                    "Permittivity": 1.0,
                    "LossTan": 0.0,
                },
            ],
            "Postprocessing": {
                "Energy": [{"Index": 1, "Attributes": [1]}],
            },
        },
        "Boundaries": {
            "PEC": {"Attributes": [3]},
        },
        "Solver": {
            "Order": int(order),
            "Device": "CPU",
            "Linear": {"Type": "Default", "Tol": 1.0e-8, "MaxIts": 200},
        },
    }
    if problem_type == "Eigenmode":
        config["Solver"]["Eigenmode"] = {
            "N": int(num_modes),
            "Tol": 1.0e-8,
            "Target": float(target_frequency_ghz),
            "Save": int(num_modes),
        }
    else:
        config["Solver"]["Driven"] = {
            "MinFreq": max(0.1, target_frequency_ghz * 0.5),
            "MaxFreq": target_frequency_ghz * 1.5,
            "FreqStep": max(target_frequency_ghz * 0.01, 0.01),
            "Save": 2,
        }
    return config


def _parse_eigenmode_csv(path: Path) -> list[dict[str, float]] | None:
    if not path.exists():
        return None
    rows: list[dict[str, float]] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return None
    header = [cell.strip().lower() for cell in lines[0].split(",")]

    def column(*names: str) -> int | None:
        for name in names:
            for index, cell in enumerate(header):
                if name in cell:
                    return index
        return None

    f_col = column("re{f}", "f (ghz)", "frequency")
    q_col = column("q", "quality")
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.split(",")]
        if f_col is None or f_col >= len(cells):
            continue
        try:
            row = {"frequency_ghz": float(cells[f_col])}
            if q_col is not None and q_col < len(cells):
                row["quality_factor"] = float(cells[q_col])
        except ValueError:
            continue
        rows.append(row)
    return rows or None


def write_palace_project(
    gds_path: str | Path,
    *,
    config_path: str | Path,
    report_path: str | Path,
    mesh_path: str | Path,
    mesh_report_path: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    problem_type: str = "Eigenmode",
    target_frequency_ghz: float = 6.0,
    num_modes: int = 4,
    run: bool = False,
) -> dict[str, Any]:
    """Generate a Palace project (config + gmsh mesh) and optionally run `palace`."""
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
    config = build_palace_config(
        mesh_path=mesh_path,
        substrate=stack["substrate"],
        problem_type=problem_type,
        target_frequency_ghz=target_frequency_ghz,
        num_modes=num_modes,
    )
    config_file = Path(config_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

    result: dict[str, Any] = {
        "schema": "text-to-gds.palace-project.v1",
        "backend": "Palace (AWS open-source FEM)",
        "problem_type": problem_type,
        "status": "prepared",
        "source_gds": str(gds_path),
        "config_path": str(config_file),
        "mesh": {
            "status": mesh.get("status"),
            "path": str(mesh_path),
            "nodes": mesh.get("nodes"),
            "tetrahedra": mesh.get("tetrahedra"),
        },
        "target_frequency_ghz": target_frequency_ghz,
        "num_modes": num_modes,
        "expected_results": ["frequency_ghz", "quality_factor", "field_energy", "participation"],
        "review_gates": [
            "Assign mesh physical-group attributes to the Domains/Boundaries attribute numbers.",
            "Replace PEC metal with a superconducting surface impedance for loss/Q.",
            "Calibrate substrate loss tangent before participation/Q signoff.",
        ],
        "model_validity": (
            "Generated Palace eigenmode config plus a real gmsh mesh. Palace is the "
            "open-source HFSS-eigenmode analog (f0, Q, energy, participation); it solves "
            "under WSL/Linux+MPI."
        ),
    }

    if run:
        if not mesh_available():
            result["status"] = "skipped"
            result.setdefault("warnings", []).append("gmsh is required to mesh before Palace.")
        elif not palace_available():
            result["status"] = "skipped"
            result.setdefault("warnings", []).append(
                "palace executable not found on PATH; install Palace (WSL/Linux) to solve."
            )
        else:
            completed = subprocess.run(
                ["palace", str(config_file)],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(config_file.parent),
            )
            result["returncode"] = completed.returncode
            eig = _parse_eigenmode_csv(config_file.parent / "postpro" / "eig.csv")
            if eig is not None:
                result["eigenmodes"] = eig
            result["status"] = "executed" if completed.returncode == 0 else "failed"

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result
