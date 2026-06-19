from __future__ import annotations

import numpy as np


def four_wave_mixing_gain(
    phase_mismatch_per_m: float | np.ndarray,
    *,
    nonlinear_phase_per_m: float,
    length_m: float,
) -> np.ndarray:
    """Undepleted-pump degenerate 4WM signal power gain."""
    mismatch = np.asarray(phase_mismatch_per_m, dtype=float) + 2.0 * nonlinear_phase_per_m
    coupling = abs(nonlinear_phase_per_m)
    if length_m <= 0.0:
        raise ValueError("length_m must be positive")
    growth = np.sqrt(coupling**2 - (mismatch / 2.0) ** 2 + 0j)
    ratio = np.where(np.abs(growth) > 1e-15, np.sinh(growth * length_m) / growth, length_m)
    return 1.0 + np.abs(coupling * ratio) ** 2
