from __future__ import annotations

import math
from typing import Any

PHI0_WEBER = 2.067833848e-15


def critical_current_ua(junction_area_um2: float, jc_ua_per_um2: float) -> float:
    """Return critical current in microamps from area and critical current density."""
    if junction_area_um2 < 0:
        raise ValueError(f"junction_area_um2 must be non-negative, got {junction_area_um2}")
    if jc_ua_per_um2 <= 0:
        raise ValueError(f"jc_ua_per_um2 must be positive, got {jc_ua_per_um2}")
    return junction_area_um2 * jc_ua_per_um2


def josephson_inductance_ph(critical_current_ua: float) -> float | None:
    """Return ideal zero-phase small-signal Josephson inductance in picohenries."""
    if critical_current_ua < 0:
        raise ValueError(f"critical_current_ua must be non-negative, got {critical_current_ua}")
    if critical_current_ua == 0:
        return None
    critical_current_a = critical_current_ua * 1e-6
    return PHI0_WEBER / (2.0 * math.pi * critical_current_a) * 1e12


def simulate_ideal_junction(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
) -> dict[str, float | None]:
    """Compute ideal JJ quantities from Text-to-GDS sidecar metadata."""
    if shunt_capacitance_ff < 0:
        raise ValueError(f"shunt_capacitance_ff must be non-negative, got {shunt_capacitance_ff}")

    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    return {
        "junction_area_um2": area_um2,
        "jc_ua_per_um2": jc_ua_per_um2,
        "critical_current_ua": ic_ua,
        "josephson_inductance_ph": josephson_inductance_ph(ic_ua),
        "shunt_capacitance_ff": shunt_capacitance_ff,
    }

