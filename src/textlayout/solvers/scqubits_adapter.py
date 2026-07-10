"""Optional scqubits adapter boundary.

scqubits evidence is solver scoped: spectra, matrix elements, and noise-channel
outputs are not interchangeable with Palace or pyEPR evidence.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from textlayout.simulation.models import SimulationResult


def scqubits_available() -> bool:
    return importlib.util.find_spec("scqubits") is not None


def prepare_scqubits_input(parameters: dict[str, Any], output_dir: str | Path) -> SimulationResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = out / "scqubits_input.json"
    payload.write_text(json.dumps(parameters, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SimulationResult(
        status="prepared",
        solver="scqubits",
        readiness_level=2,
        reason="scqubits Hamiltonian input prepared; no diagonalization executed.",
        output_dir=out,
        artifacts={"input": str(payload)},
        warnings=("Prepared Hamiltonian inputs are not physics verification.",),
    )


def execute_scqubits(prepared: SimulationResult) -> SimulationResult:
    if not scqubits_available():
        return SimulationResult(
            status="skipped",
            solver="scqubits",
            readiness_level=prepared.readiness_level,
            reason="scqubits is not installed; returning SKIPPED_SOLVER_ABSENT.",
            output_dir=prepared.output_dir,
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    return SimulationResult(
        status="failed",
        solver="scqubits",
        readiness_level=prepared.readiness_level,
        reason=(
            "Live scqubits execution requires a component-specific model builder; "
            "this adapter boundary refuses to fabricate spectra."
        ),
        output_dir=prepared.output_dir,
        artifacts=dict(prepared.artifacts),
        warnings=prepared.warnings,
    )
