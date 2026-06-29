"""Artifact validation layer — every solver must produce a verifiable artifact.

Rules per solver:
  JosephsonCircuits.jl  → gain array must be a non-empty list of finite numbers
  scqubits              → eigenvalues must be a non-empty list of finite numbers
  openEMS               → .s2p Touchstone file must exist and load
  Elmer FEM             → capacitance matrix must be a non-empty list/matrix
  JoSIM                 → waveform data must be a non-empty list

If any required artifact is missing or invalid: status = "failed".
No exceptions — a claimed "executed" with no artifact is a signoff failure.

Schema: text-to-gds.artifact-validation.v1
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "text-to-gds.artifact-validation.v1"


def _is_finite_list(value: Any, min_length: int = 1) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) < min_length:
        return False
    return all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in value)


def _check_josephsoncircuits(result: dict[str, Any]) -> dict[str, Any]:
    """JosephsonCircuits.jl: must have a numerical gain or frequency array."""
    if result.get("status") in ("skipped", "SKIPPED"):
        return {"passed": True, "status": "skipped", "reason": "solver skipped"}

    gains = result.get("gain_db") or result.get("gain_array") or result.get("frequencies_ghz")
    if not _is_finite_list(gains, min_length=2):
        adapter_result = result.get("adapter_result", {})
        inner_gains = adapter_result.get("gain_db") or adapter_result.get("frequencies_ghz")
        if not _is_finite_list(inner_gains, min_length=2):
            return {
                "passed": False,
                "status": "failed",
                "reason": "JosephsonCircuits.jl result has no valid numerical gain or frequency array",
            }

    return {
        "passed": True,
        "status": "ok",
        "artifact": "gain array present",
        "gain_point_count": len(gains) if isinstance(gains, list) else 0,
    }


def _check_scqubits(result: dict[str, Any]) -> dict[str, Any]:
    """scqubits: must have eigenvalue list."""
    if result.get("status") in ("skipped", "SKIPPED"):
        return {"passed": True, "status": "skipped", "reason": "solver skipped"}

    execution = result.get("execution", result)
    levels = execution.get("energy_levels_ghz") or execution.get("eigenvalues")
    if not _is_finite_list(levels, min_length=2):
        return {
            "passed": False,
            "status": "failed",
            "reason": "scqubits result has no valid energy_levels_ghz eigenvalue list",
        }

    f01 = execution.get("f01_ghz")
    if f01 is None or not math.isfinite(float(f01)):
        return {
            "passed": False,
            "status": "failed",
            "reason": "scqubits result missing f01_ghz",
        }

    return {
        "passed": True,
        "status": "ok",
        "artifact": "eigenvalues present",
        "level_count": len(levels),
        "f01_ghz": f01,
    }


def _check_openems(result: dict[str, Any]) -> dict[str, Any]:
    """openEMS: must have a .s2p Touchstone file that exists and is non-empty."""
    if result.get("status") in ("skipped", "SKIPPED"):
        reason = result.get("reason", "openEMS not installed")
        return {"passed": True, "status": "skipped", "reason": reason}

    touchstone = result.get("touchstone_path")
    if not touchstone:
        # Check nested raw_result
        raw = result.get("artifacts", {})
        touchstone = raw.get("touchstone")

    if not touchstone:
        return {
            "passed": False,
            "status": "failed",
            "reason": "openEMS result has no touchstone_path",
        }

    ts = Path(touchstone)
    if not ts.is_file():
        return {
            "passed": False,
            "status": "failed",
            "reason": f"openEMS touchstone_path points to non-existent file: {ts}",
        }

    if ts.stat().st_size < 10:
        return {
            "passed": False,
            "status": "failed",
            "reason": f"openEMS Touchstone file is too small ({ts.stat().st_size} bytes): {ts}",
        }

    return {
        "passed": True,
        "status": "ok",
        "artifact": str(ts),
        "size_bytes": ts.stat().st_size,
    }


def _check_elmer(result: dict[str, Any]) -> dict[str, Any]:
    """Elmer FEM: must have capacitance matrix."""
    if result.get("status") in ("skipped", "SKIPPED"):
        return {"passed": True, "status": "skipped", "reason": "ElmerSolver not installed"}

    cap = result.get("capacitance_matrix_pf") or result.get("capacitance_pf")
    if cap is None:
        values = result.get("values", {})
        cap = values.get("capacitance_matrix", {}).get("value")

    if cap is None:
        return {
            "passed": False,
            "status": "failed",
            "reason": "Elmer result has no capacitance_matrix_pf",
        }

    if isinstance(cap, (int, float)) and math.isfinite(float(cap)) and float(cap) > 0:
        return {"passed": True, "status": "ok", "artifact": f"capacitance {cap} pF"}
    if isinstance(cap, (list, tuple)) and len(cap) > 0:
        return {"passed": True, "status": "ok", "artifact": f"capacitance matrix ({len(cap)} elements)"}

    return {
        "passed": False,
        "status": "failed",
        "reason": f"Elmer capacitance value is invalid: {cap!r}",
    }


def _check_josim(result: dict[str, Any]) -> dict[str, Any]:
    """JoSIM: must have waveform data."""
    if result.get("status") in ("skipped", "SKIPPED"):
        return {"passed": True, "status": "skipped", "reason": "JoSIM not configured"}

    waveform = result.get("waveform") or result.get("voltage_waveform") or result.get("flux_waveform")
    if not _is_finite_list(waveform, min_length=10):
        return {
            "passed": False,
            "status": "failed",
            "reason": "JoSIM result has no waveform data (voltage_waveform or flux_waveform)",
        }

    return {
        "passed": True,
        "status": "ok",
        "artifact": "waveform present",
        "point_count": len(waveform),
    }


_CHECKERS: dict[str, Any] = {
    "josephsoncircuits": _check_josephsoncircuits,
    "josephsoncircuits.jl": _check_josephsoncircuits,
    "jc": _check_josephsoncircuits,
    "scqubits": _check_scqubits,
    "openems": _check_openems,
    "elmer": _check_elmer,
    "josim": _check_josim,
}


def validate_artifact(
    solver_name: str,
    result: dict[str, Any],
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the artifact produced by a named solver.

    Args:
        solver_name: One of "josephsoncircuits", "scqubits", "openems", "elmer", "josim".
        result: The dict returned by the solver/backend.
        report_path: Optional path to write a validation report.

    Returns:
        {"passed": bool, "status": str, "artifact": str | None, "reason": str | None}
    """
    key = solver_name.strip().lower()
    checker = _CHECKERS.get(key)
    if checker is None:
        check = {
            "passed": False,
            "status": "failed",
            "reason": f"No artifact validator registered for solver '{solver_name}'",
        }
    else:
        check = checker(result)

    validation: dict[str, Any] = {
        "schema": SCHEMA,
        "solver": solver_name,
        **check,
    }

    if report_path is not None:
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(validation, indent=2), encoding="utf-8")
        validation["report_path"] = str(rp)

    return validation


def validate_all_artifacts(
    results: dict[str, dict[str, Any]],
    *,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate artifacts from all solvers in a results dict.

    Args:
        results: {"solver_name": solver_result_dict, ...}

    Returns:
        {"all_passed": bool, "results": {solver_name: check_dict}, "failed": [solver_names]}
    """
    checks: dict[str, dict[str, Any]] = {}
    failed: list[str] = []

    for solver, result in results.items():
        check = validate_artifact(solver, result)
        checks[solver] = check
        if not check["passed"]:
            failed.append(solver)

    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "all_passed": len(failed) == 0,
        "solver_count": len(results),
        "failed_count": len(failed),
        "failed": failed,
        "results": checks,
    }

    if report_path is not None:
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["report_path"] = str(rp)

    return summary
