"""Analytical CPW S-parameter model from conformal mapping.

Computes S11/S21 for a quarter-wave CPW resonator without an EM solver.
Provenance: method="analytical", source="CPW conformal mapping + coupled resonator model".
Confidence: 0.65 (good for ideal geometry, weaker for Q and radiation effects).

This is NOT equivalent to a full-wave FDTD/FEM simulation. It is a cross-check and
first-estimate only. The openEMS backend must produce EXECUTED status for signoff.

Never use this to claim a simulation result. Use it to:
  1. Estimate expected f0 and Z0 before running EM solver.
  2. Cross-validate the EM solver result (tolerance 10%).
  3. Produce a provisional Touchstone .s2p when openEMS is unavailable (SKIPPED state).
"""

from __future__ import annotations

import cmath
import json
import math
from pathlib import Path
from typing import Any

C0 = 299_792_458.0  # m/s
Z_REFERENCE = 50.0  # ohm, standard port impedance
SCHEMA = "text-to-gds.cpw-analytical.v1"


# ─── conformal mapping ────────────────────────────────────────────────────────

def _agm(a: float, b: float, tol: float = 1e-14) -> float:
    """Arithmetic-geometric mean (used for K(k))."""
    for _ in range(80):
        a, b = (a + b) / 2.0, math.sqrt(a * b)
        if abs(a - b) < tol:
            break
    return a


def _K(k: float) -> float:
    """Complete elliptic integral of the first kind via AGM."""
    if not 0.0 < k < 1.0:
        raise ValueError(f"elliptic modulus must be in (0,1), got {k}")
    return math.pi / (2.0 * _agm(1.0, math.sqrt(1.0 - k * k)))


def cpw_z0(
    *,
    center_width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
    epsilon_r: float,
) -> dict[str, float]:
    """Return Z0, epsilon_eff, and phase velocity via finite-substrate conformal mapping.

    Uses the Wheeler / Gupta formulation for CPW on a finite substrate.
    """
    w = center_width_um
    g = gap_um
    h = substrate_thickness_um
    k = w / (w + 2.0 * g)
    k_p = math.sqrt(1.0 - k * k)
    sinh_w = math.sinh(math.pi * w / (4.0 * h))
    sinh_wg = math.sinh(math.pi * (w + 2.0 * g) / (4.0 * h))
    k1 = sinh_w / sinh_wg
    k1 = min(max(k1, 1e-12), 1.0 - 1e-12)
    k1_p = math.sqrt(1.0 - k1 * k1)

    ratio_air = _K(k_p) / _K(k)
    substrate_factor = (_K(k1) / _K(k1_p)) * ratio_air
    eps_eff = 1.0 + (epsilon_r - 1.0) * substrate_factor / 2.0
    z0 = 30.0 * math.pi * ratio_air / math.sqrt(eps_eff)
    vp = C0 / math.sqrt(eps_eff)
    return {
        "z0_ohm": z0,
        "epsilon_effective": eps_eff,
        "phase_velocity_m_per_s": vp,
        "elliptic_modulus_k": k,
        "substrate_factor": substrate_factor,
    }


# ─── quarter-wave resonator model ─────────────────────────────────────────────

def _cpw_quarter_wave_resonator_s_params(
    *,
    frequencies_hz: list[float],
    f0_hz: float,
    loaded_q: float,
    z0_ohm: float,
    coupling_efficiency: float = 0.5,
) -> tuple[list[complex], list[complex]]:
    """Return (S11, S21) for a coupled quarter-wave CPW resonator.

    Uses the admittance model for a shunt-coupled QW resonator:
        Y_res = jQ * (f/f0 - f0/f) / Z0
    at critical coupling: κ_ext = κ_int = ω_0 / (2Q_i)
    """
    s11_list: list[complex] = []
    s21_list: list[complex] = []
    q_ext = loaded_q / (2.0 * coupling_efficiency)  # approximation
    for f in frequencies_hz:
        delta = f / f0_hz - f0_hz / f
        y_in = 1j * loaded_q * delta / z0_ohm + 1.0 / (q_ext * z0_ohm)
        gamma = y_in * Z_REFERENCE
        s11 = (gamma - 1.0) / (gamma + 1.0)
        s21 = cmath.sqrt(max(0.0, 1.0 - abs(s11) ** 2)) * cmath.exp(1j * cmath.phase(s11))
        s11_list.append(s11)
        s21_list.append(s21)
    return s11_list, s21_list


def _write_touchstone(
    path: Path,
    frequencies_hz: list[float],
    s11: list[complex],
    s21: list[complex],
    *,
    z_ref: float = 50.0,
) -> None:
    """Write a 2-port Touchstone .s2p file (RI format, Hz)."""
    lines = [
        "! Text-to-GDS analytical CPW resonator model",
        f"! Z0_ref={z_ref} ohm",
        "! provenance: conformal mapping + coupled resonator model",
        "! method=analytical  confidence=0.65",
        f"# Hz S RI R {z_ref:.1f}",
    ]
    for f, s11_v, s21_v in zip(frequencies_hz, s11, s21):
        s12_v = s21_v  # reciprocal
        s22_v = s11_v  # symmetric 2-port
        lines.append(
            f"{f:.6e}  "
            f"{s11_v.real:.8f} {s11_v.imag:.8f}  "
            f"{s21_v.real:.8f} {s21_v.imag:.8f}  "
            f"{s12_v.real:.8f} {s12_v.imag:.8f}  "
            f"{s22_v.real:.8f} {s22_v.imag:.8f}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─── public API ───────────────────────────────────────────────────────────────

def compute_cpw_resonator(
    *,
    center_width_um: float,
    gap_um: float,
    substrate_thickness_um: float,
    epsilon_r: float,
    target_frequency_ghz: float,
    target_bandwidth_mhz: float | None = None,
    target_impedance_ohm: float = 50.0,
    n_points: int = 201,
    report_path: str | Path | None = None,
    touchstone_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compute analytical CPW resonator characteristics and optional Touchstone output.

    Returns:
        status: "ok" | "failed"
        z0_ohm, f0_ghz, quarter_wave_length_um, loaded_q — analytical values
        touchstone_path — path if written (requires touchstone_path arg)
        provenance — all values labelled as method="analytical"
    """
    try:
        cpw = cpw_z0(
            center_width_um=center_width_um,
            gap_um=gap_um,
            substrate_thickness_um=substrate_thickness_um,
            epsilon_r=epsilon_r,
        )
    except (ValueError, ZeroDivisionError) as exc:
        return {"schema": SCHEMA, "status": "failed", "reason": str(exc)}

    z0 = cpw["z0_ohm"]
    vp = cpw["phase_velocity_m_per_s"]
    f0_hz = target_frequency_ghz * 1e9
    lambda_quarter_m = vp / (4.0 * f0_hz)
    bw_hz = (target_bandwidth_mhz or 10.0) * 1e6
    loaded_q = f0_hz / bw_hz

    impedance_ok = abs(z0 - target_impedance_ohm) <= 5.0

    # Frequency sweep ±3 BW around f0
    f_min = f0_hz - 3.0 * bw_hz
    f_max = f0_hz + 3.0 * bw_hz
    freqs = [f_min + (f_max - f_min) * i / (n_points - 1) for i in range(n_points)]
    s11, s21 = _cpw_quarter_wave_resonator_s_params(
        frequencies_hz=freqs,
        f0_hz=f0_hz,
        loaded_q=loaded_q,
        z0_ohm=z0,
    )

    # Write Touchstone if requested
    ts_path_str: str | None = None
    if touchstone_path is not None:
        ts = Path(touchstone_path)
        ts.parent.mkdir(parents=True, exist_ok=True)
        _write_touchstone(ts, freqs, s11, s21)
        ts_path_str = str(ts)

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ok",
        "geometry": {
            "center_width_um": center_width_um,
            "gap_um": gap_um,
            "substrate_thickness_um": substrate_thickness_um,
            "epsilon_r": epsilon_r,
        },
        "cpw": {
            "z0_ohm": z0,
            "epsilon_effective": cpw["epsilon_effective"],
            "phase_velocity_m_per_s": vp,
        },
        "resonator": {
            "f0_ghz": target_frequency_ghz,
            "f0_hz": f0_hz,
            "quarter_wave_length_um": lambda_quarter_m * 1e6,
            "loaded_q": loaded_q,
            "bandwidth_mhz": bw_hz / 1e6,
        },
        "impedance_check": {
            "z0_computed_ohm": z0,
            "z0_target_ohm": target_impedance_ohm,
            "error_ohm": abs(z0 - target_impedance_ohm),
            "passed": impedance_ok,
        },
        "provenance": {
            "method": "analytical",
            "source": "CPW conformal mapping + coupled quarter-wave resonator model",
            "confidence": 0.65,
            "formulas": {
                "Z0": "30*pi/sqrt(eps_eff) * K(k')/K(k), k=w/(w+2g)",
                "f0": "vp / (4*length), vp = c/sqrt(eps_eff)",
                "Q_loaded": "f0 / bandwidth",
            },
            "limitations": [
                "No radiation loss modelling",
                "No coupler mismatch",
                "Quasi-static approximation valid up to ~50 GHz",
                "Must cross-validate with openEMS FDTD for signoff",
            ],
        },
    }
    if ts_path_str is not None:
        result["touchstone_path"] = ts_path_str

    if report_path is not None:
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["report_path"] = str(rp)

    return result


def cross_validate_with_openems(
    analytical: dict[str, Any],
    openems: dict[str, Any],
    *,
    tolerance_pct: float = 10.0,
) -> dict[str, Any]:
    """Cross-check analytical CPW model against openEMS FDTD result.

    Returns agreement dict. Disagreement above tolerance_pct → physics_signoff = False.
    """
    if openems.get("status") != "executed":
        return {
            "status": "skipped",
            "reason": "openEMS result not available for cross-validation",
            "physics_signoff": False,
        }

    a_z0 = analytical.get("cpw", {}).get("z0_ohm")
    o_z0 = openems.get("z0_ohm")
    a_f0 = analytical.get("resonator", {}).get("f0_ghz")
    o_f0 = openems.get("f0_GHz")

    checks: list[dict[str, Any]] = []
    all_pass = True

    for name, a_val, o_val, unit in [
        ("Z0", a_z0, o_z0, "ohm"),
        ("f0", a_f0, o_f0, "GHz"),
    ]:
        if a_val is None or o_val is None:
            checks.append({"quantity": name, "status": "skipped", "reason": "value missing"})
            continue
        diff_pct = abs(a_val - o_val) / max(abs(o_val), 1e-30) * 100.0
        passed = diff_pct <= tolerance_pct
        if not passed:
            all_pass = False
        checks.append({
            "quantity": name,
            "analytical": a_val,
            "openems": o_val,
            "unit": unit,
            "difference_pct": round(diff_pct, 2),
            "tolerance_pct": tolerance_pct,
            "passed": passed,
        })

    return {
        "status": "ok",
        "physics_signoff": all_pass,
        "checks": checks,
        "verdict": "AGREE" if all_pass else f"DISAGREE (tolerance {tolerance_pct}%)",
    }
