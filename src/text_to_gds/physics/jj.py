"""Josephson junction physics — consolidated API.

All equations are referenced to their physical source.
source="LLM" is a fatal error here.

References:
  [AB1963] Ambegaokar & Baratoff, PRL 10, 486 (1963)
  [Jos1962] Josephson, Phys. Lett. 1, 251 (1962)
  [Koch2007] Koch et al., PRL 98, 267003 (2007) — transmon
"""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.core.units import (
    BOLTZMANN,
    ELECTRON_CHARGE,
    FLUX_QUANTUM,
    PLANCK_HBAR,
)

# ─── Fundamental JJ equations ──────────────────────────────────────────────────

def ic_from_area(
    area_um2: float,
    jc_ua_per_um2: float,
) -> float:
    """Critical current Ic = Jc * A.

    Parameters
    ----------
    area_um2 : float
        Junction overlap area in µm².
    jc_ua_per_um2 : float
        Critical current density in µA/µm².

    Returns
    -------
    float
        Critical current in Amperes.

    Reference: Josephson (1962), Ic = Jc × A
    """
    if area_um2 <= 0 or jc_ua_per_um2 <= 0:
        raise ValueError("area and Jc must be positive")
    return area_um2 * jc_ua_per_um2 * 1e-6


def lj_from_ic(ic_a: float) -> float:
    """Josephson inductance Lj = Φ₀ / (2π Ic).

    Parameters
    ----------
    ic_a : float
        Critical current in Amperes.

    Returns
    -------
    float
        Josephson inductance in Henries.

    Reference: Jos (1962), Lj = Φ₀/(2πIc)
    """
    if ic_a <= 0:
        raise ValueError("Ic must be positive")
    return FLUX_QUANTUM / (2.0 * math.pi * ic_a)


def ej_from_ic(ic_a: float) -> float:
    """Josephson energy Ej = Ic Φ₀ / (2π) = ℏ Ic / (2e).

    Parameters
    ----------
    ic_a : float
        Critical current in Amperes.

    Returns
    -------
    float
        Josephson energy in Joules.

    Reference: Jos (1962), Ej = ℏIc/(2e)
    """
    if ic_a <= 0:
        raise ValueError("Ic must be positive")
    return PLANCK_HBAR * ic_a / (2.0 * ELECTRON_CHARGE)


def ej_ghz_from_ic(ic_a: float) -> float:
    """Josephson energy in GHz (Ej/h)."""
    return ej_from_ic(ic_a) / (2.0 * math.pi * PLANCK_HBAR) * 1e-9


def ec_from_capacitance(c_f: float) -> float:
    """Charging energy Ec = e² / (2C).

    Parameters
    ----------
    c_f : float
        Total junction capacitance in Farads.

    Returns
    -------
    float
        Charging energy in Joules.

    Reference: Koch et al. (2007), Ec = e²/(2C)
    """
    if c_f <= 0:
        raise ValueError("Capacitance must be positive")
    return ELECTRON_CHARGE ** 2 / (2.0 * c_f)


def ec_ghz_from_capacitance(c_f: float) -> float:
    """Charging energy in GHz (Ec/h)."""
    return ec_from_capacitance(c_f) / (2.0 * math.pi * PLANCK_HBAR) * 1e-9


def plasma_frequency_hz(lj_h: float, c_f: float) -> float:
    """Josephson plasma frequency f_p = 1/(2π√(Lj C)).

    Parameters
    ----------
    lj_h : float
        Josephson inductance in Henries.
    c_f : float
        Junction capacitance in Farads.

    Returns
    -------
    float
        Plasma frequency in Hz.
    """
    if lj_h <= 0 or c_f <= 0:
        raise ValueError("Lj and C must be positive")
    return 1.0 / (2.0 * math.pi * math.sqrt(lj_h * c_f))


def transmon_f01_hz(ej_j: float, ec_j: float) -> float:
    """Transmon f₀₁ ≈ √(8 Ej Ec) - Ec  (valid for Ej/Ec >> 1).

    Parameters
    ----------
    ej_j : float
        Josephson energy in Joules.
    ec_j : float
        Charging energy in Joules.

    Returns
    -------
    float
        01 transition frequency in Hz.

    Reference: Koch et al. (2007), Eq. (2.11)
    """
    if ej_j <= 0 or ec_j <= 0:
        raise ValueError("Ej and Ec must be positive")
    return (math.sqrt(8.0 * ej_j * ec_j) - ec_j) / (2.0 * math.pi * PLANCK_HBAR)


def transmon_anharmonicity_hz(ec_j: float) -> float:
    """Transmon anharmonicity α ≈ -Ec (valid for Ej/Ec >> 1).

    Parameters
    ----------
    ec_j : float
        Charging energy in Joules.

    Returns
    -------
    float
        Anharmonicity in Hz (negative = transmon).

    Reference: Koch et al. (2007)
    """
    return -ec_j / (2.0 * math.pi * PLANCK_HBAR)


def ambegaokar_baratoff(
    *,
    normal_resistance_ohm: float,
    temperature_k: float,
    critical_temperature_k: float,
) -> dict[str, float]:
    """Ambegaokar–Baratoff relation: Ic Rn = (π/2) Δ(T)/e × tanh(Δ/(2kT)).

    Parameters
    ----------
    normal_resistance_ohm : float
        Normal-state resistance of the junction in Ω.
    temperature_k : float
        Operating temperature in K.
    critical_temperature_k : float
        Superconductor critical temperature in K.

    Returns
    -------
    dict with keys: gap_j, critical_current_a, icrn_product_v, normal_resistance_ohm

    Reference: Ambegaokar & Baratoff (1963) [AB1963]
    """
    if normal_resistance_ohm <= 0 or critical_temperature_k <= 0:
        raise ValueError("Rn and Tc must be positive")
    if temperature_k < 0:
        raise ValueError("Temperature must be >= 0")

    if temperature_k >= critical_temperature_k:
        return {
            "gap_j": 0.0,
            "critical_current_a": 0.0,
            "icrn_product_v": 0.0,
            "normal_resistance_ohm": normal_resistance_ohm,
        }

    delta_0 = 1.764 * BOLTZMANN * critical_temperature_k
    t_ratio = temperature_k / critical_temperature_k
    delta_t = delta_0 * math.tanh(1.74 * math.sqrt(max(1.0 / t_ratio - 1.0, 0.0)))

    thermal_factor = math.tanh(delta_t / max(2.0 * BOLTZMANN * max(temperature_k, 1e-12), 1e-40))
    ic = (math.pi * delta_t) / (2.0 * ELECTRON_CHARGE * normal_resistance_ohm) * thermal_factor

    return {
        "gap_j": delta_t,
        "critical_current_a": ic,
        "icrn_product_v": ic * normal_resistance_ohm,
        "normal_resistance_ohm": normal_resistance_ohm,
    }


def junction_capacitance_f(
    *,
    area_um2: float,
    specific_capacitance_ff_per_um2: float,
    fringe_fraction: float = 0.0,
) -> float:
    """Junction capacitance from specific capacitance: C = Cs × A × (1 + fringe).

    Parameters
    ----------
    area_um2 : float
        Junction area in µm².
    specific_capacitance_ff_per_um2 : float
        Specific capacitance (Cs) in fF/µm² (typically 40–80 fF/µm² for AlOx).
    fringe_fraction : float
        Fractional fringe capacitance correction (0 = no fringe).

    Returns
    -------
    float
        Total capacitance in Farads.
    """
    if area_um2 <= 0 or specific_capacitance_ff_per_um2 <= 0:
        raise ValueError("area and Cs must be positive")
    return area_um2 * specific_capacitance_ff_per_um2 * 1e-15 * (1.0 + fringe_fraction)


def ejec_ratio(
    area_um2: float,
    jc_ua_per_um2: float,
    specific_capacitance_ff_per_um2: float,
) -> float:
    """Compute Ej/Ec from junction geometry and process parameters.

    Transmon regime: 20 < Ej/Ec < 200.
    """
    ic = ic_from_area(area_um2, jc_ua_per_um2)
    ej = ej_from_ic(ic)
    c = junction_capacitance_f(area_um2=area_um2, specific_capacitance_ff_per_um2=specific_capacitance_ff_per_um2)
    ec = ec_from_capacitance(c)
    return ej / ec


def full_jj_analysis(
    *,
    area_um2: float,
    jc_ua_per_um2: float,
    specific_capacitance_ff_per_um2: float = 50.0,
    rn_ohm: float | None = None,
    temperature_k: float = 0.02,
    critical_temperature_k: float = 1.2,
    artifact: str | None = None,
) -> dict[str, Any]:
    """Complete JJ parameter extraction from area + process specs.

    All outputs carry provenance labels. source="LLM" is a fatal error.
    """
    ic = ic_from_area(area_um2, jc_ua_per_um2)
    lj = lj_from_ic(ic)
    ej_j = ej_from_ic(ic)
    c_f = junction_capacitance_f(area_um2=area_um2, specific_capacitance_ff_per_um2=specific_capacitance_ff_per_um2)
    ec_j = ec_from_capacitance(c_f)
    f_p = plasma_frequency_hz(lj, c_f)
    ratio = ej_j / ec_j

    result: dict[str, Any] = {
        "schema": "text-to-gds.jj-analysis.v1",
        "provenance": {
            "method": "analytical",
            "source": "Josephson (1962), Ambegaokar-Baratoff (1963)",
            "inputs": {
                "area_um2": area_um2,
                "jc_ua_per_um2": jc_ua_per_um2,
                "specific_capacitance_ff_per_um2": specific_capacitance_ff_per_um2,
                "temperature_k": temperature_k,
            },
        },
        "critical_current_a": {
            "value": ic, "unit": "A",
            "equation": "Ic = Jc * A",
            "source": "process_spec + geometry",
        },
        "josephson_inductance_h": {
            "value": lj, "unit": "H",
            "equation": "Lj = Phi0/(2*pi*Ic)",
            "source": "Josephson (1962)",
        },
        "josephson_inductance_ph": {
            "value": lj * 1e12, "unit": "pH",
            "equation": "Lj = Phi0/(2*pi*Ic)",
            "source": "Josephson (1962)",
        },
        "josephson_energy_j": {
            "value": ej_j, "unit": "J",
            "equation": "Ej = hbar*Ic/(2e)",
            "source": "Josephson (1962)",
        },
        "josephson_energy_ghz": {
            "value": ej_j / (2.0 * math.pi * PLANCK_HBAR) * 1e-9, "unit": "GHz",
            "equation": "Ej/h",
            "source": "Josephson (1962)",
        },
        "capacitance_f": {
            "value": c_f, "unit": "F",
            "equation": "C = Cs * A",
            "source": "parallel_plate_model",
        },
        "capacitance_ff": {
            "value": c_f * 1e15, "unit": "fF",
            "equation": "C = Cs * A",
            "source": "parallel_plate_model",
        },
        "charging_energy_j": {
            "value": ec_j, "unit": "J",
            "equation": "Ec = e^2/(2C)",
            "source": "Koch et al. (2007)",
        },
        "charging_energy_ghz": {
            "value": ec_j / (2.0 * math.pi * PLANCK_HBAR) * 1e-9, "unit": "GHz",
            "equation": "Ec/h",
            "source": "Koch et al. (2007)",
        },
        "ej_ec_ratio": {
            "value": ratio, "unit": "dimensionless",
            "equation": "Ej/Ec",
            "source": "Josephson (1962) + Koch (2007)",
        },
        "plasma_frequency_ghz": {
            "value": f_p * 1e-9, "unit": "GHz",
            "equation": "f_p = 1/(2*pi*sqrt(Lj*C))",
            "source": "Josephson (1962)",
        },
    }

    if ratio < 20.0:
        result["regime_warning"] = f"Ej/Ec={ratio:.1f} < 20 — Cooper-pair box regime, not transmon"
    elif ratio > 200.0:
        result["regime_warning"] = f"Ej/Ec={ratio:.1f} > 200 — deep transmon, charge dispersion negligible"
    else:
        result["regime"] = f"transmon (Ej/Ec={ratio:.1f}, valid range 20–200)"

    if rn_ohm is not None:
        ab = ambegaokar_baratoff(
            normal_resistance_ohm=rn_ohm,
            temperature_k=temperature_k,
            critical_temperature_k=critical_temperature_k,
        )
        result["ambegaokar_baratoff"] = {
            "value": ab,
            "source": "Ambegaokar-Baratoff (1963)",
            "note": "Ic from AB should agree with Ic from geometry within ~10%",
        }

    if artifact:
        result["artifact"] = artifact

    return result
