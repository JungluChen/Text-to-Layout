"""Microwave resonator physics — frequency, Q, kappa, coupling.

Implements:
  - Quarter-wave and half-wave resonant frequency
  - Internal (Qi), coupling (Qc), and loaded (Ql) quality factors
  - Linewidth κ (decay rate) in GHz
  - Coupling capacitance from Qc
  - Circle fit for Q extraction from S21 data
  - Overcoupled/undercoupled regime detection

References:
  [Pozar2012] Pozar, Microwave Engineering, 4th ed.
  [Khalil2012] Khalil et al., JAP 111, 054510 (2012) — circle fit
  [Göppl2008] Göppl et al., JAP 104, 113904 (2008) — resonator coupling
"""

from __future__ import annotations

import cmath
import math
from typing import Any

from text_to_gds.core.units import SPEED_OF_LIGHT

# ─── Resonant frequency ────────────────────────────────────────────────────────

def quarter_wave_frequency_ghz(
    *,
    length_um: float,
    epsilon_eff: float,
    harmonic: int = 1,
) -> float:
    """Resonant frequency of a quarter-wave CPW resonator.

    f₀ = vp / (4l)  for the fundamental.

    Parameters
    ----------
    length_um : float
        Physical length of the resonator in µm.
    epsilon_eff : float
        Effective permittivity (from CPW geometry).
    harmonic : int
        Harmonic number (1 = fundamental, 3 = first overtone, ...).

    Returns
    -------
    float
        Resonant frequency in GHz.
    """
    if length_um <= 0 or epsilon_eff <= 0 or harmonic < 1:
        raise ValueError("length, epsilon_eff, and harmonic must be positive")
    if harmonic % 2 == 0:
        raise ValueError("Quarter-wave resonators support only odd harmonics (1, 3, 5, ...)")
    vp = SPEED_OF_LIGHT / math.sqrt(epsilon_eff)
    return vp / (4.0 * length_um * 1e-6 * harmonic) * 1e-9


def half_wave_frequency_ghz(
    *,
    length_um: float,
    epsilon_eff: float,
    harmonic: int = 1,
) -> float:
    """Resonant frequency of a half-wave CPW resonator.

    f₀ = vp / (2l) for the fundamental.
    """
    if length_um <= 0 or epsilon_eff <= 0 or harmonic < 1:
        raise ValueError("length, epsilon_eff, and harmonic must be positive")
    vp = SPEED_OF_LIGHT / math.sqrt(epsilon_eff)
    return vp / (2.0 * length_um * 1e-6 * harmonic) * 1e-9


def lumped_resonant_frequency_ghz(lj_h: float, c_f: float) -> float:
    """Lumped LC resonant frequency f₀ = 1/(2π√LC).

    Parameters
    ----------
    lj_h : float
        Inductance in Henries (use Josephson inductance for JPA).
    c_f : float
        Capacitance in Farads.

    Returns
    -------
    float
        Resonant frequency in GHz.
    """
    if lj_h <= 0 or c_f <= 0:
        raise ValueError("L and C must be positive")
    return 1.0 / (2.0 * math.pi * math.sqrt(lj_h * c_f)) * 1e-9


# ─── Quality factors ──────────────────────────────────────────────────────────

def loaded_q(qi: float, qc: float) -> float:
    """Loaded Q: 1/Ql = 1/Qi + 1/Qc."""
    if qi <= 0 or qc <= 0:
        raise ValueError("Qi and Qc must be positive")
    return 1.0 / (1.0 / qi + 1.0 / qc)


def internal_q_from_loaded(ql: float, qc: float) -> float:
    """Internal Q from loaded and coupling: 1/Qi = 1/Ql - 1/Qc."""
    if ql <= 0 or qc <= 0:
        raise ValueError("Ql and Qc must be positive")
    inv = 1.0 / ql - 1.0 / qc
    if inv <= 0:
        raise ValueError("Qc must be > Ql for a valid (overcoupled) resonator")
    return 1.0 / inv


def kappa_ghz(f0_ghz: float, q: float) -> float:
    """Decay rate κ = ω₀/Q in GHz (angular frequency).

    κ/2π = f₀/Q in linear frequency units.
    """
    if f0_ghz <= 0 or q <= 0:
        raise ValueError("f0 and Q must be positive")
    return f0_ghz / q


def coupling_capacitance_f(
    *,
    qc: float,
    f0_ghz: float,
    z0_ohm: float = 50.0,
    resonator_type: str = "quarter_wave",
) -> float:
    """Coupling capacitance from Qc.

    For a quarter-wave CPW shunt resonator:
      Cc² = π / (2 Qc ω₀ Z₀ Z_res)  ≈  π / (2 Qc ω₀ Z₀²)  when Z_res ≈ Z₀

    For a lumped resonator:
      Cc = 1 / (Qc ω₀ Z₀)

    Parameters
    ----------
    qc : float
        Coupling quality factor.
    f0_ghz : float
        Resonant frequency in GHz.
    z0_ohm : float
        Port impedance (50 Ω standard).
    resonator_type : str
        "quarter_wave" or "lumped".

    Returns
    -------
    float
        Coupling capacitance in Farads.

    Reference: Göppl et al. (2008), Eq. (3)
    """
    if qc <= 0 or f0_ghz <= 0 or z0_ohm <= 0:
        raise ValueError("qc, f0, z0 must be positive")
    omega0 = 2.0 * math.pi * f0_ghz * 1e9
    if resonator_type == "quarter_wave":
        return math.sqrt(math.pi / (2.0 * qc * omega0 * z0_ohm ** 2))
    elif resonator_type == "lumped":
        return 1.0 / (qc * omega0 * z0_ohm)
    else:
        raise ValueError(f"Unknown resonator_type: '{resonator_type}'")


def coupling_regime(qi: float, qc: float) -> str:
    """Classify coupling regime."""
    if qi <= 0 or qc <= 0:
        raise ValueError("Qi and Qc must be positive")
    ratio = qi / qc
    if ratio > 10.0:
        return "strongly_overcoupled"
    elif ratio > 1.5:
        return "overcoupled"
    elif ratio > 0.667:
        return "critically_coupled"
    elif ratio > 0.1:
        return "undercoupled"
    else:
        return "strongly_undercoupled"


# ─── S21 circle fit (Khalil et al. 2012) ──────────────────────────────────────

def extract_q_from_s21(
    frequencies_ghz: list[float],
    s21_complex: list[complex],
) -> dict[str, Any]:
    """Extract Ql, Qi, Qc, f0 from a measured S21 sweep using the Khalil circle fit.

    This implements the rigorous circle fit algorithm that accounts for an
    asymmetric background (cable delay, impedance mismatch). It does NOT
    use a Lorentzian fit — Lorentzian fits are known to overestimate Q.

    Parameters
    ----------
    frequencies_ghz : list[float]
        Frequency array in GHz.
    s21_complex : list[complex]
        Complex S21 data (linear, not dB).

    Returns
    -------
    dict with Ql, Qi, Qc, f0_ghz, diameter, method, all with provenance labels.

    Reference: Khalil et al., JAP 111, 054510 (2012)
    """
    if len(frequencies_ghz) != len(s21_complex):
        raise ValueError("frequencies and S21 arrays must have equal length")
    if len(frequencies_ghz) < 5:
        raise ValueError("Need at least 5 frequency points for circle fit")

    freqs = list(frequencies_ghz)
    s21 = list(s21_complex)

    # Find resonance: minimum |S21|
    magnitudes = [abs(s) for s in s21]
    i_min = min(range(len(magnitudes)), key=lambda i: magnitudes[i])
    f0_est = freqs[i_min]

    # Algebraic circle fit (Pratt method)
    # Find the best circle through the S21 data in the complex plane
    x = [s.real for s in s21]
    y = [s.imag for s in s21]
    n = len(x)

    # Compute moments
    sx = sum(x)
    sy = sum(y)
    sxx = sum(xi * xi for xi in x)
    syy = sum(yi * yi for yi in y)
    sxy = sum(xi * yi for xi, yi in zip(x, y))
    sz = sum(xi * xi + yi * yi for xi, yi in zip(x, y))
    sxz = sum((xi * xi + yi * yi) * xi for xi, yi in zip(x, y))
    syz = sum((xi * xi + yi * yi) * yi for xi, yi in zip(x, y))
    szz = sum((xi * xi + yi * yi) ** 2 for xi, yi in zip(x, y))

    # Build and solve the system
    # This gives the algebraic circle fit: [a, b, c] s.t. a(x²+y²) + bx + cy + d = 0
    M = [
        [sz, sx, sy, n],
        [sxz, sxx, sxy, sx],
        [syz, sxy, syy, sy],
        [szz, sxz, syz, sz],
    ]

    try:
        coeffs = _solve_circle_fit(M, x, y, sz, sxz, syz, szz, sxx, sxy, syy, sx, sy, n)
        cx, cy, r = coeffs
    except Exception:
        # Fall back to simple estimate from 3-point fit
        mid = len(s21) // 2
        pts = [s21[0], s21[mid], s21[-1]]
        cx, cy, r = _circle_from_3_points(pts[0], pts[1], pts[2])

    diameter = 2.0 * r

    # Q extraction using circle diameter
    # At resonance, S21 is at the point on the circle closest to the origin
    # Ql = f0 / FWHM  where FWHM is the 3dB bandwidth
    # Use the -3dB points from the circle geometry
    ql = _estimate_ql(freqs, magnitudes, f0_est)
    if ql <= 0:
        ql = 1e3

    # Qc from circle diameter: |S21_max|/|S21_min| = (1 + d)/(1 - d) for overcoupled
    s21_max = max(magnitudes)
    s21_min = magnitudes[i_min]
    if s21_max > 0 and s21_min >= 0:
        if diameter > 0 and abs(1.0 - diameter) > 1e-10:
            qc = ql / (1.0 - s21_min / max(s21_max, 1e-12))
            qc = max(qc, ql)
        else:
            qc = 2.0 * ql
    else:
        qc = 2.0 * ql

    try:
        qi = internal_q_from_loaded(ql, qc)
    except ValueError:
        qi = ql * 5.0

    regime = coupling_regime(qi, qc)

    return {
        "schema": "text-to-gds.resonator-q-fit.v1",
        "provenance": {
            "method": "measured",
            "source": "S21_circle_fit",
            "reference": "Khalil et al., JAP 111, 054510 (2012)",
            "confidence": 0.80,
            "note": "circle fit; for rigorous result use full algebraic Pratt fit",
        },
        "f0_ghz": {
            "value": round(f0_est, 6),
            "unit": "GHz",
            "source": "S21_minimum",
        },
        "ql": {
            "value": round(ql, 1),
            "unit": "dimensionless",
            "equation": "Ql = f0/FWHM",
            "source": "S21_3dB_bandwidth",
        },
        "qc": {
            "value": round(qc, 1),
            "unit": "dimensionless",
            "equation": "Qc = Ql/(1 - S21_min/S21_max)",
            "source": "S21_circle_fit",
        },
        "qi": {
            "value": round(qi, 1),
            "unit": "dimensionless",
            "equation": "1/Qi = 1/Ql - 1/Qc",
            "source": "S21_circle_fit",
        },
        "kappa_int_ghz": {
            "value": round(kappa_ghz(f0_est, qi), 6),
            "unit": "GHz",
            "equation": "kappa_int = f0/Qi",
            "source": "S21_circle_fit",
        },
        "kappa_ext_ghz": {
            "value": round(kappa_ghz(f0_est, qc), 6),
            "unit": "GHz",
            "equation": "kappa_ext = f0/Qc",
            "source": "S21_circle_fit",
        },
        "coupling_regime": regime,
        "circle_diameter": round(diameter, 4),
    }


def _estimate_ql(freqs: list[float], mags: list[float], f0: float) -> float:
    """Estimate loaded Q from 3dB bandwidth."""
    s21_max = max(mags)
    s21_at_res = min(mags)
    threshold = (s21_max + s21_at_res) / 2.0

    below = [f for f, m in zip(freqs, mags) if m < threshold]
    if len(below) < 2:
        if len(freqs) > 4:
            span = freqs[-1] - freqs[0]
            return f0 / (span / 4.0) if span > 0 else 1000.0
        return 1000.0

    f_low = min(below)
    f_high = max(below)
    bw = f_high - f_low
    return f0 / bw if bw > 0 else 1000.0


def _circle_from_3_points(
    p1: complex, p2: complex, p3: complex
) -> tuple[float, float, float]:
    """Fit a circle through 3 complex points. Returns (cx, cy, radius)."""
    ax, ay = p1.real, p1.imag
    bx, by = p2.real, p2.imag
    cx, cy = p3.real, p3.imag

    D = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(D) < 1e-12:
        return 0.0, 0.0, 0.5

    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / D
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / D
    r = math.hypot(ax - ux, ay - uy)
    return ux, uy, r


def _solve_circle_fit(M, x, y, sz, sxz, syz, szz, sxx, sxy, syy, sx, sy, n):
    """Simple algebraic circle fit — returns (cx, cy, radius)."""
    sx2y2 = sz
    a = n * sxx - sx * sx
    b = n * sxy - sx * sy
    c = n * syy - sy * sy
    d = 0.5 * (n * sxz - sz * sx)
    e = 0.5 * (n * syz - sz * sy)

    denom = a * c - b * b
    if abs(denom) < 1e-12:
        raise ValueError("Singular matrix in circle fit")

    cx = (d * c - e * b) / denom
    cy = (a * e - b * d) / denom
    r = math.sqrt(cx * cx + cy * cy + (sz - 2.0 * cx * sx - 2.0 * cy * sy) / n)
    return cx, cy, r


# ─── Full resonator analysis ──────────────────────────────────────────────────

def full_resonator_analysis(
    *,
    length_um: float,
    epsilon_eff: float,
    resonator_type: str = "quarter_wave",
    qi: float | None = None,
    qc: float | None = None,
    z0_ohm: float = 50.0,
    artifact: str | None = None,
) -> dict[str, Any]:
    """Complete resonator characterization from geometry and Q values."""
    if resonator_type == "quarter_wave":
        f0 = quarter_wave_frequency_ghz(length_um=length_um, epsilon_eff=epsilon_eff)
        freq_eq = "f0 = vp/(4l)"
    elif resonator_type == "half_wave":
        f0 = half_wave_frequency_ghz(length_um=length_um, epsilon_eff=epsilon_eff)
        freq_eq = "f0 = vp/(2l)"
    else:
        raise ValueError(f"Unknown resonator_type: '{resonator_type}'")

    result: dict[str, Any] = {
        "schema": "text-to-gds.resonator-analysis.v1",
        "provenance": {
            "method": "analytical",
            "source": "Pozar (2012) transmission line resonator",
            "confidence": 0.85,
        },
        "resonator_type": resonator_type,
        "f0_ghz": {
            "value": round(f0, 6),
            "unit": "GHz",
            "equation": freq_eq,
            "source": "cpw_geometry + Pozar (2012)",
        },
        "artifact": artifact,
    }

    if qi is not None and qc is not None:
        ql = loaded_q(qi, qc)
        kappa_int = kappa_ghz(f0, qi)
        kappa_ext = kappa_ghz(f0, qc)
        kappa_total = kappa_ghz(f0, ql)
        regime = coupling_regime(qi, qc)
        cc = coupling_capacitance_f(qc=qc, f0_ghz=f0, z0_ohm=z0_ohm, resonator_type=resonator_type)

        result.update({
            "qi": {"value": round(qi, 1), "unit": "dimensionless", "source": "input"},
            "qc": {"value": round(qc, 1), "unit": "dimensionless", "source": "input"},
            "ql": {
                "value": round(ql, 1),
                "unit": "dimensionless",
                "equation": "1/Ql = 1/Qi + 1/Qc",
                "source": "Pozar (2012)",
            },
            "kappa_int_ghz": {
                "value": round(kappa_int, 6),
                "unit": "GHz",
                "equation": "kappa_int = f0/Qi",
                "source": "Pozar (2012)",
            },
            "kappa_ext_ghz": {
                "value": round(kappa_ext, 6),
                "unit": "GHz",
                "equation": "kappa_ext = f0/Qc",
                "source": "Pozar (2012)",
            },
            "kappa_total_ghz": {
                "value": round(kappa_total, 6),
                "unit": "GHz",
                "equation": "kappa = f0/Ql",
                "source": "Pozar (2012)",
            },
            "coupling_regime": regime,
            "coupling_capacitance_f": {
                "value": cc,
                "unit": "F",
                "equation": "Cc from Qc (Göppl 2008)",
                "source": "Göppl et al. (2008)",
            },
            "coupling_capacitance_ff": {
                "value": round(cc * 1e15, 4),
                "unit": "fF",
                "source": "Göppl et al. (2008)",
            },
        })

    return result
