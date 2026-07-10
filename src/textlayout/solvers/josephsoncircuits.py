"""Process-isolated JosephsonCircuits.jl adapter.

This module prepares circuit/netlist files and can invoke Julia when the pinned
environment is installed. It never substitutes a local JPA gain formula for a
JosephsonCircuits.jl result.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from textlayout.simulation.models import SimulationResult
from textlayout.solvers.base import run_subprocess

JULIA_PROJECT = Path("external_tools") / "julia" / "JosephsonCircuits"
RESULT_FILE = "josephsoncircuits_result.json"
SPARAM_FILE = "josephsoncircuits_sparameters.csv"


def discover_julia(explicit: str | None = None) -> str | None:
    """Return a Julia executable path/name if available."""
    if explicit:
        return explicit if Path(explicit).is_file() else shutil.which(explicit)
    return shutil.which("julia")


def prepare_jpa_netlist(
    circuit: dict[str, Any],
    output_dir: str | Path,
) -> SimulationResult:
    """Write a JSON netlist handoff for a JPA/JTWPA run."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    netlist = out / "josephsoncircuits_netlist.json"
    driver = out / "run_josephsoncircuits.jl"
    netlist.write_text(json.dumps(circuit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    driver.write_text(
        "\n".join(
            [
                "using JSON3",
                "using JosephsonCircuits",
                f'input = JSON3.read(read("{netlist.name}", String))',
                "# TODO: map extracted C/L/M/JJ/environment records into a full",
                "# JosephsonCircuits.jl harmonic-balance problem.",
                f'open("{RESULT_FILE}", "w") do io',
                '    JSON3.pretty(io, Dict("status" => "INPUT_FILES_PREPARED",',
                '        "solver" => "JosephsonCircuits.jl",',
                '        "reason" => "netlist prepared; nonlinear solve not executed by this driver"))',
                '    write(io, "\\n")',
                "end",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return SimulationResult(
        status="prepared",
        solver="JosephsonCircuits.jl",
        readiness_level=2,
        reason="JosephsonCircuits.jl netlist and Julia driver prepared; no solver executed.",
        output_dir=out,
        artifacts={"netlist": str(netlist), "driver": str(driver)},
        warnings=(
            "Prepared inputs are not solver evidence.",
            "Do not claim JPA/JTWPA gain, bandwidth, conversion, or noise without parsed solver output.",
        ),
    )


def execute_josephsoncircuits(
    prepared: SimulationResult,
    *,
    executable: str | None = None,
    timeout_seconds: int = 600,
) -> SimulationResult:
    """Run the prepared Julia driver when Julia is available."""
    if prepared.output_dir is None:
        return SimulationResult(
            status="failed",
            solver="JosephsonCircuits.jl",
            readiness_level=prepared.readiness_level,
            reason="No output directory was attached to the prepared run.",
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    julia = discover_julia(executable)
    if julia is None:
        return SimulationResult(
            status="skipped",
            solver="JosephsonCircuits.jl",
            readiness_level=prepared.readiness_level,
            reason="Julia executable not found; returning SKIPPED_SOLVER_ABSENT.",
            output_dir=prepared.output_dir,
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    driver = Path(prepared.artifacts.get("driver", ""))
    if not driver.is_file():
        return SimulationResult(
            status="failed",
            solver="JosephsonCircuits.jl",
            readiness_level=prepared.readiness_level,
            reason="Prepared Julia driver is missing.",
            output_dir=prepared.output_dir,
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    project = Path.cwd() / JULIA_PROJECT
    try:
        completed = run_subprocess(
            [julia, f"--project={project}", driver.name],
            cwd=Path(prepared.output_dir),
            timeout_seconds=timeout_seconds,
            log_prefix="josephsoncircuits",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SimulationResult(
            status="failed",
            solver="JosephsonCircuits.jl",
            readiness_level=prepared.readiness_level,
            reason=f"JosephsonCircuits.jl subprocess failed: {exc}",
            output_dir=prepared.output_dir,
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    result = Path(prepared.output_dir) / RESULT_FILE
    artifacts = {
        **prepared.artifacts,
        "solver_stdout": str(completed.stdout_path),
        "solver_stderr": str(completed.stderr_path),
    }
    if completed.returncode != 0 or not result.is_file() or result.stat().st_size == 0:
        return SimulationResult(
            status="failed",
            solver="JosephsonCircuits.jl",
            readiness_level=prepared.readiness_level,
            reason=f"Julia exited {completed.returncode} without a non-empty solver result.",
            output_dir=prepared.output_dir,
            artifacts=artifacts,
            warnings=prepared.warnings,
            command=completed.command,
            return_code=completed.returncode,
            runtime_seconds=completed.runtime_seconds,
        )
    return SimulationResult(
        status="executed",
        solver="JosephsonCircuits.jl",
        readiness_level=3,
        reason="JosephsonCircuits.jl subprocess produced a non-empty result file.",
        output_dir=prepared.output_dir,
        artifacts={**artifacts, "result": str(result)},
        warnings=prepared.warnings,
        command=completed.command,
        return_code=completed.returncode,
        runtime_seconds=completed.runtime_seconds,
    )


class JosephsonCircuitsAdapter:
    """Minimal adapter object used by registry checks and future workflows."""

    name = "JosephsonCircuits.jl"

    def discover(self, explicit: str | None = None) -> str | None:
        return discover_julia(explicit)

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def prepare(self, circuit: dict[str, Any], output_dir: str | Path) -> SimulationResult:
        return prepare_jpa_netlist(circuit, output_dir)

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return execute_josephsoncircuits(
            prepared, executable=executable, timeout_seconds=timeout_seconds
        )
