"""Geometry-backed coplanar-waveguide synthesis and validation."""

from __future__ import annotations

import math
from typing import Any

C0_M_PER_S = 299_792_458.0


def complete_elliptic_k(modulus: float) -> float:
    if not 0.0 < modulus < 1.0:
        raise ValueError("elliptic modulus must satisfy 0 < k < 1")
    a = 1.0
    b = math.sqrt(1.0 - modulus * modulus)
    for _ in range(60):
        next_a = (a + b) / 2.0
        next_b = math.sqrt(a * b)
        if abs(next_a - next_b) <= 1e-15:
            return math.pi / (2.0 * next_a)
        a, b = next_a, next_b
    return math.pi / (2.0 * a)


def synthesize_cpw(
    *,
    center_width_um: float,
    gap_um: float,
    ground_width_um: float,
    epsilon_r: float,
    substrate_thickness_um: float,
    frequency_ghz: float,
    target_impedance_ohm: float = 50.0,
    impedance_tolerance_ohm: float = 2.5,
    substrate: str = "unspecified",
) -> dict[str, Any]:
    """Calculate finite-substrate CPW Z0, epsilon_eff, velocity, and lambda/4 length."""
    named = {
        "center_width_um": center_width_um,
        "gap_um": gap_um,
        "ground_width_um": ground_width_um,
        "epsilon_r": epsilon_r,
        "substrate_thickness_um": substrate_thickness_um,
        "frequency_ghz": frequency_ghz,
        "target_impedance_ohm": target_impedance_ohm,
        "impedance_tolerance_ohm": impedance_tolerance_ohm,
    }
    for name, value in named.items():
        if not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
    if ground_width_um < center_width_um:
        raise ValueError("ground_width_um must be at least center_width_um")

    width = center_width_um
    gap = gap_um
    height = substrate_thickness_um
    k = width / (width + 2.0 * gap)
    k_prime = math.sqrt(1.0 - k * k)
    sinh_denominator = math.sinh(math.pi * (width + 2.0 * gap) / (4.0 * height))
    k1 = math.sinh(math.pi * width / (4.0 * height)) / sinh_denominator
    k1 = min(max(k1, 1e-12), 1.0 - 1e-12)
    k1_prime = math.sqrt(1.0 - k1 * k1)

    ratio_air = complete_elliptic_k(k_prime) / complete_elliptic_k(k)
    substrate_factor = (
        complete_elliptic_k(k1)
        / complete_elliptic_k(k1_prime)
        * ratio_air
    )
    epsilon_effective = 1.0 + (epsilon_r - 1.0) * substrate_factor / 2.0
    impedance = 30.0 * math.pi * ratio_air / math.sqrt(epsilon_effective)
    phase_velocity = C0_M_PER_S / math.sqrt(epsilon_effective)
    quarter_wave_length_m = phase_velocity / (4.0 * frequency_ghz * 1e9)
    error = abs(impedance - target_impedance_ohm)
    passed = error <= impedance_tolerance_ohm

    return {
        "schema": "text-to-gds.cpw-physics.v1",
        "status": "ok" if passed else "failed",
        "reason": None if passed else "CPW impedance is outside tolerance",
        "geometry": {
            "center_width_um": center_width_um,
            "gap_um": gap_um,
            "ground_width_um": ground_width_um,
        },
        "substrate": {
            "name": substrate,
            "epsilon_r": epsilon_r,
            "thickness_um": substrate_thickness_um,
        },
        "frequency_ghz": frequency_ghz,
        "impedance_ohm": impedance,
        "effective_permittivity": epsilon_effective,
        "phase_velocity_m_per_s": phase_velocity,
        "quarter_wave_length_um": quarter_wave_length_m * 1e6,
        "validation": {
            "target_impedance_ohm": target_impedance_ohm,
            "absolute_error_ohm": error,
            "tolerance_ohm": impedance_tolerance_ohm,
            "passed": passed,
        },
        "lineage": {
            "impedance": "30*pi/sqrt(epsilon_eff) * K(k')/K(k)",
            "phase_velocity": "c0/sqrt(epsilon_eff)",
            "quarter_wave_length": "phase_velocity/(4*frequency)",
        },
    }
