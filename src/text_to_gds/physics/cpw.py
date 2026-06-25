"""Coplanar waveguide (CPW) physics — consolidated API.

Implements conformal mapping Z0 and derived quantities, kinetic inductance
corrections, and resonator parameter extraction.

References:
  [Wen1969] Wen, MTT-17, 1087 (1969) — CPW conformal mapping
  [Pozar2012] Pozar, Microwave Engineering, 4th ed.
  [Barends2008] Barends et al., APL 92, 223502 (2008) — kinetic inductance
"""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.core.units import SPEED_OF_LIGHT

# ─── Complete elliptic integral K(k) via AGM ──────────────────────────────────

def _agm(a: float, b: float, tol: float = 1e-14) -> float:
    """Arithmetic-geometric mean for computing K(k) via AGM."""
    for _ in range(80):
        a, b = (a + b) / 2.0, math.sqrt(a * b)
        if abs(a - b) < tol:
            break
    return a


def _K(k: float) -> float:
    """Complete elliptic integral of the first kind K(k) via AGM.

    Valid for 0 < k < 1.
    """
    if not (0.0 < k < 1.0):
        raise ValueError(f"elliptic modulus must be in (0,1), got k={k}")
    return math.pi / (2.0 * _agm(1.0, math.sqrt(1.0 - k * k)))


# ─── Substrate filling factor ─────────────────────────────────────────────────

def _substrate_filling_factor(
    width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
) -> float:
    """Substrate filling factor q for finite-thickness substrate CPW.

    Uses the standard conformal mapping result for a CPW on a finite dielectric.
    Returns q ∈ [0, 0.5] where q=0.5 is the semi-infinite limit.

    Reference: Wen (1969), extended for finite substrate thickness.
    """
    w = width_um
    g = gap_um
    h = substrate_thickness_um

    # Infinite substrate limit modulus
    k0 = w / (w + 2.0 * g)
    k0 = min(max(k0, 1e-9), 1.0 - 1e-9)
    k0p = math.sqrt(1.0 - k0 * k0)

    # Finite-thickness modulus k1
    s1 = math.sinh(math.pi * w / (4.0 * h))
    s2 = math.sinh(math.pi * (w + 2.0 * g) / (4.0 * h))
    if s2 < 1e-12:
        return 0.5
    k1 = s1 / s2
    k1 = min(max(k1, 1e-9), 1.0 - 1e-9)
    k1p = math.sqrt(1.0 - k1 * k1)

    ratio = (_K(k1) * _K(k0p)) / (_K(k1p) * _K(k0))
    return ratio / 2.0


def epsilon_eff_cpw(
    *,
    center_width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
    epsilon_r: float,
) -> float:
    """Effective permittivity of a CPW on a finite substrate.

    ε_eff = 1 + q(ε_r - 1)

    where q is the substrate filling factor from conformal mapping.

    Reference: Wen (1969), Pozar (2012)
    """
    for name, val in [
        ("center_width_um", center_width_um),
        ("gap_um", gap_um),
        ("substrate_thickness_um", substrate_thickness_um),
        ("epsilon_r", epsilon_r),
    ]:
        if val <= 0:
            raise ValueError(f"{name} must be positive, got {val}")

    q = _substrate_filling_factor(center_width_um, gap_um, substrate_thickness_um)
    return 1.0 + q * (epsilon_r - 1.0)


def z0_cpw(
    *,
    center_width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
    epsilon_r: float,
) -> float:
    """Characteristic impedance Z0 of a CPW.

    Z0 = (30π / √ε_eff) × K(k') / K(k)

    where k = w/(w+2g) is the geometry modulus.

    Reference: Wen (1969), Pozar (2012) Eq. (3.196)
    """
    for name, val in [
        ("center_width_um", center_width_um),
        ("gap_um", gap_um),
        ("substrate_thickness_um", substrate_thickness_um),
        ("epsilon_r", epsilon_r),
    ]:
        if val <= 0:
            raise ValueError(f"{name} must be positive")

    w = center_width_um
    g = gap_um
    k = w / (w + 2.0 * g)
    k = min(max(k, 1e-9), 1.0 - 1e-9)
    kp = math.sqrt(1.0 - k * k)

    eps_eff = epsilon_eff_cpw(
        center_width_um=center_width_um,
        gap_um=gap_um,
        substrate_thickness_um=substrate_thickness_um,
        epsilon_r=epsilon_r,
    )
    return 30.0 * math.pi * _K(kp) / (_K(k) * math.sqrt(eps_eff))


def phase_velocity_m_per_s(epsilon_eff: float) -> float:
    """Phase velocity vp = c / √ε_eff."""
    if epsilon_eff <= 0:
        raise ValueError("epsilon_eff must be positive")
    return SPEED_OF_LIGHT / math.sqrt(epsilon_eff)


def capacitance_per_length_f_per_m(z0_ohm: float, epsilon_eff: float) -> float:
    """Distributed capacitance C' = √ε_eff / (Z0 × c)."""
    vp = phase_velocity_m_per_s(epsilon_eff)
    return 1.0 / (z0_ohm * vp)


def inductance_per_length_h_per_m(z0_ohm: float, epsilon_eff: float) -> float:
    """Distributed inductance L' = Z0 √ε_eff / c."""
    vp = phase_velocity_m_per_s(epsilon_eff)
    return z0_ohm / vp


def kinetic_inductance_per_length_h_per_m(
    *,
    kinetic_inductance_ph_per_sq: float,
    width_um: float,
) -> float:
    """Kinetic inductance per unit length: Lk' = Lk_sq / w.

    Parameters
    ----------
    kinetic_inductance_ph_per_sq : float
        Sheet kinetic inductance in pH/□ (from material characterisation).
    width_um : float
        Conductor width in µm.

    Returns
    -------
    float
        Lk' in H/m.

    Reference: Barends et al. (2008)
    """
    if kinetic_inductance_ph_per_sq <= 0 or width_um <= 0:
        raise ValueError("Lk_sq and width must be positive")
    return kinetic_inductance_ph_per_sq * 1e-12 / (width_um * 1e-6)


def kinetic_inductance_fraction(
    *,
    kinetic_inductance_ph_per_sq: float,
    width_um: float,
    z0_ohm: float,
    epsilon_eff: float,
) -> float:
    """Kinetic inductance participation ratio α_k = Lk' / (Lgeo' + Lk').

    α_k sets the frequency shift and internal Q degradation from quasiparticles.
    """
    lk = kinetic_inductance_per_length_h_per_m(
        kinetic_inductance_ph_per_sq=kinetic_inductance_ph_per_sq,
        width_um=width_um,
    )
    lgeo = inductance_per_length_h_per_m(z0_ohm, epsilon_eff)
    return lk / (lgeo + lk)


def quarter_wave_length_um(
    *,
    frequency_ghz: float,
    epsilon_eff: float,
    harmonic: int = 1,
) -> float:
    """Physical length for a λ/4 resonator at the given frequency.

    l = c / (4 f √ε_eff) for the fundamental (harmonic=1),
    l = c / (4 f √ε_eff) × (2n-1)⁻¹ for higher harmonics.
    """
    if frequency_ghz <= 0 or epsilon_eff <= 0 or harmonic < 1:
        raise ValueError("frequency, epsilon_eff, and harmonic must be positive")
    vp = SPEED_OF_LIGHT / math.sqrt(epsilon_eff)
    return vp / (4.0 * frequency_ghz * 1e9 * harmonic) * 1e6


def half_wave_length_um(
    *,
    frequency_ghz: float,
    epsilon_eff: float,
    harmonic: int = 1,
) -> float:
    """Physical length for a λ/2 resonator."""
    if frequency_ghz <= 0 or epsilon_eff <= 0 or harmonic < 1:
        raise ValueError("frequency, epsilon_eff, and harmonic must be positive")
    vp = SPEED_OF_LIGHT / math.sqrt(epsilon_eff)
    return vp / (2.0 * frequency_ghz * 1e9 * harmonic) * 1e6


def full_cpw_analysis(
    *,
    center_width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
    epsilon_r: float,
    frequency_ghz: float,
    kinetic_inductance_ph_per_sq: float = 0.0,
    target_z0_ohm: float = 50.0,
    artifact: str | None = None,
) -> dict[str, Any]:
    """Complete CPW parameter extraction.

    Returns Z0, ε_eff, vp, C', L', Lk', and λ/4 length — all with provenance.
    """
    eps_eff = epsilon_eff_cpw(
        center_width_um=center_width_um,
        gap_um=gap_um,
        substrate_thickness_um=substrate_thickness_um,
        epsilon_r=epsilon_r,
    )
    z0 = z0_cpw(
        center_width_um=center_width_um,
        gap_um=gap_um,
        substrate_thickness_um=substrate_thickness_um,
        epsilon_r=epsilon_r,
    )
    vp = phase_velocity_m_per_s(eps_eff)
    cprime = capacitance_per_length_f_per_m(z0, eps_eff)
    lprime = inductance_per_length_h_per_m(z0, eps_eff)
    lk = kinetic_inductance_per_length_h_per_m(
        kinetic_inductance_ph_per_sq=kinetic_inductance_ph_per_sq,
        width_um=center_width_um,
    ) if kinetic_inductance_ph_per_sq > 0 else 0.0
    alpha_k = lk / (lprime + lk) if (lprime + lk) > 0 else 0.0
    l_total = lprime + lk
    z0_with_ki = math.sqrt(l_total / cprime) if cprime > 0 else z0
    lam4 = quarter_wave_length_um(frequency_ghz=frequency_ghz, epsilon_eff=eps_eff)

    return {
        "schema": "text-to-gds.cpw-analysis.v1",
        "provenance": {
            "method": "analytical",
            "source": "Wen (1969), conformal mapping",
            "confidence": 0.85,
            "inputs": {
                "center_width_um": center_width_um,
                "gap_um": gap_um,
                "substrate_thickness_um": substrate_thickness_um,
                "epsilon_r": epsilon_r,
                "frequency_ghz": frequency_ghz,
                "kinetic_inductance_ph_per_sq": kinetic_inductance_ph_per_sq,
            },
        },
        "epsilon_eff": {
            "value": round(eps_eff, 5),
            "unit": "dimensionless",
            "equation": "eps_eff = 1 + q*(eps_r - 1)",
            "source": "Wen (1969)",
        },
        "z0_ohm": {
            "value": round(z0, 4),
            "unit": "Ohm",
            "equation": "Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)",
            "source": "Wen (1969)",
        },
        "z0_with_kinetic_inductance_ohm": {
            "value": round(z0_with_ki, 4),
            "unit": "Ohm",
            "equation": "Z0_ki = sqrt((L_geo+L_k)/C')",
            "source": "Barends et al. (2008)",
        },
        "phase_velocity_m_per_s": {
            "value": round(vp, 2),
            "unit": "m/s",
            "equation": "vp = c/sqrt(eps_eff)",
            "source": "Wen (1969)",
        },
        "capacitance_per_length_f_per_m": {
            "value": round(cprime, 6),
            "unit": "F/m",
            "equation": "C' = 1/(Z0*vp)",
            "source": "Pozar (2012)",
        },
        "inductance_per_length_h_per_m": {
            "value": round(lprime, 6),
            "unit": "H/m",
            "equation": "L' = Z0/vp",
            "source": "Pozar (2012)",
        },
        "kinetic_inductance_per_length_h_per_m": {
            "value": round(lk, 8),
            "unit": "H/m",
            "equation": "Lk' = Lk_sq/w",
            "source": "Barends et al. (2008)",
        },
        "kinetic_inductance_fraction": {
            "value": round(alpha_k, 6),
            "unit": "dimensionless",
            "equation": "alpha_k = Lk'/(L'+Lk')",
            "source": "Barends et al. (2008)",
        },
        "quarter_wave_length_um": {
            "value": round(lam4, 2),
            "unit": "um",
            "equation": "l = c/(4*f*sqrt(eps_eff))",
            "source": "Pozar (2012)",
        },
        "impedance_check": {
            "target_z0_ohm": target_z0_ohm,
            "actual_z0_ohm": round(z0, 4),
            "error_ohm": round(abs(z0 - target_z0_ohm), 4),
            "error_pct": round(abs(z0 - target_z0_ohm) / target_z0_ohm * 100.0, 3),
            "passed": abs(z0 - target_z0_ohm) <= 2.5,
        },
        "artifact": artifact,
    }
