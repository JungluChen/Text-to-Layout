from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def solve_jpa_model(
    *,
    lj_h: float,
    capacitance_f: float,
    kappa_hz: float,
    pump_strength_hz: float,
    frequency_span_hz: float = 500e6,
    points: int = 401,
    pump_points: int = 41,
    input_1db_power_dbm: float = -120.0,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compatibility shim for the removed custom JPA gain solver.

    JPA/JTWPA/SQUID gain must be produced by JosephsonCircuits.jl through
    textlayout._legacy.backends.JosephsonCircuitsBackend or textlayout._legacy.josephsoncircuits_adapter.
    Analytical Kerr equations remain available under textlayout._legacy.theory as sanity checks,
    but this API no longer reports them as simulated device performance.
    """
    payload = {
        "schema": "text-to-gds.jpa-report.v1",
        "status": "skipped",
        "reason": (
            "Custom analytical JPA gain solver removed. Use JosephsonCircuits.jl "
            "for pump sweeps, gain, compression, and stability."
        ),
        "backend": "JosephsonCircuits.jl",
        "source_url": "https://github.com/kpobrien/JosephsonCircuits.jl",
        "values": {},
        "rejected_inputs": {
            "lj_h": lj_h,
            "capacitance_f": capacitance_f,
            "kappa_hz": kappa_hz,
            "pump_strength_hz": pump_strength_hz,
            "frequency_span_hz": frequency_span_hz,
            "points": points,
            "pump_points": pump_points,
            "input_1db_power_dbm": input_1db_power_dbm,
        },
        "next_step": (
            "Run JosephsonCircuitsBackend.simulate with extraction_path and "
            "mode='jpa'. Every returned gain value will then have source="
            "JosephsonCircuits.jl, method=harmonic-balance pump sweep."
        ),
    }
    if report_path is not None:
        out = Path(report_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(out)
    return payload
