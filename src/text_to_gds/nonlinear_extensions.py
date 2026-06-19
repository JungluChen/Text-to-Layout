"""Nonlinear JPA/JTWPA models, stability, pump, and dynamic-range analysis."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def solve_duffing_steady_state(
    *, detuning_hz: list[float], drive_amplitude: float, damping_hz: float, kerr_hz: float
) -> dict[str, Any]:
    """Solve |a|^2[(Delta+K|a|^2)^2+(kappa/2)^2]=|eps|^2."""
    if damping_hz <= 0.0 or drive_amplitude < 0.0:
        raise ValueError("Damping must be positive and drive non-negative")
    rows = []
    for detuning in detuning_hz:
        coefficients = [kerr_hz**2, 2.0 * detuning * kerr_hz, detuning**2 + (damping_hz / 2.0) ** 2, -drive_amplitude**2]
        roots = np.roots(coefficients)
        physical = sorted(float(root.real) for root in roots if abs(root.imag) < 1e-7 and root.real >= 0.0)
        rows.append({"detuning_hz": detuning, "photon_numbers": physical, "multistable": len(physical) > 1})
    return {"schema": "text-to-gds.duffing.v1", "solutions": rows, "bifurcation_detected": any(row["multistable"] for row in rows)}


def amplifier_model(kind: str, **parameters: float) -> dict[str, Any]:
    """Normalize SNAIL, IMPA, KIT, JPA, and TWPA parameters into one model."""
    normalized = kind.upper().replace("-", "")
    supported = {"JPA", "SNAIL", "IMPA", "KIT", "TWPA", "JTWPA"}
    if normalized not in supported:
        raise ValueError(f"Unsupported amplifier {kind!r}")
    mixing = "3wm" if normalized in {"SNAIL", "IMPA", "JTWPA"} else "4wm"
    return {"schema": "text-to-gds.amplifier-model.v1", "kind": normalized, "mixing": mixing, "parameters": parameters}


def phase_matching_optimizer(
    *, signal_frequencies_ghz: list[float], base_mismatch_per_m: list[float], tunable_shift_per_m: float
) -> dict[str, Any]:
    mismatch = np.asarray(base_mismatch_per_m, dtype=float)
    if len(signal_frequencies_ghz) != mismatch.size or mismatch.size == 0:
        raise ValueError("Frequency and mismatch arrays must have equal non-zero length")
    shift = float(np.median(mismatch)) if tunable_shift_per_m == 0.0 else float(np.clip(np.median(mismatch), -abs(tunable_shift_per_m), abs(tunable_shift_per_m)))
    residual = mismatch - shift
    return {"phase_shift_per_m": shift, "residual_mismatch_per_m": residual.tolist(), "rms_mismatch_per_m": float(np.sqrt(np.mean(residual**2)))}


def pump_depletion_model(*, input_pump_power_w: float, signal_power_w: list[float], small_signal_gain_power: float, conversion_efficiency: float = 1.0) -> dict[str, Any]:
    if input_pump_power_w <= 0.0 or small_signal_gain_power < 1.0 or not 0.0 < conversion_efficiency <= 1.0:
        raise ValueError("Invalid pump depletion inputs")
    rows = []
    for signal in signal_power_w:
        extracted = max(small_signal_gain_power - 1.0, 0.0) * signal / conversion_efficiency
        remaining = max(input_pump_power_w - extracted, 0.0)
        gain = 1.0 + (small_signal_gain_power - 1.0) * remaining / input_pump_power_w
        rows.append({"signal_power_w": signal, "remaining_pump_power_w": remaining, "gain_power": gain, "gain_db": 10.0 * math.log10(max(gain, 1e-30))})
    return {"schema": "text-to-gds.pump-depletion.v1", "sweep": rows}


def nonlinear_saturation(*, input_power_dbm: list[float], small_signal_gain_db: float, p1db_dbm: float) -> dict[str, Any]:
    values = np.asarray(input_power_dbm, dtype=float)
    compression = 10.0 * np.log10(1.0 + 10.0 ** ((values - p1db_dbm) / 10.0))
    return {"input_power_dbm": values.tolist(), "gain_db": (small_signal_gain_db - compression).tolist(), "p1db_dbm": p1db_dbm}


def stability_map(*, detuning_hz: list[float], pump_coupling_hz: list[float], damping_hz: float) -> dict[str, Any]:
    if damping_hz <= 0.0:
        raise ValueError("Damping must be positive")
    grid = []
    for pump in pump_coupling_hz:
        row = []
        for detuning in detuning_hz:
            margin = math.sqrt(detuning**2 + (damping_hz / 2.0) ** 2) - pump
            row.append({"margin_hz": margin, "stable": margin > 0.0})
        grid.append(row)
    return {"schema": "text-to-gds.stability-map.v1", "detuning_hz": detuning_hz, "pump_coupling_hz": pump_coupling_hz, "grid": grid}


def gain_ripple_analysis(frequency_ghz: list[float], gain_db: list[float]) -> dict[str, float]:
    frequency, gain = np.asarray(frequency_ghz), np.asarray(gain_db)
    if frequency.size != gain.size or frequency.size < 3:
        raise ValueError("At least three gain samples are required")
    trend = np.polyval(np.polyfit(frequency, gain, min(2, frequency.size - 1)), frequency)
    residual = gain - trend
    return {"peak_to_peak_ripple_db": float(np.ptp(residual)), "rms_ripple_db": float(np.sqrt(np.mean(residual**2)))}


def impedance_mismatch_analysis(impedance_profile_ohm: list[float], *, reference_ohm: float = 50.0) -> dict[str, Any]:
    values = np.asarray(impedance_profile_ohm, dtype=float)
    if values.size == 0 or np.any(values <= 0.0) or reference_ohm <= 0.0:
        raise ValueError("Impedances must be positive")
    gamma = (values - reference_ohm) / (values + reference_ohm)
    return {"reflection_coefficients": gamma.tolist(), "worst_return_loss_db": float(-20.0 * np.log10(max(np.max(np.abs(gamma)), 1e-15)))}


def standing_wave_effect(*, frequencies_hz: list[float], line_length_m: float, velocity_m_per_s: float, reflection_coefficient: float) -> dict[str, Any]:
    rows = []
    for frequency in frequencies_hz:
        phase = 4.0 * math.pi * frequency * line_length_m / velocity_m_per_s
        amplitude = abs(1.0 + reflection_coefficient * np.exp(-1j * phase))
        rows.append({"frequency_hz": frequency, "amplitude": float(amplitude), "power_ripple_db": 20.0 * math.log10(max(amplitude, 1e-15))})
    return {"samples": rows, "standing_wave_ratio": (1.0 + abs(reflection_coefficient)) / max(1.0 - abs(reflection_coefficient), 1e-15)}


def pump_leakage(*, pump_power_dbm: float, isolation_db: float, filter_rejection_db: float = 0.0) -> dict[str, float]:
    leaked = pump_power_dbm - isolation_db - filter_rejection_db
    return {"leaked_pump_power_dbm": leaked, "total_rejection_db": isolation_db + filter_rejection_db}


def pump_cancellation_design(*, leakage_amplitude: complex, cancellation_path_phase_deg: float = 0.0) -> dict[str, float]:
    path_phase = np.exp(1j * math.radians(cancellation_path_phase_deg))
    source = -leakage_amplitude / path_phase
    return {"cancellation_amplitude": float(abs(source)), "cancellation_phase_deg": float(math.degrees(np.angle(source)) % 360.0)}


def optimize_dynamic_range(*, pump_power_dbm: list[float], gain_db: list[float], p1db_dbm: list[float], target_gain_db: float) -> dict[str, float]:
    if not (len(pump_power_dbm) == len(gain_db) == len(p1db_dbm)):
        raise ValueError("Sweep arrays must have equal length")
    feasible = [(p1db, pump, gain) for pump, gain, p1db in zip(pump_power_dbm, gain_db, p1db_dbm, strict=True) if gain >= target_gain_db]
    if not feasible:
        raise ValueError("No point reaches target gain")
    p1db, pump, gain = max(feasible)
    return {"pump_power_dbm": pump, "gain_db": gain, "p1db_dbm": p1db}
