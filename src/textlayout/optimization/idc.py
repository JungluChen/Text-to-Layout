"""Closed-loop analytical sizing for an interdigital capacitor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from textlayout.research.formulas import idc_capacitance_pf


@dataclass(frozen=True, slots=True)
class IDCIteration:
    iteration: int
    finger_pairs: int
    overlap_um: float
    gap_um: float
    finger_width_um: float
    estimate_pf: float
    error_pct: float


@dataclass(frozen=True, slots=True)
class IDCOptimizationResult:
    target_pf: float
    tolerance_pct: float
    converged: bool
    parameters: dict[str, float | int | str]
    estimate_pf: float
    error_pct: float
    iterations: tuple[IDCIteration, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "textlayout.idc-optimization.v1",
            "target_capacitance_pf": self.target_pf,
            "tolerance_pct": self.tolerance_pct,
            "converged": self.converged,
            "parameters": self.parameters,
            "analytical_estimate_pf": self.estimate_pf,
            "analytical_error_pct": self.error_pct,
            "iterations": [asdict(item) for item in self.iterations],
        }


def optimize_idc(
    *,
    target_capacitance_pf: float,
    frequency_ghz: float | None,
    substrate_epsilon_r: float,
    min_width_um: float,
    min_gap_um: float,
    initial_geometry: dict[str, float | int] | None = None,
    tolerance_pct: float = 1.0,
    max_iterations: int = 20,
) -> IDCOptimizationResult:
    """Tune IDC geometry until the Bahl/Alley estimate meets the target.

    Finger count is discrete. Overlap removes the residual error exactly within
    manufacturing-grid precision. Gap and width remain explicit optimization
    variables, clamped to process minima; the cited Bahl/Alley expression does
    not justify inventing a gap/width dependence.
    """
    if target_capacitance_pf <= 0 or substrate_epsilon_r <= 1:
        raise ValueError("target capacitance must be positive and epsilon_r must exceed one")
    if min_width_um <= 0 or min_gap_um <= 0 or tolerance_pct <= 0:
        raise ValueError("design rules and tolerance must be positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least one")
    if frequency_ghz is not None and frequency_ghz <= 0:
        raise ValueError("frequency must be positive")

    initial = initial_geometry or {}
    width = max(float(initial.get("finger_width_um", min_width_um)), min_width_um)
    gap = max(float(initial.get("gap_um", min_gap_um)), min_gap_um)
    overlap = max(float(initial.get("overlap_um", 200.0)), min_width_um)
    pairs = max(int(initial.get("finger_pairs", 8)), 2)
    history: list[IDCIteration] = []

    for iteration in range(max_iterations):
        estimate = idc_capacitance_pf(pairs, overlap, substrate_epsilon_r)
        error_pct = 100.0 * (estimate - target_capacitance_pf) / target_capacitance_pf
        history.append(IDCIteration(iteration, pairs, overlap, gap, width, estimate, error_pct))
        if abs(error_pct) <= tolerance_pct:
            break

        # First use the discrete area lever. Then scale overlap to remove the
        # quantization residual. This remains deterministic and auditable.
        ratio = target_capacitance_pf / estimate
        if iteration == 0 and (ratio > 1.25 or ratio < 0.8):
            pairs = max(2, min(2000, int(math.ceil(pairs * ratio))))
        else:
            overlap = max(min_width_um, round(overlap * ratio, 3))

    final = history[-1]
    parameters: dict[str, float | int | str] = {
        "finger_pairs": final.finger_pairs,
        "finger_width_um": final.finger_width_um,
        "gap_um": final.gap_um,
        "overlap_um": final.overlap_um,
        "bus_width_um": max(10.0, 5.0 * final.finger_width_um),
        "metal_layer": "M1",
    }
    return IDCOptimizationResult(
        target_pf=target_capacitance_pf,
        tolerance_pct=tolerance_pct,
        converged=abs(final.error_pct) <= tolerance_pct,
        parameters=parameters,
        estimate_pf=final.estimate_pf,
        error_pct=final.error_pct,
        iterations=tuple(history),
    )
