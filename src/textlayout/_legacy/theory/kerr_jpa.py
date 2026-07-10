from __future__ import annotations

import numpy as np


def kerr_jpa_gain(
    detuning_hz: float | np.ndarray,
    *,
    kappa_hz: float,
    pump_coupling_hz: float,
) -> np.ndarray:
    """Stable small-signal Kerr/degenerate-paramp power gain."""
    if kappa_hz <= 0.0 or pump_coupling_hz < 0.0:
        raise ValueError("kappa_hz must be positive and pump_coupling_hz non-negative")
    detuning = np.asarray(detuning_hz, dtype=float)
    mismatch = detuning**2 + kappa_hz**2 / 4.0 - pump_coupling_hz**2
    denominator = mismatch**2 + (kappa_hz * detuning) ** 2
    return 1.0 + (kappa_hz * pump_coupling_hz) ** 2 / np.maximum(denominator, 1e-30)


def gain_bandwidth_product(gain_power: float, bandwidth_hz: float) -> float:
    if gain_power < 1.0 or bandwidth_hz <= 0.0:
        raise ValueError("gain_power must be >= 1 and bandwidth_hz positive")
    return float(np.sqrt(gain_power) * bandwidth_hz)
