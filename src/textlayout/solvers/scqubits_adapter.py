"""Optional scqubits adapter boundary.

scqubits evidence is solver scoped: spectra, matrix elements, and noise-channel
outputs are not interchangeable with Palace or pyEPR evidence.
"""

from __future__ import annotations

import importlib
import importlib.util
import hashlib
import math
import time
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.simulation.models import SimulationResult


class TransmonInput(BaseModel):
    """Explicit SI inputs; no default EJ/EC ratio or inferred extraction."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ic_a: float = Field(gt=0)
    capacitance_f: float = Field(gt=0)
    ng: float = 0.0
    ncut: int = Field(default=30, ge=1, strict=True)
    n_evals: int = Field(default=6, ge=3, strict=True)

    @model_validator(mode="after")
    def check_basis(self) -> TransmonInput:
        if self.n_evals > 2 * self.ncut + 1:
            raise ValueError("n_evals exceeds the charge basis size 2*ncut+1")
        return self


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
    started = time.perf_counter()
    artifacts = dict(prepared.artifacts)
    try:
        if prepared.output_dir is None:
            raise ValueError("Prepared input has no output directory")
        input_path = Path(artifacts["input"])
        inputs = TransmonInput.model_validate_json(input_path.read_bytes())
        scqubits = importlib.import_module("scqubits")
        # Preserve the extraction-derived conversion and guards from the legacy
        # adapter. Energies passed to scqubits are E/h in GHz, not angular rates.
        planck_j_s = 6.62607015e-34
        electron_charge_c = 1.602176634e-19
        phi0_weber = planck_j_s / (2.0 * electron_charge_c)
        ej = phi0_weber * inputs.ic_a / (2 * math.pi * planck_j_s * 1e9)
        ec = electron_charge_c**2 / (2 * inputs.capacitance_f * planck_j_s * 1e9)
        ratio = ej / ec
        transmon = scqubits.Transmon(EJ=ej, EC=ec, ng=inputs.ng, ncut=inputs.ncut)
        raw = transmon.eigenvals(evals_count=inputs.n_evals)
        levels = [float(value - raw[0]) for value in raw]
        if len(levels) != inputs.n_evals or not all(math.isfinite(x) for x in levels):
            raise ValueError("scqubits returned an incomplete or non-finite spectrum")
        if any(b <= a for a, b in zip(levels, levels[1:])):
            raise ValueError("scqubits spectrum is not strictly increasing")
        f01, f12 = levels[1], levels[2] - levels[1]
        alpha = (f12 - f01) * 1000
        warnings = ["Executed spectrum; cutoff convergence and reference comparison are pending."]
        if ratio < 10.0:
            warnings.append(f"EJ/EC = {ratio:.1f} < 10: charge-qubit regime, not transmon-like")
        if abs(f12 - f01) < 1e-6:
            warnings.append("f12 ≈ f01: accidental degeneracy — check EJ/EC and inputs")
        valid = abs(alpha) >= 10.0
        quantities = {
            "ej_ghz": ej, "ec_ghz": ec, "ej_ec_ratio": ratio,
            "transmon_regime": ratio >= 10.0,
            "f01_ghz": f01, "f12_ghz": f12, "anharmonicity_mhz": alpha,
            "energy_levels_ghz": levels,
        }
        payload = {
            "schema": "textlayout.scqubits-transmon.v1",
            "status": "executed" if valid else "failed",
            "engine": "scqubits.Transmon.eigenvals",
            "solver_version": str(scqubits.__version__),
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "parameters": inputs.model_dump(),
            "solver_inputs": {"EJ_GHz": ej, "EC_GHz": ec, "ng": inputs.ng,
                              "ncut": inputs.ncut, "n_evals": inputs.n_evals},
            "lineage": {"EJ": "Phi0 * ic_a / (2*pi*h), GHz",
                        "EC": "e^2 / (2*capacitance_f*h), GHz",
                        "source": "explicit SI inputs; extraction provenance is caller-owned",
                        "constants": {"h_j_s": planck_j_s, "e_c": electron_charge_c,
                                      "phi0_wb": phi0_weber, "phi0_definition": "h/(2e)"}},
            "quantities": quantities,
            "warnings": warnings,
            "convergence": "NOT_EVALUATED",
            "reference_comparison": "NOT_EVALUATED",
        }
        output = Path(prepared.output_dir) / "scqubits_result.json"
        output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
        artifacts["result"] = str(output)
        return SimulationResult(
            status="executed" if valid else "failed", solver="scqubits",
            readiness_level=3 if valid else prepared.readiness_level,
            reason=("Transmon spectrum from real scqubits diagonalization; not independently validated."
                    if valid else f"Spectrum is harmonic, not transmon: |α|={abs(alpha):.3f} MHz < 10 MHz"),
            output_dir=prepared.output_dir, artifacts=artifacts,
            extracted_quantities=quantities if valid else {}, warnings=tuple(warnings),
            solver_version=str(scqubits.__version__),
            runtime_seconds=time.perf_counter() - started,
        )
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as exc:
        return SimulationResult(
            status="failed", solver="scqubits", readiness_level=prepared.readiness_level,
            reason=f"scqubits transmon execution failed: {exc}",
            output_dir=prepared.output_dir, artifacts=artifacts,
            warnings=prepared.warnings,
        )
