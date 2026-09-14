"""Scale-invariant, process-constrained quasi-static CPW synthesis with SciPy."""

from __future__ import annotations

import math

from scipy.optimize import brentq  # type: ignore[import-untyped]
from scipy.special import ellipk, ellipkm1  # type: ignore[import-untyped]


def size_cpw(
    target_ohm: float,
    epsilon_r: float,
    *,
    min_width_um: float,
    min_gap_um: float,
    preferred_width_um: float = 10.0,
) -> dict[str, float]:
    """Solve Z0, then scale width and gap together to satisfy both minima.

    Assumes a thick substrate, zero-thickness metal and no kinetic inductance.
    This is an analytical design seed, never field-solver verification.
    """
    values = (target_ohm, epsilon_r, min_width_um, min_gap_um, preferred_width_um)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("CPW targets, permittivity and dimensions must be finite and positive")

    def objective(log_ratio: float) -> float:
        ratio = math.exp(log_ratio)  # gap / width
        k = 1.0 / (1.0 + 2.0 * ratio)
        impedance = 30 * math.pi / math.sqrt((epsilon_r + 1) / 2)
        impedance *= float(ellipkm1(k * k) / ellipk(k * k))
        return impedance - target_ohm

    lower, upper = math.log(1e-5), math.log(1e5)
    if objective(lower) * objective(upper) > 0:
        raise ValueError("Requested CPW impedance is outside the supported aspect-ratio range")
    ratio = math.exp(float(brentq(objective, lower, upper, xtol=1e-13)))
    width = max(preferred_width_um, min_width_um, min_gap_um / ratio)
    # Centered gdsfactory ports require an even number of 1 nm database units.
    # Round upward so snapping cannot violate a process minimum.
    width = math.ceil(width * 500) / 500
    gap = math.ceil(max(min_gap_um, ratio * width) * 1000) / 1000
    return {"center_width_um": width, "gap_um": gap, "length_um": 1000.0}
