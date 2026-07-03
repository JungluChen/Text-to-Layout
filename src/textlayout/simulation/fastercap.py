"""FastCap/FasterCap preparation and guarded execution for IDC geometry."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.base import find_simulator
from textlayout.simulation.models import SimulationResult, target_comparison
from textlayout.solvers.base import run_subprocess

_UM_TO_M = 1e-6
_MATRIX_RE = re.compile(r"CAPACITANCE MATRIX,\s*([A-Za-z]+)", re.IGNORECASE)
_UNIT_TO_PF = {
    "farads": 1e12,
    "femtofarads": 1e-3,
    "picofarads": 1.0,
    "nanofarads": 1e3,
}


def prepare_idc_fastercap(
    spec: LayoutSpec,
    geometry: Geometry,
    technology: Technology,
    output_dir: str | Path,
) -> SimulationResult:
    """Prepare a two-conductor, zero-thickness effective-medium IDC model.

    The panel file follows FastCap's generic Q-panel format. Coordinates are
    written in metres because the FastCap manual defines input dimensions as
    metres. The half-space air/silicon problem is approximated using
    ``eps_eff=(1+eps_r)/2`` and is therefore a correlation model, not signoff.
    """
    if spec.component != "IDC":
        raise ValueError("FasterCap preparation currently supports IDC only")
    finger_pairs = int(spec.parameters.get("finger_pairs", 0))
    expected_polygons = 2 + 2 * finger_pairs
    if finger_pairs <= 0 or len(geometry.polygons) < expected_polygons:
        raise ValueError(
            f"IDC topology mismatch: expected {expected_polygons} polygons, "
            f"found {len(geometry.polygons)}"
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    panel_path = out / "idc.qui"
    list_path = out / "idc.lst"
    manifest_path = out / "simulation_manifest.json"

    panel_lines = ["0 Text-to-Layout IDC planar conductor panels in metres"]
    for index, polygon in enumerate(geometry.polygons[:expected_polygons]):
        net = _idc_net(index)
        coords: list[str] = []
        for x_um, y_um in polygon.points:
            coords.extend((f"{x_um * _UM_TO_M:.12g}", f"{y_um * _UM_TO_M:.12g}", "0"))
        if len(coords) != 12:
            raise ValueError("IDC FasterCap adapter requires quadrilateral polygons")
        panel_lines.append(f"Q {net} {' '.join(coords)}")
    panel_path.write_text("\n".join(panel_lines) + "\n", encoding="ascii")

    eps_eff = (1.0 + technology.substrate_epsilon_r) / 2.0
    list_path.write_text(
        "\n".join(
            (
                "* Text-to-Layout IDC effective-medium model",
                "* Input geometry is in metres; conductors are zero-thickness panels.",
                f"C {panel_path.name} {eps_eff:.8g} 0 0 0",
            )
        )
        + "\n",
        encoding="ascii",
    )

    manifest = {
        "schema": "textlayout.simulation-input.v1",
        "status": "input_files_prepared",
        "readiness_level": 2,
        "solver": "FasterCap/FastCap",
        "component": "IDC",
        "source_layout": spec.model_dump(mode="json"),
        "panel_count": expected_polygons,
        "nets": ["P1", "P2"],
        "substrate_epsilon_r": technology.substrate_epsilon_r,
        "effective_permittivity": eps_eff,
        "model_assumptions": [
            "zero-thickness planar conductors",
            "uniform effective dielectric instead of explicit air/silicon interface",
            "no package, loss, kinetic inductance, or self-resonance model",
        ],
        "expected_outputs": ["2x2 capacitance matrix", "mutual capacitance"],
        "references": [
            "FastCap User's Guide, generic Q-panel and list-file interfaces",
            "FastFieldSolvers FasterCap documentation (FastCap2-compatible input)",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return SimulationResult(
        status="input_files_prepared",
        solver="FasterCap/FastCap",
        readiness_level=2,
        reason="FastCap-compatible IDC panel and list files were generated; solver was not run.",
        output_dir=out,
        artifacts={
            "panel_file": str(panel_path),
            "list_file": str(list_path),
            "manifest": str(manifest_path),
        },
        warnings=(
            "Effective-medium capacitance is not a full air/silicon interface extraction.",
            "Mesh convergence and a finite-thickness or full-wave cross-check are required.",
            "Self-resonance and Q are outside this electrostatic model.",
        ),
        evidence_level="EXTRACTION_INPUT_PREPARED",
    )


def run_fastercap(
    prepared: SimulationResult,
    *,
    executable: str | None = None,
    timeout_seconds: int = 600,
    target_capacitance_pf: float | None = None,
    tolerance_pct: float = 10.0,
) -> SimulationResult:
    """Execute a prepared model, returning skipped/failed honestly."""
    list_file = Path(prepared.artifacts["list_file"])
    solver = _find_solver(executable)
    if solver is None:
        return SimulationResult(
            status="skipped",
            solver=prepared.solver,
            readiness_level=2,
            reason=(
                "FastCap/FasterCap executable not found. Install FasterCap or FastCap and "
                "pass --executable; prepared input files remain available."
            ),
            output_dir=prepared.output_dir,
            artifacts=prepared.artifacts,
            warnings=prepared.warnings,
            evidence_level="SKIPPED_SOLVER_ABSENT",
        )

    command = _solver_command(solver, list_file)
    try:
        completed = run_subprocess(
            command,
            cwd=list_file.parent,
            timeout_seconds=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SimulationResult(
            status="failed",
            solver=prepared.solver,
            readiness_level=2,
            reason=f"Solver execution failed: {exc}",
            output_dir=prepared.output_dir,
            artifacts=prepared.artifacts,
            warnings=prepared.warnings,
            command=tuple(command),
        )

    stdout_path = completed.stdout_path
    stderr_path = completed.stderr_path
    artifacts = {
        **prepared.artifacts,
        "solver_stdout": str(stdout_path),
        "solver_stderr": str(stderr_path),
    }
    if completed.returncode != 0:
        return SimulationResult(
            status="failed",
            solver=prepared.solver,
            readiness_level=2,
            reason=f"Solver exited with code {completed.returncode}.",
            output_dir=prepared.output_dir,
            artifacts=artifacts,
            warnings=prepared.warnings,
            command=tuple(command),
        )

    try:
        matrix_pf = _parse_capacitance_matrix_pf(completed.stdout)
    except ValueError as exc:
        return SimulationResult(
            status="failed",
            solver=prepared.solver,
            readiness_level=2,
            reason=f"Solver output was not accepted: {exc}",
            output_dir=prepared.output_dir,
            artifacts=artifacts,
            warnings=prepared.warnings,
            command=tuple(command),
        )

    mutual_pf = abs(matrix_pf[0][1]) if len(matrix_pf) >= 2 and len(matrix_pf[0]) >= 2 else None
    comparison = (
        target_comparison(mutual_pf, target_capacitance_pf, tolerance_pct, "mutual_capacitance_pf")
        if mutual_pf is not None
        else None
    )
    result_path = list_file.parent / "simulation_result.json"
    payload = {
        "schema": "textlayout.simulation-result.v1",
        "status": "executed",
        "solver": Path(solver).name,
        "capacitance_matrix_pf": matrix_pf,
        "mutual_capacitance_pf": mutual_pf,
        "target_comparison": comparison,
        "source_artifact": str(stdout_path),
    }
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    artifacts["result"] = str(result_path)
    return SimulationResult(
        status="executed",
        solver=Path(solver).name,
        readiness_level=4 if comparison else 3,
        reason="A real solver returned a parseable capacitance matrix.",
        output_dir=prepared.output_dir,
        artifacts=artifacts,
        extracted_quantities={
            "capacitance_matrix_pf": matrix_pf,
            "mutual_capacitance_pf": mutual_pf,
        },
        target_comparison=comparison,
        warnings=prepared.warnings,
        command=tuple(command),
        return_code=completed.returncode,
        runtime_seconds=completed.runtime_seconds,
        evidence_level="CAPACITANCE_EXTRACTED",
    )


def _idc_net(polygon_index: int) -> str:
    if polygon_index == 0:
        return "P1"
    if polygon_index == 1:
        return "P2"
    return "P1" if (polygon_index - 2) % 2 == 0 else "P2"


def _find_solver(explicit: str | None) -> str | None:
    return find_simulator(
        "TEXTLAYOUT_FASTERCAP",
        ("FasterCap", "FasterCap.exe", "fastcap", "fastcap.exe"),
        explicit,
        tool_subdir="FasterCap",
    )


def _solver_command(executable: str, list_file: Path) -> list[str]:
    if "fastercap" in Path(executable).name.lower():
        return [executable, "-b", "-a0.01", str(list_file)]
    return [executable, f"-l{list_file}"]


def _parse_capacitance_matrix_pf(text: str) -> list[list[float]]:
    match = _MATRIX_RE.search(text)
    if match is None:
        for line_index, line in enumerate(text.splitlines()):
            if line.strip().lower().startswith("capacitance matrix is"):
                remaining = text.splitlines()[line_index + 1 :]
                dimension_re = re.compile(r"Dimension\s+(\d+)\s*x\s*(\d+)", re.IGNORECASE)
                dim = None
                for candidate in remaining[:10]:
                    dim_match = dimension_re.search(candidate)
                    if dim_match:
                        dim = (int(dim_match.group(1)), int(dim_match.group(2)))
                        break
                if dim is None or dim[0] != dim[1] or dim[0] < 2:
                    raise ValueError("missing or invalid FasterCap matrix dimension")
                n = dim[0]
                rows: list[list[float]] = []
                for data_line in remaining:
                    stripped = data_line.strip()
                    if not stripped:
                        continue
                    tokens = stripped.split()
                    if tokens and tokens[0].lower() == "dimension":
                        continue
                    if len(tokens) < 1 + n:
                        if rows:
                            break
                        continue
                    try:
                        values = [float(token) * 1e12 for token in tokens[1 : 1 + n]]
                    except ValueError:
                        if rows:
                            break
                        continue
                    rows.append(values)
                    if len(rows) >= n:
                        break
                if len(rows) < 2:
                    raise ValueError("fewer than two FasterCap capacitance-matrix rows")
                width = len(rows[0])
                if width < 2 or any(len(row) != width for row in rows):
                    raise ValueError("malformed FasterCap capacitance matrix")
                return rows[:width]

        raise ValueError("missing CAPACITANCE MATRIX heading")
    scale = _UNIT_TO_PF.get(match.group(1).lower())
    if scale is None:
        raise ValueError(f"unsupported capacitance unit {match.group(1)!r}")
    rows: list[list[float]] = []
    for line in text[match.end() :].splitlines():
        tokens = line.split()
        if len(tokens) < 3:
            continue
        try:
            values = [float(token) * scale for token in tokens[2:]]
        except ValueError:
            continue
        if values:
            rows.append(values)
    if len(rows) < 2:
        raise ValueError("fewer than two capacitance-matrix rows")
    width = len(rows[0])
    if width < 2 or any(len(row) != width for row in rows):
        raise ValueError("malformed capacitance matrix")
    return rows[:width]
