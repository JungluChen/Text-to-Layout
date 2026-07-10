"""Extraction-backed low-loop-inductance dc-SQUID flux physics."""

from __future__ import annotations

import math
from typing import Any

from textlayout._legacy.extraction import PHI0_WEBER


def squid_flux_sweep(
    extraction: dict[str, Any],
    *,
    loop_area_um2: float,
    capacitance_f: float,
    mutual_inductance_h: float | None = None,
    points: int = 101,
    flux_span_phi0: float = 0.98,
) -> dict[str, Any]:
    if loop_area_um2 <= 0.0 or capacitance_f <= 0.0:
        raise ValueError("loop area and capacitance must be positive")
    if points < 3:
        raise ValueError("points must be at least 3")
    lj0 = extraction.get("junction", {}).get("lj")
    if lj0 is None or float(lj0) <= 0.0:
        return {"schema": "text-to-gds.squid-physics.v1", "status": "failed", "reason": "missing extracted parameter: junction.lj"}

    rows = []
    start = -flux_span_phi0 / 2.0
    step = flux_span_phi0 / (points - 1)
    for index in range(points):
        flux_phi0 = start + index * step
        cosine = math.cos(math.pi * flux_phi0)
        lj_h = float(lj0) / abs(cosine)
        frequency_hz = 1.0 / (2.0 * math.pi * math.sqrt(lj_h * capacitance_f))
        bias_current_a = (
            flux_phi0 * PHI0_WEBER / mutual_inductance_h
            if mutual_inductance_h is not None and mutual_inductance_h > 0.0
            else None
        )
        rows.append(
            {
                "flux_phi0": flux_phi0,
                "lj_h": lj_h,
                "frequency_hz": frequency_hz,
                "bias_current_a": bias_current_a,
            }
        )
    flux_period_current_a = (
        PHI0_WEBER / mutual_inductance_h
        if mutual_inductance_h is not None and mutual_inductance_h > 0.0
        else None
    )
    return {
        "schema": "text-to-gds.squid-physics.v1",
        "status": "ok",
        "loop_area_um2": loop_area_um2,
        "lj0_h": float(lj0),
        "capacitance_f": capacitance_f,
        "mutual_inductance_h": mutual_inductance_h,
        "flux_period_phi0": 1.0,
        "flux_period_current_a": flux_period_current_a,
        "sweep": rows,
        "lineage": {
            "inductance": "Lj(phi)=Lj0/abs(cos(pi*Phi/Phi0))",
            "frequency": "1/(2*pi*sqrt(Lj(phi)*C))",
            "bias_current": "I=Phi/M when mutual inductance is supplied",
        },
    }
