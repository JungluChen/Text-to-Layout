"""First-principles analytical models used by the research layer.

Every formula here is a published, citeable closed-form model — not a guess. They
produce *design starting points* (typically ±10-20 % vs. a full EM solve), which
is exactly their role in the pipeline: seed the geometry, then verify the real
value by EM extraction. References are given per function.

Units: micrometres for geometry, pF for capacitance, GHz for frequency, ohms for
impedance, unless stated otherwise.
"""

from __future__ import annotations

import math

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0

# Bahl interdigital-capacitor per-finger capacitance coefficients (pF/cm).
# I. J. Bahl, "Lumped Elements for RF and Microwave Circuits", Artech House,
# 2003, Ch. 2; after G. D. Alley, IEEE Trans. MTT-18 (1970) 1028.
_IDC_A1 = 0.089  # interior fingers
_IDC_A2 = 0.10   # the two terminal fingers


def cpw_eps_eff(eps_r: float) -> float:
    """Effective permittivity of a CPW on a thick substrate: (1 + eps_r) / 2.

    Reference: R. N. Simons, "Coplanar Waveguide Circuits, Components, and
    Systems", Wiley, 2001, Ch. 2 (quasi-static, infinitely thick substrate).
    """
    return (1.0 + eps_r) / 2.0


def _k_ratio(k: float) -> float:
    """K(k) / K(k') via Hilberg's closed-form approximation (error < 8e-6).

    W. Hilberg, "From approximations to exact relations for characteristic
    impedances", IEEE Trans. MTT-17 (1969) 259. k' = sqrt(1 - k^2).
    """
    if not 0.0 < k < 1.0:
        raise ValueError(f"k must be in (0, 1), got {k}")
    if k <= 1.0 / math.sqrt(2.0):
        kp = math.sqrt(1.0 - k * k)
        return math.pi / math.log(2.0 * (1.0 + math.sqrt(kp)) / (1.0 - math.sqrt(kp)))
    return math.log(2.0 * (1.0 + math.sqrt(k)) / (1.0 - math.sqrt(k))) / math.pi


def cpw_z0(center_width_um: float, gap_um: float, eps_r: float) -> tuple[float, float]:
    """CPW characteristic impedance (ohms) and eps_eff via conformal mapping.

    Z0 = (30*pi / sqrt(eps_eff)) * K(k') / K(k),  k = w / (w + 2g).
    Reference: Simons (2001) Ch. 2; D. M. Pozar, "Microwave Engineering", Wiley.
    """
    if center_width_um <= 0 or gap_um <= 0:
        raise ValueError("center width and gap must be positive")
    eps_eff = cpw_eps_eff(eps_r)
    k = center_width_um / (center_width_um + 2.0 * gap_um)
    z0 = (30.0 * math.pi / math.sqrt(eps_eff)) / _k_ratio(k)
    return z0, eps_eff


def cpw_gap_for_z0(
    target_z0_ohm: float, center_width_um: float, eps_r: float
) -> float:
    """Solve for the CPW gap (µm) that yields ``target_z0_ohm`` at a fixed width.

    Z0 increases monotonically with gap, so a bisection is robust and exact to
    1e-6 µm. Returns the gap; the caller is responsible for design-rule feasibility.
    """
    lo, hi = 1e-4, 1e6
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        z0, _ = cpw_z0(center_width_um, mid, eps_r)
        if z0 < target_z0_ohm:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cpw_quarter_wave_length_um(frequency_ghz: float, eps_eff: float) -> float:
    """Quarter-wave resonator physical length (µm): L = v_p / (4 f), v_p = c/sqrt(eps_eff)."""
    if frequency_ghz <= 0:
        raise ValueError("frequency must be positive")
    v_p = SPEED_OF_LIGHT_M_PER_S / math.sqrt(eps_eff)
    length_m = v_p / (4.0 * frequency_ghz * 1e9)
    return length_m * 1e6


def idc_capacitance_pf(finger_pairs: int, overlap_um: float, eps_r: float) -> float:
    """Interdigital-capacitor capacitance (pF), Bahl/Alley closed form.

    C = (eps_re + 1) * l_cm * [(N - 3) * A1 + A2],  N = 2 * finger_pairs,
    eps_re = (eps_r + 1) / 2,  l = finger overlap length.
    Reference: Bahl (2003) Ch. 2; Alley, IEEE Trans. MTT-18 (1970) 1028.
    """
    if finger_pairs <= 0 or overlap_um <= 0:
        raise ValueError("finger_pairs and overlap must be positive")
    n_fingers = 2 * finger_pairs
    eps_re = (eps_r + 1.0) / 2.0
    l_cm = overlap_um * 1e-4
    return (eps_re + 1.0) * l_cm * ((n_fingers - 3) * _IDC_A1 + _IDC_A2)


def idc_finger_pairs_for_target(
    target_pf: float, overlap_um: float, eps_r: float
) -> int:
    """Smallest finger-pair count whose Bahl estimate reaches ``target_pf``."""
    if target_pf <= 0:
        raise ValueError("target capacitance must be positive")
    eps_re = (eps_r + 1.0) / 2.0
    l_cm = overlap_um * 1e-4
    # target = (eps_re+1)*l*[(2P - 3)*A1 + A2]  ->  solve for P.
    rhs = target_pf / ((eps_re + 1.0) * l_cm)
    n_fingers = (rhs - _IDC_A2) / _IDC_A1 + 3.0
    pairs = math.ceil(n_fingers / 2.0)
    return max(pairs, 1)


def spiral_inductance_nh(turns: int, outer_um: float, inner_um: float) -> float:
    """Square-spiral inductance from Mohan's modified-Wheeler expression.

    L = K1 * mu0 * n^2 * d_avg / (1 + K2*rho), with K1=2.34 and
    K2=2.75 for a square spiral. Reference: Mohan et al., IEEE JSSC 34(10),
    1999, Table II.
    """
    if turns < 1 or outer_um <= inner_um or inner_um <= 0:
        raise ValueError("turns and spiral diameters must be positive with outer > inner")
    d_avg_m = ((outer_um + inner_um) / 2.0) * 1e-6
    rho = (outer_um - inner_um) / (outer_um + inner_um)
    mu0 = 4.0 * math.pi * 1e-7
    inductance_h = 2.34 * mu0 * turns**2 * d_avg_m / (1.0 + 2.75 * rho)
    return inductance_h * 1e9
