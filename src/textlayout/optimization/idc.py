"""Closed-loop IDC parameter tuning against a target capacitance.

The loop uses the cited Bahl/Alley closed form (``research.formulas``) as its
objective. That model is a *design guide* — every result here is
``ANALYTICAL_ONLY`` by construction and is never reported as physics
verification. The solver flow (Phase 5) is the only path to
``SIMULATION_EXECUTED`` / ``PHYSICS_VERIFIED``.

Tunable knobs, in the order the loop reaches for them:

1. ``finger_pairs`` — coarse, integer, capacitance ~linear in N.
2. ``overlap_um``  — fine, continuous, capacitance exactly linear in overlap.

Width and gap are honoured as *constraints* (process rules or explicit user
values), not tuned: shrinking the gap below the stated minimum to hit a target
would produce an unmanufacturable answer.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.research import formulas as F

OPTIMIZATION_SCHEMA = "textlayout.idc-optimization.v1"

_MIN_PAIRS, _MAX_PAIRS = 2, 2000
_MIN_OVERLAP_UM, _MAX_OVERLAP_UM = 20.0, 2000.0
_DEFAULTS: dict[str, float] = {
    "finger_width_um": 4.0,
    "gap_um": 2.0,
    "overlap_um": 250.0,
    "bus_width_um": 25.0,
}


class IDCOptimizationResult(BaseModel):
    """Full record of the tuning loop — inputs, every iteration, and outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=OPTIMIZATION_SCHEMA)
    converged: bool
    method: str = Field(
        default="Bahl/Alley quasi-static closed form — ANALYTICAL_ONLY, not a solver result"
    )
    target_capacitance_pf: float
    estimated_capacitance_pf: float
    error_percent: float
    tolerance_percent: float
    iterations: list[dict[str, float | int]]
    final_parameters: dict[str, Any]
    fixed_parameters: list[str]
    solver_iterations: list[dict[str, Any]] = Field(default_factory=list)
    final_basis: str = "analytical"
    notes: list[str] = Field(default_factory=list)


def optimize_idc(
    *,
    target_capacitance_pf: float,
    substrate_epsilon_r: float,
    min_finger_width_um: float = 2.0,
    min_gap_um: float = 2.0,
    initial_parameters: dict[str, Any] | None = None,
    tolerance_percent: float = 5.0,
    max_iterations: int = 20,
) -> IDCOptimizationResult:
    """Tune IDC parameters until the analytical estimate is within tolerance.

    Parameters the caller supplies in ``initial_parameters`` are treated as
    user-fixed and are not tuned; the loop only adjusts the free knobs. The
    loop fails safely (``converged=False`` with an explanatory note) instead of
    violating a bound or a user-fixed value.
    """
    if target_capacitance_pf <= 0:
        raise ValueError("target capacitance must be positive")
    if tolerance_percent <= 0:
        raise ValueError("tolerance must be positive")

    supplied = dict(initial_parameters or {})
    fixed = sorted(k for k in supplied if k in {"finger_pairs", "overlap_um"})
    notes: list[str] = []

    width = max(
        float(supplied.get("finger_width_um", _DEFAULTS["finger_width_um"])), min_finger_width_um
    )
    gap = max(float(supplied.get("gap_um", _DEFAULTS["gap_um"])), min_gap_um)
    if width != supplied.get("finger_width_um", width):
        notes.append(f"finger_width_um raised to process minimum {min_finger_width_um} um.")
    if gap != supplied.get("gap_um", gap):
        notes.append(f"gap_um raised to process minimum {min_gap_um} um.")
    bus = float(supplied.get("bus_width_um", _DEFAULTS["bus_width_um"]))
    metal_layer = str(supplied.get("metal_layer", "M1"))

    overlap = float(supplied.get("overlap_um", _DEFAULTS["overlap_um"]))
    pairs_fixed = "finger_pairs" in supplied
    overlap_fixed = "overlap_um" in supplied
    if pairs_fixed:
        pairs = int(supplied["finger_pairs"])
    else:
        pairs = _clamp_pairs(
            F.idc_finger_pairs_for_target(target_capacitance_pf, overlap, substrate_epsilon_r)
        )

    history: list[dict[str, float | int]] = []
    best: tuple[float, int, float] | None = None  # (error, pairs, overlap)

    for iteration in range(1, max_iterations + 1):
        estimate = F.idc_capacitance_pf(pairs, overlap, substrate_epsilon_r)
        error = abs(estimate - target_capacitance_pf) / target_capacitance_pf * 100.0
        history.append(
            {
                "iteration": iteration,
                "finger_pairs": pairs,
                "overlap_um": round(overlap, 4),
                "estimated_capacitance_pf": round(estimate, 6),
                "error_percent": round(error, 4),
            }
        )
        if best is None or error < best[0]:
            best = (error, pairs, overlap)
        if error <= tolerance_percent:
            break

        if not overlap_fixed:
            # Capacitance is exactly linear in overlap: one scaling step lands on
            # target unless a bound intervenes.
            overlap = _clamp(
                overlap * target_capacitance_pf / estimate, _MIN_OVERLAP_UM, _MAX_OVERLAP_UM
            )
            if not pairs_fixed and overlap in (_MIN_OVERLAP_UM, _MAX_OVERLAP_UM):
                pairs = _clamp_pairs(
                    F.idc_finger_pairs_for_target(
                        target_capacitance_pf, overlap, substrate_epsilon_r
                    )
                )
        elif not pairs_fixed:
            step = 1 if estimate < target_capacitance_pf else -1
            next_pairs = _clamp_pairs(pairs + step)
            if next_pairs == pairs:
                notes.append("finger_pairs hit its bound; no further coarse adjustment possible.")
                break
            pairs = next_pairs
        else:
            notes.append("finger_pairs and overlap_um are both user-fixed; nothing is tunable.")
            break

    assert best is not None
    error, pairs, overlap = best
    estimate = F.idc_capacitance_pf(pairs, overlap, substrate_epsilon_r)
    converged = error <= tolerance_percent
    if not converged:
        notes.append(
            f"Did not converge within {tolerance_percent}% "
            f"(best analytical error {error:.2f}%). Constraints or fixed parameters "
            "prevent reaching the target."
        )

    final = {
        "finger_pairs": pairs,
        "finger_width_um": width,
        "gap_um": gap,
        "overlap_um": round(overlap, 4),
        "bus_width_um": bus,
        "metal_layer": metal_layer,
    }
    if not (math.isfinite(estimate) and estimate > 0):
        raise ValueError(f"analytical model returned a non-physical estimate: {estimate}")

    return IDCOptimizationResult(
        converged=converged,
        target_capacitance_pf=target_capacitance_pf,
        estimated_capacitance_pf=round(estimate, 6),
        error_percent=round(error, 4),
        tolerance_percent=tolerance_percent,
        iterations=history,
        final_parameters=final,
        fixed_parameters=fixed,
        notes=notes,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _clamp_pairs(pairs: int) -> int:
    return max(_MIN_PAIRS, min(_MAX_PAIRS, pairs))
