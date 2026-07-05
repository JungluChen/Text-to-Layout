"""Josephson junction / SQUID / frequency physics for yield modeling.

Exact relations (CODATA Φ₀), no fitting:

    Ic  = Jc · A                       [µA] = [µA/µm²]·[µm²]
    LJ  = Φ₀ / (2π · Ic)               Josephson inductance at zero bias
    f   = 1 / (2π √(L·C))              LC resonance
    f01 ≈ √(8·EJ·EC)/h − EC/h          transmon approximation (charge limit)

SQUID with junction asymmetry d = (Ic1−Ic2)/(Ic1+Ic2):

    Ic_eff(Φ) = (Ic1+Ic2) · √(cos²(πΦ/Φ₀) + d²·sin²(πΦ/Φ₀))

which is finite at the half-flux point for any asymmetric SQUID and reduces to
|cos| for a symmetric one. All functions are pure and unit-explicit.
"""

from __future__ import annotations

import math

#: Magnetic flux quantum, Wb (CODATA 2018 exact: h / 2e).
PHI0_WB = 2.067833848e-15
#: Planck constant, J·s (CODATA 2018 exact).
H_JS = 6.62607015e-34
#: Elementary charge, C (CODATA 2018 exact).
E_C = 1.602176634e-19


def ic_ua(jc_ua_per_um2: float, area_um2: float) -> float:
    """Critical current Ic = Jc·A, in µA."""
    if jc_ua_per_um2 <= 0 or area_um2 <= 0:
        raise ValueError(
            f"Jc and area must be positive, got Jc={jc_ua_per_um2} uA/um^2, A={area_um2} um^2"
        )
    return jc_ua_per_um2 * area_um2


def lj_nh(ic_ua_value: float) -> float:
    """Zero-bias Josephson inductance LJ = Φ₀/(2π·Ic), in nH."""
    if ic_ua_value <= 0:
        raise ValueError(f"Ic must be positive, got {ic_ua_value} uA")
    ic_a = ic_ua_value * 1e-6
    return PHI0_WB / (2.0 * math.pi * ic_a) * 1e9


def squid_ic_eff_ua(ic1_ua: float, ic2_ua: float, flux_phi0: float) -> float:
    """Flux-dependent effective critical current of a two-junction SQUID, µA.

    ``flux_phi0`` is the external flux in units of Φ₀. Finite at Φ = Φ₀/2 for
    asymmetric junctions; exactly zero there only for a perfectly symmetric
    SQUID (in which case a downstream LJ would diverge — callers must guard).
    """
    if ic1_ua <= 0 or ic2_ua <= 0:
        raise ValueError(f"junction Ics must be positive, got {ic1_ua}, {ic2_ua} uA")
    total = ic1_ua + ic2_ua
    asymmetry = abs(ic1_ua - ic2_ua) / total
    phase = math.pi * flux_phi0
    return total * math.sqrt(
        math.cos(phase) ** 2 + (asymmetry * math.sin(phase)) ** 2
    )


def squid_lj_nh(ic1_ua: float, ic2_ua: float, flux_phi0: float) -> float:
    """Flux-dependent SQUID Josephson inductance, nH. Raises near Ic→0."""
    ic_eff = squid_ic_eff_ua(ic1_ua, ic2_ua, flux_phi0)
    if ic_eff < 1e-9:
        raise ValueError(
            "effective SQUID Ic is ~0 (symmetric SQUID at half flux); "
            "LJ diverges — refusing to return a number"
        )
    return lj_nh(ic_eff)


def lc_resonance_ghz(l_nh: float, c_pf: float) -> float:
    """f = 1/(2π√(LC)), in GHz."""
    if l_nh <= 0 or c_pf <= 0:
        raise ValueError(f"L and C must be positive, got L={l_nh} nH, C={c_pf} pF")
    return 1.0 / (2.0 * math.pi * math.sqrt(l_nh * 1e-9 * c_pf * 1e-12)) / 1e9


def ej_ghz(ic_ua_value: float) -> float:
    """Josephson energy EJ/h = Φ₀·Ic/(2π·h), in GHz."""
    if ic_ua_value <= 0:
        raise ValueError(f"Ic must be positive, got {ic_ua_value} uA")
    return PHI0_WB * ic_ua_value * 1e-6 / (2.0 * math.pi * H_JS) / 1e9


def ec_ghz(c_total_ff: float) -> float:
    """Charging energy EC/h = e²/(2·C·h), in GHz."""
    if c_total_ff <= 0:
        raise ValueError(f"C must be positive, got {c_total_ff} fF")
    return E_C**2 / (2.0 * c_total_ff * 1e-15 * H_JS) / 1e9


def transmon_f01_ghz(ic_ua_value: float, c_total_ff: float) -> float:
    """Transmon f01 ≈ √(8·EJ·EC) − EC (all in GHz).

    Valid in the transmon limit EJ/EC ≳ 50; callers propagating process
    variation should check the ratio per sample rather than assume it.
    """
    ej = ej_ghz(ic_ua_value)
    ec = ec_ghz(c_total_ff)
    return math.sqrt(8.0 * ej * ec) - ec


def ej_over_ec(ic_ua_value: float, c_total_ff: float) -> float:
    """EJ/EC ratio (dimensionless) — transmon-limit sanity signal."""
    return ej_ghz(ic_ua_value) / ec_ghz(c_total_ff)
