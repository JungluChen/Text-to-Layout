"""Solver execution provenance contract.

Any value labelled simulated must be backed by an executed solver record.  This
module validates the common metadata payload before reports or signoff consume
the number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_SOLVER_FIELDS = {
    "solver",
    "version",
    "input_file",
    "output_file",
    "mesh_size",
    "runtime",
    "convergence",
}

FORBIDDEN_SOLVER_NAMES = {"none", "mock", "mockjj", "ideal", "synthetic", "analytical", "scipy"}


def validate_solver_execution(record: dict[str, Any]) -> dict[str, Any]:
    """Validate that a simulated quantity is owned by a real solver artifact."""
    missing = sorted(REQUIRED_SOLVER_FIELDS - set(record))
    issues: list[str] = []
    if missing:
        issues.append(f"missing solver provenance fields: {', '.join(missing)}")
    solver = str(record.get("solver", "")).strip()
    if solver.lower() in FORBIDDEN_SOLVER_NAMES:
        issues.append(f"forbidden solver label for simulated quantity: {solver!r}")
    for field in ("input_file", "output_file"):
        value = record.get(field)
        if not value or not Path(value).exists():
            issues.append(f"{field} does not exist: {value}")
    convergence = record.get("convergence")
    if isinstance(convergence, dict) and convergence.get("status") in {"failed", "not_run"}:
        issues.append(f"solver convergence is not acceptable: {convergence.get('status')}")
    return {
        "schema": "text-to-gds.solver-execution-contract.v1",
        "passed": not issues,
        "issues": issues,
        "record": record,
    }


def solver_quantity(
    value: float,
    unit: str,
    *,
    provenance: dict[str, Any],
    quantity: str,
) -> dict[str, Any]:
    """Return a simulated quantity only when the solver provenance is valid."""
    validation = validate_solver_execution(provenance)
    if not validation["passed"]:
        return {
            "status": "failed",
            "reason": validation["issues"][0],
            "quantity": quantity,
            "method_label": "simulated",
            "solver_contract": validation,
        }
    return {
        "status": "ok",
        "quantity": quantity,
        "value": float(value),
        "unit": unit,
        "method_label": "simulated",
        "solver_contract": validation,
    }

