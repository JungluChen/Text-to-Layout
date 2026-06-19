from __future__ import annotations

import numpy as np


def three_wave_mixing_gain(
    phase_mismatch_per_m: float | np.ndarray,
    *,
    coupling_per_m: float,
    length_m: float,
) -> np.ndarray:
    """Undepleted-pump 3WM signal power gain."""
    if coupling_per_m < 0.0 or length_m <= 0.0:
        raise ValueError("coupling must be non-negative and length positive")
    mismatch = np.asarray(phase_mismatch_per_m, dtype=float)
    growth = np.sqrt(coupling_per_m**2 - (mismatch / 2.0) ** 2 + 0j)
    ratio = np.where(np.abs(growth) > 1e-15, np.sinh(growth * length_m) / growth, length_m)
    return 1.0 + np.abs(coupling_per_m * ratio) ** 2
