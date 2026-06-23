"""Touchstone (.s2p) validation — reciprocity, passivity, energy conservation.

Every S-parameter file produced by an EM solver must pass:
  1. Reciprocity:  |S21 - S12| < tolerance  (for passive reciprocal devices)
  2. Passivity:    max singular value of S†S ≤ 1.0 at every frequency
  3. Causality:    (not checked here — requires time-domain transform)

A failed check means the solver output is unphysical and must not be used.

source="LLM" is never written here. All validation is purely numerical.
"""

from __future__ import annotations

import cmath
import math
import re
from pathlib import Path
from typing import Any


def parse_touchstone_s2p(path: str | Path) -> dict[str, Any]:
    """Parse a .s2p Touchstone file.

    Returns
    -------
    dict with keys:
      frequencies_hz : list[float]
      S11, S21, S12, S22 : list[complex]
      format : "MA" | "RI" | "DB"
      reference_ohm : float
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Touchstone file not found: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    freq_unit = 1e9
    fmt = "MA"
    r = 50.0
    freqs: list[float] = []
    s11_list: list[complex] = []
    s21_list: list[complex] = []
    s12_list: list[complex] = []
    s22_list: list[complex] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("!"):
            continue
        if stripped.startswith("#"):
            # Option line: # GHz S MA R 50
            parts = stripped.upper().split()
            unit_map = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9, "THZ": 1e12}
            for i, p in enumerate(parts):
                if p in unit_map:
                    freq_unit = unit_map[p]
                if p in ("MA", "RI", "DB"):
                    fmt = p
                if p == "R" and i + 1 < len(parts):
                    try:
                        r = float(parts[i + 1])
                    except ValueError:
                        pass
            continue

        # Data line
        nums = [float(x) for x in re.split(r"[\s,]+", stripped) if x]
        if len(nums) < 9:
            continue

        f = nums[0] * freq_unit
        freqs.append(f)

        s11 = _parse_pair(nums[1], nums[2], fmt)
        s21 = _parse_pair(nums[3], nums[4], fmt)
        s12 = _parse_pair(nums[5], nums[6], fmt)
        s22 = _parse_pair(nums[7], nums[8], fmt)

        s11_list.append(s11)
        s21_list.append(s21)
        s12_list.append(s12)
        s22_list.append(s22)

    if not freqs:
        raise ValueError(f"No data found in Touchstone file: {path}")

    return {
        "frequencies_hz": freqs,
        "S11": s11_list,
        "S21": s21_list,
        "S12": s12_list,
        "S22": s22_list,
        "format": fmt,
        "reference_ohm": r,
        "n_points": len(freqs),
    }


def _parse_pair(a: float, b: float, fmt: str) -> complex:
    if fmt == "MA":
        return cmath.rect(a, math.radians(b))
    elif fmt == "RI":
        return complex(a, b)
    elif fmt == "DB":
        mag = 10.0 ** (a / 20.0)
        return cmath.rect(mag, math.radians(b))
    else:
        return complex(a, b)


def check_reciprocity(
    s21: list[complex],
    s12: list[complex],
    *,
    tolerance: float = 0.02,
) -> dict[str, Any]:
    """Check |S21 - S12| < tolerance at every frequency point.

    Tolerance is in linear units (not dB).

    Returns
    -------
    dict with passed, max_deviation, worst_frequency_idx
    """
    if len(s21) != len(s12):
        return {
            "passed": False,
            "reason": "S21 and S12 have different lengths",
            "max_deviation": None,
        }

    deviations = [abs(a - b) for a, b in zip(s21, s12)]
    max_dev = max(deviations) if deviations else 0.0
    worst_idx = deviations.index(max_dev) if deviations else 0

    return {
        "passed": max_dev <= tolerance,
        "tolerance": tolerance,
        "max_deviation_linear": round(max_dev, 6),
        "max_deviation_db": round(20.0 * math.log10(max(max_dev, 1e-20)), 3),
        "worst_point_index": worst_idx,
        "reason": None if max_dev <= tolerance else (
            f"|S21-S12|_max = {max_dev:.4f} > tolerance {tolerance:.4f} — "
            "non-reciprocal response suggests numerical or port error"
        ),
    }


def check_passivity(
    s11: list[complex],
    s21: list[complex],
    s12: list[complex],
    s22: list[complex],
    *,
    tolerance: float = 1e-3,
) -> dict[str, Any]:
    """Check that the S-matrix is passive at every frequency.

    Passivity: all singular values of S(f) ≤ 1 + tolerance.
    For a 2×2 matrix [[S11, S12], [S21, S22]], the singular values
    are the square roots of the eigenvalues of S†S.

    Returns
    -------
    dict with passed, max_singular_value, worst_frequency_idx
    """
    n = len(s11)
    if not (n == len(s21) == len(s12) == len(s22)):
        return {
            "passed": False,
            "reason": "S-parameter arrays have inconsistent lengths",
            "max_singular_value": None,
        }

    max_sv = 0.0
    worst_idx = 0

    for i in range(n):
        S = [[s11[i], s12[i]], [s21[i], s22[i]]]
        sv_max = _max_singular_value_2x2(S)
        if sv_max > max_sv:
            max_sv = sv_max
            worst_idx = i

    return {
        "passed": max_sv <= 1.0 + tolerance,
        "tolerance": tolerance,
        "max_singular_value": round(max_sv, 6),
        "worst_point_index": worst_idx,
        "energy_violation_db": round(20.0 * math.log10(max(max_sv, 1e-20)), 3) if max_sv > 1.0 else 0.0,
        "reason": None if max_sv <= 1.0 + tolerance else (
            f"max singular value = {max_sv:.4f} > 1 + {tolerance} — "
            "S-matrix is not passive; check for numerical instability or gain without source"
        ),
    }


def _max_singular_value_2x2(S: list[list[complex]]) -> float:
    """Max singular value of 2×2 complex matrix via eigenvalue of S†S."""
    a, b = S[0][0], S[0][1]
    c, d = S[1][0], S[1][1]

    # S†S elements
    m11 = abs(a) ** 2 + abs(c) ** 2
    m12 = a.conjugate() * b + c.conjugate() * d
    m21 = m12.conjugate()
    m22 = abs(b) ** 2 + abs(d) ** 2

    trace = m11 + m22
    det_real = (m11 * m22 - abs(m12) ** 2).real

    # Eigenvalues of 2×2 Hermitian matrix
    discriminant = (trace / 2.0) ** 2 - det_real
    if discriminant < 0:
        discriminant = 0.0
    lam_max = trace / 2.0 + math.sqrt(discriminant)
    return math.sqrt(max(lam_max, 0.0))


def check_energy_conservation(
    s11: list[complex],
    s21: list[complex],
    s12: list[complex],
    s22: list[complex],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Check that |S11|² + |S21|² ≤ 1 at every frequency (port 1 input).

    This is a necessary (but not sufficient) condition for energy conservation.
    """
    n = len(s11)
    if n == 0:
        return {"passed": False, "reason": "Empty S-parameter arrays"}

    max_violation = 0.0
    worst_idx = 0
    for i in range(n):
        total = abs(s11[i]) ** 2 + abs(s21[i]) ** 2
        violation = total - 1.0
        if violation > max_violation:
            max_violation = violation
            worst_idx = i

    return {
        "passed": max_violation <= tolerance,
        "tolerance": tolerance,
        "max_power_violation": round(max_violation, 6),
        "worst_point_index": worst_idx,
        "reason": None if max_violation <= tolerance else (
            f"|S11|²+|S21|² - 1 = {max_violation:.4f} > {tolerance} at point {worst_idx} — "
            "energy is not conserved; check excitation and port normalization"
        ),
    }


def validate_touchstone(
    path: str | Path,
    *,
    reciprocity_tol: float = 0.02,
    passivity_tol: float = 1e-3,
    energy_tol: float = 0.05,
) -> dict[str, Any]:
    """Full Touchstone validation pipeline.

    Returns a structured report. All checks must pass for physical validity.
    """
    path = Path(path)

    try:
        data = parse_touchstone_s2p(path)
    except (FileNotFoundError, ValueError) as e:
        return {
            "schema": "text-to-gds.touchstone-validation.v1",
            "artifact": str(path),
            "parse_error": str(e),
            "reciprocity": {"passed": False, "reason": "parse failed"},
            "passivity": {"passed": False, "reason": "parse failed"},
            "energy_conservation": {"passed": False, "reason": "parse failed"},
            "overall_passed": False,
        }

    s11 = data["S11"]
    s21 = data["S21"]
    s12 = data["S12"]
    s22 = data["S22"]

    reciprocity = check_reciprocity(s21, s12, tolerance=reciprocity_tol)
    passivity = check_passivity(s11, s21, s12, s22, tolerance=passivity_tol)
    energy = check_energy_conservation(s11, s21, s12, s22, tolerance=energy_tol)

    overall = reciprocity["passed"] and passivity["passed"] and energy["passed"]

    return {
        "schema": "text-to-gds.touchstone-validation.v1",
        "artifact": str(path),
        "artifact_bytes": path.stat().st_size,
        "n_frequency_points": data["n_points"],
        "frequency_ghz_range": [
            round(data["frequencies_hz"][0] / 1e9, 4),
            round(data["frequencies_hz"][-1] / 1e9, 4),
        ] if data["n_points"] > 0 else [],
        "reference_ohm": data["reference_ohm"],
        "reciprocity": reciprocity,
        "passivity": passivity,
        "energy_conservation": energy,
        "overall_passed": overall,
        "provenance": {
            "method": "extracted",
            "source": "Touchstone numerical validation",
        },
    }
