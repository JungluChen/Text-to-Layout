"""FastCap/FasterCap preparation and guarded execution for IDC geometry."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import replace
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
        return _persist_result(SimulationResult(
            status="skipped",
            solver=prepared.solver,
            readiness_level=2,
            reason="FasterCap/FastCap executable not found.",
            output_dir=prepared.output_dir,
            artifacts=prepared.artifacts,
            warnings=prepared.warnings,
            evidence_level="SKIPPED_SOLVER_ABSENT",
        ), list_file)

    command = _solver_command(solver, list_file)
    solver_version = _capture_solver_version(solver, list_file.parent)
    try:
        completed = run_subprocess(
            command,
            cwd=list_file.parent,
            timeout_seconds=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        stdout, stderr = _exception_output(exc)
        stdout_path, stderr_path = _write_attempt_logs(
            list_file.parent,
            stdout,
            stderr or f"Solver execution failed: {exc}\n",
        )
        return _persist_result(SimulationResult(
            status="failed",
            solver=_solver_label(solver),
            readiness_level=2,
            reason=f"Solver execution failed: {exc}",
            output_dir=prepared.output_dir,
            artifacts={
                **prepared.artifacts,
                "solver_stdout": str(stdout_path),
                "solver_stderr": str(stderr_path),
            },
            warnings=prepared.warnings,
            command=tuple(command),
            solver_version=solver_version,
        ), list_file)

    stdout_path = completed.stdout_path
    stderr_path = completed.stderr_path
    _ensure_nonempty_log(stdout_path, "Solver produced no stdout.")
    _ensure_nonempty_log(stderr_path, "Solver produced no stderr.")
    artifacts = {
        **prepared.artifacts,
        "solver_stdout": str(stdout_path),
        "solver_stderr": str(stderr_path),
    }
    if completed.returncode != 0:
        return _persist_result(SimulationResult(
            status="failed",
            solver=_solver_label(solver),
            readiness_level=2,
            reason=f"Solver exited with code {completed.returncode}.",
            output_dir=prepared.output_dir,
            artifacts=artifacts,
            warnings=prepared.warnings,
            command=tuple(command),
            return_code=completed.returncode,
            runtime_seconds=completed.runtime_seconds,
            solver_version=solver_version,
        ), list_file)

    try:
        matrix_pf = _parse_capacitance_matrix_pf(completed.stdout)
    except ValueError as exc:
        return _persist_result(SimulationResult(
            status="failed",
            solver=_solver_label(solver),
            readiness_level=2,
            reason=f"Solver parser failed: {exc}",
            output_dir=prepared.output_dir,
            artifacts=artifacts,
            warnings=prepared.warnings,
            command=tuple(command),
            return_code=completed.returncode,
            runtime_seconds=completed.runtime_seconds,
            solver_version=solver_version,
        ), list_file)

    mutual_pf = abs(matrix_pf[0][1]) if len(matrix_pf) >= 2 and len(matrix_pf[0]) >= 2 else None
    comparison = (
        target_comparison(mutual_pf, target_capacitance_pf, tolerance_pct, "mutual_capacitance_pf")
        if mutual_pf is not None
        else None
    )
    verified = bool(comparison and comparison.get("within_tolerance"))
    return _persist_result(SimulationResult(
        status="executed",
        solver=_solver_label(solver),
        readiness_level=4 if comparison else 3,
        reason=(
            "Extracted mutual capacitance is within tolerance."
            if verified
            else "A real solver returned a parseable capacitance matrix; "
            "the target was not met or was not provided."
        ),
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
        evidence_level="PHYSICS_VERIFIED" if verified else "CAPACITANCE_EXTRACTED",
        solver_version=solver_version,
    ), list_file)


def _persist_result(result: SimulationResult, list_file: Path) -> SimulationResult:
    """Write one schema-complete result for every terminal solver status."""
    result_path = list_file.parent / "simulation_result.json"
    artifacts = {**result.artifacts, "result": str(result_path)}
    persisted = replace(result, artifacts=artifacts)
    payload = persisted.to_dict()
    payload.update(persisted.extracted_quantities)
    payload["prepared_inputs"] = all(
        Path(artifacts[key]).is_file() for key in ("list_file", "panel_file")
    )
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return persisted


def _solver_label(executable: str) -> str:
    return "FasterCap" if "fastercap" in Path(executable).name.lower() else "FastCap"


def _ensure_nonempty_log(path: Path, message: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        path.write_text(message + "\n", encoding="utf-8")


def _write_attempt_logs(output_dir: Path, stdout: str, stderr: str) -> tuple[Path, Path]:
    stdout_path = output_dir / "solver.stdout.txt"
    stderr_path = output_dir / "solver.stderr.txt"
    stdout_path.write_text(stdout or "Solver produced no stdout.\n", encoding="utf-8")
    stderr_path.write_text(stderr or "Solver produced no stderr.\n", encoding="utf-8")
    return stdout_path, stderr_path


def _exception_output(exc: OSError | subprocess.TimeoutExpired) -> tuple[str, str]:
    if not isinstance(exc, subprocess.TimeoutExpired):
        return "", str(exc)

    def decoded(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    return decoded(exc.stdout), decoded(exc.stderr)


def _idc_net(polygon_index: int) -> str:
    if polygon_index == 0:
        return "P1"
    if polygon_index == 1:
        return "P2"
    return "P1" if (polygon_index - 2) % 2 == 0 else "P2"


def _find_solver(explicit: str | None) -> str | None:
    found = find_simulator(
        "TEXTLAYOUT_FASTERCAP",
        ("FasterCap", "FasterCap.exe", "fastcap", "fastcap.exe"),
        explicit,
        tool_subdir="FasterCap",
    )
    if found is not None and sys.platform == "win32" and _is_elf(Path(found)):
        # A Linux (WSL) build of FasterCap discovered from Windows: usable only
        # when the `wsl` launcher exists; otherwise report it honestly as absent.
        return found if _wsl_available() else None
    return found


def _is_elf(path: Path) -> bool:
    try:
        return path.is_file() and path.read_bytes()[:4] == b"\x7fELF"
    except OSError:
        return False


def _wsl_available() -> bool:
    import shutil

    return shutil.which("wsl") is not None


def _to_wsl_path(path: Path) -> str:
    """Translate ``C:\\dir\\file`` into ``/mnt/c/dir/file`` for WSL invocation."""
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def _needs_wsl(executable: str) -> bool:
    return sys.platform == "win32" and _is_elf(Path(executable))


def _executable_prefix(executable: str) -> list[str]:
    if Path(executable).suffix.lower() == ".py":
        return [sys.executable, executable]
    if _needs_wsl(executable):
        return ["wsl", _to_wsl_path(Path(executable))]
    return [executable]


def _solver_command(executable: str, list_file: Path) -> list[str]:
    prefix = _executable_prefix(executable)
    list_arg = _to_wsl_path(list_file) if _needs_wsl(executable) else str(list_file)
    if "fastercap" in Path(executable).name.lower():
        return [*prefix, "-b", "-a0.01", list_arg]
    return [*prefix, f"-l{list_arg}"]


def _capture_solver_version(executable: str, cwd: Path) -> str | None:
    prefix = _executable_prefix(executable)
    flag = "-bv" if "fastercap" in Path(executable).name.lower() else "-v"
    try:
        completed = subprocess.run(
            [*prefix, flag],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    banner = (completed.stdout or completed.stderr).strip()
    return banner.splitlines()[0][:200] if banner else None


def _validate_maxwell_matrix(rows: list[list[float]]) -> list[list[float]]:
    """Reject non-physical Maxwell capacitance matrices.

    FasterCap's automatic refinement (``-a``) prints one matrix per refinement
    pass; early passes can be numerically invalid (negative diagonal and/or
    positive off-diagonal — FasterCap itself warns about them). Accepting such
    a matrix would turn solver noise into a fake extraction, so a matrix that
    violates the Maxwell sign convention is a hard parser failure.
    """
    for i, row in enumerate(rows):
        if row[i] <= 0:
            raise ValueError(
                f"non-physical capacitance matrix: diagonal element [{i}][{i}] = "
                f"{row[i]:g} pF is not positive (unconverged or invalid solve)"
            )
        for j, value in enumerate(row):
            if j != i and value > 0:
                raise ValueError(
                    f"non-physical capacitance matrix: off-diagonal element [{i}][{j}] = "
                    f"{value:g} pF is positive (unconverged or invalid solve)"
                )
    return rows


def _parse_capacitance_matrix_pf(text: str) -> list[list[float]]:
    match = _MATRIX_RE.search(text)
    if match is None:
        lines = text.splitlines()
        headings = [
            index
            for index, line in enumerate(lines)
            if line.strip().lower().startswith("capacitance matrix is")
        ]
        if not headings:
            raise ValueError("missing CAPACITANCE MATRIX heading")
        # With automatic refinement, only the LAST printed matrix is the
        # converged result; earlier ones are intermediate refinement passes.
        remaining = lines[headings[-1] + 1 :]
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
        return _validate_maxwell_matrix(rows[:width])
    scale = _UNIT_TO_PF.get(match.group(1).lower())
    if scale is None:
        raise ValueError(f"unsupported capacitance unit {match.group(1)!r}")
    fastcap_rows: list[list[float]] = []
    for line in text[match.end() :].splitlines():
        tokens = line.split()
        if len(tokens) < 3:
            continue
        try:
            values = [float(token) * scale for token in tokens[2:]]
        except ValueError:
            continue
        if values:
            fastcap_rows.append(values)
    if len(fastcap_rows) < 2:
        raise ValueError("fewer than two capacitance-matrix rows")
    width = len(fastcap_rows[0])
    if width < 2 or any(len(row) != width for row in fastcap_rows):
        raise ValueError("malformed capacitance matrix")
    return _validate_maxwell_matrix(fastcap_rows[:width])
