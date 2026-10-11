"""Recompute bounded SQcircuit LC checks from raw arrays; no evidence promotion."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from textlayout.external.sqcircuit_lc import SQcircuitLCPlan


class SQcircuitLCAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    numerical_checks_passed: bool
    max_reference_error_hz: float
    last_refinement_hz: float
    max_scaled_residual: float
    max_relative_hermiticity: float
    max_orthonormality_error: float
    capacitance_matches: bool


def _array(value: Any, shape: tuple[int, ...]) -> NDArray[np.float64]:
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in "fiu":
        raise ValueError("Raw component has wrong shape or nonnumeric type")
    return np.asarray(array, dtype=np.float64)


def assess_sqcircuit_lc(
    plan: SQcircuitLCPlan, rows: list[dict[str, Any]]
) -> SQcircuitLCAssessment:
    """Check raw arrays, never trusting precomputed worker pass flags.

    Malformed/nonfinite/zero-norm input raises ValueError. Finite numerical
    disagreement returns a failed assessment. This verifies no process, source,
    platform, geometry or measurement identity and emits no canonical quantity.
    """
    plan = SQcircuitLCPlan.model_validate_json(plan.model_dump_json())
    if len(rows) != len(plan.truncations):
        raise ValueError("Exactly three ordered truncation rows required")
    request = plan.request
    total_c = request.capacitance_f + request.branch_capacitance_f
    reference = np.arange(plan.levels) / (
        2 * math.pi * math.sqrt(total_c * request.inductance_h)
    )
    errors, residuals, hermiticities, orthogonalities, spectra = [], [], [], [], []
    capacitance_matches = True
    for size, row in zip(plan.truncations, rows):
        if type(row.get("truncation")) is not int or row["truncation"] != size:
            raise ValueError("Wrong or reordered truncation")
        try:
            matrix = _array(row["hamiltonian_rad_s_real"], (size, size)) + 1j * _array(
                row["hamiltonian_rad_s_imag"], (size, size)
            )
            vectors = _array(row["eigenvectors_real"], (size, plan.levels)) + 1j * _array(
                row["eigenvectors_imag"], (size, plan.levels)
            )
            values = _array(row["eigenvalues_rad_s"], (plan.levels,))
            capacitance = row["resolved_capacitance_f"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Malformed raw eigenpair arrays") from exc
        if (
            matrix.shape != (size, size)
            or vectors.shape != (size, plan.levels)
            or values.shape != (plan.levels,)
            or not all(np.isfinite(a).all() for a in (matrix, vectors, values))
            or type(capacitance) not in (int, float)
            or not math.isfinite(capacitance)
        ):
            raise ValueError("Invalid shape or nonfinite raw data")
        norm = float(np.linalg.norm(matrix))
        vector_norms = np.linalg.norm(vectors, axis=0)
        if not math.isfinite(norm) or norm <= 0 or np.any(vector_norms <= 0):
            raise ValueError("Zero or invalid matrix/eigenvector norm")
        if np.any(np.diff(values) <= 0):
            raise ValueError("LC eigenvalues must be strictly increasing")
        excitation = (values - values[0]) / (2 * math.pi)
        errors.append(float(np.max(np.abs(excitation - reference))))
        residuals.append(float(np.max(
            np.linalg.norm(matrix @ vectors - vectors * values, axis=0) / (norm * vector_norms)
        )))
        hermiticities.append(float(np.linalg.norm(matrix - matrix.conj().T) / norm))
        orthogonalities.append(float(np.max(np.abs(
            vectors.conj().T @ vectors - np.eye(plan.levels)
        ))))
        spectra.append(excitation)
        capacitance_matches = capacitance_matches and capacitance == total_c
    metrics = {
        "max_reference_error_hz": max(errors),
        "last_refinement_hz": float(np.max(np.abs(spectra[-1] - spectra[-2]))),
        "max_scaled_residual": max(residuals),
        "max_relative_hermiticity": max(hermiticities),
        "max_orthonormality_error": max(orthogonalities),
    }
    if not all(math.isfinite(value) for value in metrics.values()):
        raise ValueError("Nonfinite diagnostic metric")
    passed = (
        capacitance_matches
        and metrics["max_reference_error_hz"] <= plan.reference_limit_hz
        and metrics["last_refinement_hz"] <= plan.reference_limit_hz
        and metrics["max_scaled_residual"] <= plan.scaled_residual_limit
        and metrics["max_relative_hermiticity"] <= plan.hermiticity_limit
        # Algebraic normalization budget, fixed before assessment acceptance.
        and metrics["max_orthonormality_error"] <= 1e-12
    )
    return SQcircuitLCAssessment(
        numerical_checks_passed=passed, capacitance_matches=capacitance_matches, **metrics
    )
