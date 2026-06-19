"""Scalable transfer-matrix and reduced 3WM models for loaded JTWPAs.

The reference configuration reproduces Gaydamachenko et al.,
arXiv:2209.11052v2.  Linear dispersion, stop bands, reflection, phase
mismatch, and coherence length are computed directly from Appendix B.  The
nonlinear coupling magnitude is an explicit paper calibration because the
project does not bundle WRspice's Josephson-device transient solver.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


@dataclass(frozen=True)
class Jtwpa3WMConfig:
    """Typed circuit and sweep configuration for a periodically loaded JTWPA."""

    name: str
    cell_count: int
    loading_period: int
    capacitance_profile_ff: tuple[float, ...]
    squid_inductance_ph: float
    junction_capacitance_ff: float
    reference_impedance_ohm: float
    pump_frequency_ghz: float
    pump_current_ua: float
    signal_start_ghz: float = 0.5
    signal_stop_ghz: float = 12.0
    signal_points: int = 1151
    calibrated_phase_matched_gain_db: float = 21.5
    gain_ripple_db: float = 1.5
    gain_ripple_period_ghz: float = 0.160

    def validate(self) -> None:
        if self.cell_count < 1:
            raise ValueError("cell_count must be positive")
        if self.loading_period < 1:
            raise ValueError("loading_period must be positive")
        if self.cell_count % self.loading_period:
            raise ValueError("cell_count must be divisible by loading_period")
        if len(self.capacitance_profile_ff) != self.loading_period:
            raise ValueError("capacitance_profile_ff length must equal loading_period")
        if any(value <= 0.0 for value in self.capacitance_profile_ff):
            raise ValueError("all ground capacitances must be positive")
        for name, value in {
            "squid_inductance_ph": self.squid_inductance_ph,
            "junction_capacitance_ff": self.junction_capacitance_ff,
            "reference_impedance_ohm": self.reference_impedance_ohm,
            "pump_frequency_ghz": self.pump_frequency_ghz,
            "pump_current_ua": self.pump_current_ua,
            "gain_ripple_period_ghz": self.gain_ripple_period_ghz,
        }.items():
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.signal_points < 101:
            raise ValueError("signal_points must be at least 101")
        if not 0.0 < self.signal_start_ghz < self.signal_stop_ghz:
            raise ValueError("signal frequencies must satisfy 0 < start < stop")


def gaydamachenko_reference_config(
    *,
    pump_frequency_ghz: float = 12.92,
    signal_points: int = 1151,
) -> Jtwpa3WMConfig:
    """Return the dispersion-engineered JTWPA parameters from arXiv:2209.11052v2."""
    c01, c02, c03 = 8.8, 62.3, 80.0
    profile = (c01,) * 5 + (c02,) * 5 + (c01,) * 5 + (c03,) * 5
    config = Jtwpa3WMConfig(
        name="gaydamachenko-2022-3wm-jtwpa",
        cell_count=1500,
        loading_period=20,
        capacitance_profile_ff=profile,
        squid_inductance_ph=109.0,
        junction_capacitance_ff=20.0,
        reference_impedance_ohm=50.0,
        pump_frequency_ghz=pump_frequency_ghz,
        pump_current_ua=1.8,
        signal_points=signal_points,
    )
    config.validate()
    return config


def _multiply_abcd(
    left: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    right: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a, b, c, d = left
    e, f, g, h = right
    return a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h


def _unit_cell_abcd(
    frequency_ghz: Iterable[float] | np.ndarray,
    config: Jtwpa3WMConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    config.validate()
    frequency = np.asarray(frequency_ghz, dtype=float)
    omega = 2.0 * math.pi * frequency * 1e9
    one = np.ones_like(omega, dtype=complex)
    zero = np.zeros_like(omega, dtype=complex)
    result = (one, zero, zero, one)
    inductance = config.squid_inductance_ph * 1e-12
    junction_capacitance = config.junction_capacitance_ff * 1e-15
    denominator = 1.0 - omega**2 * junction_capacitance * inductance
    for capacitance_ff in config.capacitance_profile_ff:
        capacitance = capacitance_ff * 1e-15
        a = 1.0 - 0.5 * omega**2 * inductance * capacitance / denominator
        b = 1j * omega * inductance / denominator
        c = 1j * omega * capacitance - (
            0.25j * omega**3 * inductance * capacitance**2 / denominator
        )
        result = _multiply_abcd(result, (a, b, c, a))
    return result


def _abcd_power(
    matrix: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    exponent: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if exponent < 0:
        raise ValueError("exponent must be non-negative")
    one = np.ones_like(matrix[0], dtype=complex)
    zero = np.zeros_like(matrix[0], dtype=complex)
    result = (one, zero, zero, one)
    power = matrix
    count = exponent
    while count:
        if count & 1:
            result = _multiply_abcd(result, power)
        power = _multiply_abcd(power, power)
        count >>= 1
    return result


def jtwpa_linear_response(
    frequency_ghz: Iterable[float] | np.ndarray,
    config: Jtwpa3WMConfig,
) -> dict[str, np.ndarray]:
    """Compute vectorized finite-line S11/S21 and periodic-cell discriminant."""
    frequency = np.asarray(frequency_ghz, dtype=float)
    unit = _unit_cell_abcd(frequency, config)
    discriminant = np.real_if_close((unit[0] + unit[3]) / 2.0).real
    periods = config.cell_count // config.loading_period
    a, b, c, d = _abcd_power(unit, periods)
    z0 = config.reference_impedance_ohm
    denominator = a + b / z0 + c * z0 + d
    s11 = (a + b / z0 - c * z0 - d) / denominator
    s21 = 2.0 / denominator
    return {
        "frequency_ghz": frequency,
        "discriminant": discriminant,
        "s11": s11,
        "s21": s21,
    }


def _interpolate_boundary(f0: float, f1: float, y0: float, y1: float) -> float:
    if abs(y1 - y0) < 1e-15:
        return (f0 + f1) / 2.0
    return float(f0 + np.clip(-y0 / (y1 - y0), 0.0, 1.0) * (f1 - f0))


def jtwpa_stop_bands(
    config: Jtwpa3WMConfig,
    *,
    max_frequency_ghz: float = 40.0,
    points: int = 40001,
) -> list[dict[str, float | int]]:
    """Locate stop bands where the periodic-cell Bloch discriminant exceeds unity."""
    if points < 1001:
        raise ValueError("points must be at least 1001")
    frequency = np.linspace(1e-6, max_frequency_ghz, points)
    discriminant = jtwpa_linear_response(frequency, config)["discriminant"]
    blocked = np.abs(discriminant) > 1.0
    starts = np.flatnonzero(blocked & ~np.r_[False, blocked[:-1]])
    ends = np.flatnonzero(blocked & ~np.r_[blocked[1:], False])
    bands: list[dict[str, float | int]] = []
    for number, (start, end) in enumerate(zip(starts, ends), start=1):
        if start == 0 or end >= points - 1:
            continue
        sign = 1.0 if discriminant[start] > 1.0 else -1.0
        lower = _interpolate_boundary(
            frequency[start - 1],
            frequency[start],
            sign * discriminant[start - 1] - 1.0,
            sign * discriminant[start] - 1.0,
        )
        upper = _interpolate_boundary(
            frequency[end],
            frequency[end + 1],
            sign * discriminant[end] - 1.0,
            sign * discriminant[end + 1] - 1.0,
        )
        bands.append(
            {"number": number, "lower_ghz": lower, "upper_ghz": upper, "width_ghz": upper - lower}
        )
    return bands


def jtwpa_bloch_wavenumber(
    frequency_ghz: Iterable[float] | np.ndarray,
    config: Jtwpa3WMConfig,
    *,
    band: int = 1,
) -> np.ndarray:
    """Return unfolded Bloch wavenumber in radians per elementary cell."""
    if band not in {1, 2}:
        raise ValueError("band must be 1 or 2")
    unit = _unit_cell_abcd(frequency_ghz, config)
    discriminant = np.real_if_close((unit[0] + unit[3]) / 2.0).real
    phase = np.arccos(np.clip(discriminant, -1.0, 1.0))
    unfolded_phase = phase if band == 1 else 2.0 * math.pi - phase
    return unfolded_phase / config.loading_period


def jtwpa_reduced_3wm_gain(config: Jtwpa3WMConfig) -> dict[str, Any]:
    """Compute a reduced 3WM gain curve from TMM phase mismatch."""
    config.validate()
    signal = np.linspace(config.signal_start_ghz, config.signal_stop_ghz, config.signal_points)
    idler = config.pump_frequency_ghz - signal
    pump_k = float(jtwpa_bloch_wavenumber([config.pump_frequency_ghz], config, band=2)[0])
    signal_k = jtwpa_bloch_wavenumber(signal, config, band=1)
    idler_k = jtwpa_bloch_wavenumber(idler, config, band=1)
    mismatch = pump_k - signal_k - idler_k

    length = float(config.cell_count)
    coupling = math.acosh(
        math.sqrt(10.0 ** (config.calibrated_phase_matched_gain_db / 10.0))
    ) / length
    growth = np.sqrt(coupling**2 - (mismatch / 2.0) ** 2 + 0j)
    ratio = np.where(np.abs(growth) > 1e-12, np.sinh(growth * length) / growth, length)
    amplitude = np.cosh(growth * length) + 0.5j * mismatch * ratio
    smooth_gain_db = 10.0 * np.log10(np.maximum(np.abs(amplitude) ** 2, 1.0))
    ripple = config.gain_ripple_db * np.sin(
        2.0 * math.pi * (signal - 3.0) / config.gain_ripple_period_ghz
    )
    gain_db = np.maximum(smooth_gain_db + ripple, 0.0)

    reference_signal_ghz = 6.7
    reference_index = int(np.argmin(np.abs(signal - reference_signal_ghz)))
    reference_mismatch = float(mismatch[reference_index])
    coherence_length = math.pi / max(abs(reference_mismatch), 1e-15)
    band_mask = (signal >= 3.0) & (signal <= 9.0)
    return {
        "signal_frequency_ghz": signal.tolist(),
        "idler_frequency_ghz": idler.tolist(),
        "phase_mismatch_per_cell": mismatch.tolist(),
        "smooth_gain_db": smooth_gain_db.tolist(),
        "gain_db": gain_db.tolist(),
        "coupling_per_cell": coupling,
        "coherence_length_cells_at_6p7ghz": coherence_length,
        "reported_coherence_length_cells": 2186.0,
        "gain_3_to_9_ghz": {
            "minimum_db": float(np.min(gain_db[band_mask])),
            "maximum_db": float(np.max(gain_db[band_mask])),
            "mean_db": float(np.mean(gain_db[band_mask])),
            "peak_to_peak_ripple_db": float(np.ptp(gain_db[band_mask])),
        },
        "model_validity": (
            "Phase mismatch and coherence length are independently computed from Appendix-B "
            "transfer matrices. Nonlinear coupling and the 160 MHz finite-line ripple amplitude "
            "are calibrated to the paper's WRspice result."
        ),
    }


def write_gaydamachenko_benchmark(
    *,
    report_path: str | Path,
    csv_path: str | Path,
    plot_path: str | Path,
    paper_path: str | Path | None = None,
    pump_frequency_ghz: float = 12.92,
) -> dict[str, Any]:
    """Write a reproducible benchmark for arXiv:2209.11052v2."""
    report_file, csv_file, plot_file = Path(report_path), Path(csv_path), Path(plot_path)
    for path in (report_file, csv_file, plot_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    config = gaydamachenko_reference_config(pump_frequency_ghz=pump_frequency_ghz)
    frequency = np.linspace(0.5, 32.0, 3151)
    linear = jtwpa_linear_response(frequency, config)
    stop_bands = jtwpa_stop_bands(config)
    gain = jtwpa_reduced_3wm_gain(config)
    first, second = stop_bands[:2]
    coherence_error = abs(gain["coherence_length_cells_at_6p7ghz"] - 2186.0) / 2186.0
    band_metrics = gain["gain_3_to_9_ghz"]
    checks = {
        "pump_is_above_first_stop_band": pump_frequency_ghz > float(first["upper_ghz"]),
        "second_harmonic_is_inside_second_stop_band": (
            float(second["lower_ghz"]) < 2.0 * pump_frequency_ghz < float(second["upper_ghz"])
        ),
        "coherence_length_within_15_percent": coherence_error <= 0.15,
        "coherence_length_exceeds_device": (
            gain["coherence_length_cells_at_6p7ghz"] > config.cell_count
        ),
        "three_to_nine_ghz_gain_exceeds_18db": band_metrics["minimum_db"] >= 18.0,
        "paper_pdf_present": paper_path is not None and Path(paper_path).is_file(),
    }

    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["signal_frequency_ghz", "idler_frequency_ghz", "phase_mismatch_per_cell", "smooth_gain_db", "gain_db"],
        )
        writer.writeheader()
        for row in zip(
            gain["signal_frequency_ghz"],
            gain["idler_frequency_ghz"],
            gain["phase_mismatch_per_cell"],
            gain["smooth_gain_db"],
            gain["gain_db"],
        ):
            writer.writerow(dict(zip(writer.fieldnames, row)))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(9.2, 9.0), constrained_layout=True)
    axes[0].plot(gain["signal_frequency_ghz"], gain["gain_db"], linewidth=1.2)
    axes[0].axvspan(3.0, 9.0, color="#34c759", alpha=0.12, label="paper target band")
    axes[0].set(xlabel="signal frequency (GHz)", ylabel="gain (dB)")
    axes[0].legend()
    axes[1].plot(frequency, 20.0 * np.log10(np.maximum(np.abs(linear["s11"]), 1e-12)))
    for band in stop_bands[:2]:
        axes[1].axvspan(band["lower_ghz"], band["upper_ghz"], color="#ff9f0a", alpha=0.15)
    axes[1].axvline(pump_frequency_ghz, color="#af52de", linestyle="--", label="pump")
    axes[1].axvline(2.0 * pump_frequency_ghz, color="#ff3b30", linestyle="--", label="2 x pump")
    axes[1].set(xlabel="frequency (GHz)", ylabel="|S11| (dB)", ylim=(-40.0, 2.0))
    axes[1].legend()
    axes[2].plot(gain["signal_frequency_ghz"], gain["phase_mismatch_per_cell"])
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set(xlabel="signal frequency (GHz)", ylabel="phase mismatch (rad/cell)")
    fig.suptitle("Gaydamachenko 3WM JTWPA reproduction")
    fig.savefig(plot_file, dpi=200)
    plt.close(fig)

    result = {
        "schema": "text-to-gds.gaydamachenko-jtwpa-benchmark.v0",
        "status": "passed" if all(checks.values()) else "failed",
        "paper": {
            "title": "Numerical analysis of a three-wave-mixing Josephson traveling-wave parametric amplifier with engineered dispersion loadings",
            "arxiv": "2209.11052v2",
            "path": str(Path(paper_path)) if paper_path is not None else None,
        },
        "config": asdict(config),
        "stop_bands": stop_bands,
        "gain": gain,
        "checks": checks,
        "comparison": {
            "computed_coherence_length_cells": gain["coherence_length_cells_at_6p7ghz"],
            "reported_coherence_length_cells": 2186.0,
            "coherence_length_relative_error": coherence_error,
            "reported_gain_band_ghz": [3.0, 9.0],
            "computed_gain_in_reported_band": band_metrics,
        },
        "scaling": {
            "frequency_points": len(frequency),
            "unit_cell_matrix_multiplications_per_frequency": config.loading_period,
            "line_cascade": "binary matrix exponentiation",
            "complexity": "O(F * (m + log(N/m))) time and O(F) memory",
        },
        "artifacts": {
            "report_path": str(report_file),
            "csv_path": str(csv_file),
            "plot_path": str(plot_file),
        },
    }
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
