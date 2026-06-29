"""Lumped JPA parameter synthesis."""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.extraction import PHI0_WEBER


def synthesize_jpa(
    *,
    frequency_ghz: float,
    impedance_ohm: float = 50.0,
    target_gain_db: float = 20.0,
    bandwidth_mhz: float = 200.0,
    junction_count: int = 8,
    jc_ua_per_um2: float = 2.0,
) -> dict[str, Any]:
    if min(frequency_ghz, impedance_ohm, bandwidth_mhz, jc_ua_per_um2) <= 0.0:
        raise ValueError("JPA synthesis inputs must be positive")
    if junction_count < 2:
        raise ValueError("junction_count must be >= 2")
    if bandwidth_mhz >= frequency_ghz * 1000.0:
        raise ValueError(
            f"bandwidth {bandwidth_mhz} MHz cannot meet or exceed the carrier "
            f"{frequency_ghz * 1000.0:.0f} MHz"
        )
    if not 0.0 < target_gain_db <= 40.0:
        raise ValueError(
            f"target_gain_db {target_gain_db} is outside the physical single-stage "
            "parametric-amplifier range (0, 40] dB"
        )
    omega = 2.0 * math.pi * frequency_ghz * 1e9
    capacitance_f = 1.0 / (omega * impedance_ohm)
    inductance_h = 1.0 / (omega * omega * capacitance_f)
    ic_per_junction_a = PHI0_WEBER / (2.0 * math.pi * inductance_h * junction_count)
    junction_area_um2 = ic_per_junction_a / (jc_ua_per_um2 * 1e-6)
    side_um = math.sqrt(max(junction_area_um2, 0.01))
    coupling_q = frequency_ghz * 1000.0 / bandwidth_mhz
    # Gain-bandwidth product gate for a single-pole parametric resonator:
    # sqrt(G_lin) * BW must stay below the carrier, else no physical operating point.
    gain_lin = 10.0 ** (target_gain_db / 20.0)
    gbp_hz = gain_lin * bandwidth_mhz * 1e6
    if gbp_hz >= frequency_ghz * 1e9:
        raise ValueError(
            f"gain-bandwidth product {gbp_hz / 1e9:.2f} GHz exceeds the carrier "
            f"{frequency_ghz} GHz; reduce target_gain_db or bandwidth_mhz"
        )
    if capacitance_f <= 0.0 or inductance_h <= 0.0:
        raise ValueError("synthesized LC values must be positive")
    return {
        "schema": "text-to-gds.synthesis.jpa.v1",
        "status": "ready",
        "frequency_ghz": frequency_ghz,
        "impedance_ohm": impedance_ohm,
        "target_gain_db": target_gain_db,
        "bandwidth_mhz": bandwidth_mhz,
        "capacitance_f": capacitance_f,
        "capacitance_ff": capacitance_f * 1e15,
        "squid_array_inductance_h": inductance_h,
        "squid_array_inductance_ph": inductance_h * 1e12,
        "junction_count": junction_count,
        "ic_per_junction_a": ic_per_junction_a,
        "ic_per_junction_ua": ic_per_junction_a * 1e6,
        "junction_area_um2": junction_area_um2,
        "junction_width_um": side_um,
        "junction_height_um": side_um,
        "coupling_q": coupling_q,
        "lineage": {
            "C": "C = 1/(omega*Z)",
            "L": "L = 1/(omega^2*C)",
            "Ic": "Ic = Phi0/(2*pi*L_total*N)",
            "area": "area = Ic/Jc",
            "Q": "Q = f0/BW",
        },
    }
