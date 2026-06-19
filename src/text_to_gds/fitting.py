"""Measurement fitting engine for resonator, JPA gain, pump, and noise traces.

The fits use a numpy moment/Lorentzian baseline that always runs, and refine
with ``scipy.optimize.curve_fit`` when SciPy is installed. They never claim a
SciPy-refined result the optional dependency did not produce; the report records
the actual method used.
"""

from __future__ import annotations

import csv
import json
import math
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import numpy as np

PLANCK_J_S = 6.62607015e-34
BOLTZMANN_J_K = 1.380649e-23

SCIPY_AVAILABLE = find_spec("scipy") is not None


# --------------------------------------------------------------------------- #
# Trace loading
# --------------------------------------------------------------------------- #

_FREQUENCY_ALIASES = {
    "frequency_ghz": 1.0,
    "freq_ghz": 1.0,
    "f_ghz": 1.0,
    "frequency_mhz": 1e-3,
    "freq_mhz": 1e-3,
    "frequency_hz": 1e-9,
    "freq_hz": 1e-9,
    "frequency": 1.0,
    "freq": 1.0,
    "f": 1.0,
}
_GAIN_ALIASES = ("gain_db", "gain", "s21_gain_db", "reflection_gain_db")
_S21_DB_ALIASES = ("s21_db", "s21_mag_db", "mag_db", "logmag", "logmag_db")
_S21_MAG_ALIASES = ("s21_mag", "s21_lin", "s21", "mag", "magnitude")
_S21_RE_ALIASES = ("s21_re", "s21_real", "re", "real")
_S21_IM_ALIASES = ("s21_im", "s21_imag", "im", "imag")
_NOISE_ALIASES = ("noise_temperature_k", "noise_k", "tn_k", "system_noise_k", "noise")
_PUMP_ALIASES = ("pump_fraction", "pump_current_fraction", "pump", "pump_current_ua", "power_dbm")


def _first_column(columns: dict[str, list[float]], names: tuple[str, ...]) -> list[float] | None:
    for name in names:
        if name in columns:
            return columns[name]
    return None


def _frequency_ghz(columns: dict[str, list[float]]) -> np.ndarray | None:
    for name, scale in _FREQUENCY_ALIASES.items():
        if name in columns:
            return np.asarray(columns[name], dtype=float) * scale
    return None


def _columns_from_csv(path: Path) -> dict[str, list[float]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        rows = [row for row in reader if row and not row[0].lstrip().startswith(("#", "!", "*"))]
    if not rows:
        raise ValueError(f"No data rows in {path}")
    header = [cell.strip().lower().lstrip("|").rstrip("|") for cell in rows[0]]
    try:
        [float(cell) for cell in rows[0]]
        has_header = False
    except ValueError:
        has_header = True
    if not has_header:
        header = [f"col_{index}" for index in range(len(rows[0]))]
        data_rows = rows
    else:
        data_rows = rows[1:]
    columns: dict[str, list[float]] = {name: [] for name in header}
    for row in data_rows:
        for index, name in enumerate(header):
            if index >= len(row):
                continue
            try:
                columns[name].append(float(row[index]))
            except ValueError:
                continue
    return {name: values for name, values in columns.items() if values}


def _columns_from_json(payload: dict[str, Any]) -> dict[str, list[float]]:
    columns: dict[str, list[float]] = {}

    def absorb(mapping: dict[str, Any]) -> None:
        for key, value in mapping.items():
            if isinstance(value, list) and value and all(
                isinstance(item, (int, float)) for item in value
            ):
                columns.setdefault(key.lower(), [float(item) for item in value])

    absorb(payload)
    sub = payload.get("s_parameters_db")
    if isinstance(sub, dict):
        absorb(sub)
    return columns


def load_measurement_trace(path: str | Path) -> dict[str, Any]:
    """Load a measurement/simulation trace from CSV or JSON into named arrays."""
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {source}")
        columns = _columns_from_json(payload)
    else:
        columns = _columns_from_csv(source)

    frequency_ghz = _frequency_ghz(columns)
    trace: dict[str, Any] = {"source": str(source), "columns": sorted(columns)}
    if frequency_ghz is not None:
        trace["frequency_ghz"] = frequency_ghz

    gain = _first_column(columns, _GAIN_ALIASES)
    if gain is not None:
        trace["gain_db"] = np.asarray(gain, dtype=float)

    s21_db = _first_column(columns, _S21_DB_ALIASES)
    re = _first_column(columns, _S21_RE_ALIASES)
    im = _first_column(columns, _S21_IM_ALIASES)
    mag = _first_column(columns, _S21_MAG_ALIASES)
    if s21_db is not None:
        trace["s21_mag"] = 10.0 ** (np.asarray(s21_db, dtype=float) / 20.0)
    elif re is not None and im is not None:
        trace["s21_mag"] = np.abs(np.asarray(re, dtype=float) + 1j * np.asarray(im, dtype=float))
    elif mag is not None:
        trace["s21_mag"] = np.asarray(mag, dtype=float)

    noise = _first_column(columns, _NOISE_ALIASES)
    if noise is not None:
        trace["noise_temperature_k"] = np.asarray(noise, dtype=float)

    pump = _first_column(columns, _PUMP_ALIASES)
    if pump is not None:
        trace["pump"] = np.asarray(pump, dtype=float)
    return trace


def infer_fit_kind(trace: dict[str, Any]) -> str:
    """Choose a fit from the columns a trace actually contains."""
    if "noise_temperature_k" in trace:
        return "noise"
    if "pump" in trace and "gain_db" in trace:
        return "jpa_pump"
    if "gain_db" in trace:
        return "jpa_gain"
    if "s21_mag" in trace:
        return "resonator"
    raise ValueError("Could not infer a fit kind; provide gain_db, s21_mag, or noise columns")


# --------------------------------------------------------------------------- #
# Peak/notch helpers
# --------------------------------------------------------------------------- #

def _parabolic_extremum(x: np.ndarray, y: np.ndarray, index: int) -> float:
    """Refine an extremum location with a 3-point parabola; clamp to the grid."""
    if index <= 0 or index >= len(x) - 1:
        return float(x[index])
    x0, x1, x2 = x[index - 1], x[index], x[index + 1]
    y0, y1, y2 = y[index - 1], y[index], y[index + 1]
    denom = (y0 - 2.0 * y1 + y2)
    if abs(denom) < 1e-30:
        return float(x1)
    delta = 0.5 * (y0 - y2) / denom
    return float(x1 + delta * (x2 - x1) if delta >= 0 else x1 + delta * (x1 - x0))


def _threshold_width(x: np.ndarray, y: np.ndarray, center_index: int, level: float) -> float | None:
    """Full width where ``y`` crosses ``level`` on each side of ``center_index``."""
    left = None
    for i in range(center_index, 0, -1):
        if (y[i] - level) * (y[i - 1] - level) <= 0.0 and y[i] != y[i - 1]:
            frac = (level - y[i]) / (y[i - 1] - y[i])
            left = float(x[i] + frac * (x[i - 1] - x[i]))
            break
    right = None
    for i in range(center_index, len(x) - 1):
        if (y[i] - level) * (y[i + 1] - level) <= 0.0 and y[i] != y[i + 1]:
            frac = (level - y[i]) / (y[i + 1] - y[i])
            right = float(x[i] + frac * (x[i + 1] - x[i]))
            break
    if left is None or right is None:
        return None
    return abs(right - left)


# --------------------------------------------------------------------------- #
# Resonator fit (notch / hanger)
# --------------------------------------------------------------------------- #

def fit_resonator(frequencies_ghz: np.ndarray, s21_mag: np.ndarray) -> dict[str, Any]:
    """Fit a symmetric notch resonator for f0, Ql, Qc, and Qi.

    Baseline is a Lorentzian-notch moment estimate on ``|S21|**2``; SciPy refines
    the three parameters when available. Assumes ``|S21|`` is normalized to ~1 off
    resonance and dips at resonance (hanger geometry).
    """
    freq = np.asarray(frequencies_ghz, dtype=float)
    mag = np.asarray(s21_mag, dtype=float)
    if freq.size < 5 or freq.size != mag.size:
        raise ValueError("Resonator fit needs at least 5 aligned frequency/|S21| points")

    baseline = float(np.median(np.sort(mag)[-max(3, mag.size // 10):]))
    if baseline <= 0.0:
        raise ValueError("Off-resonance |S21| baseline must be positive")
    normalized = np.clip(mag / baseline, 0.0, None)
    power = normalized**2

    notch_index = int(np.argmin(power))
    f0 = _parabolic_extremum(freq, power, notch_index)
    s21_min = float(math.sqrt(max(power[notch_index], 0.0)))
    depth = 1.0 - power[notch_index]
    width = _threshold_width(freq, power, notch_index, 1.0 - depth / 2.0)
    if not width or width <= 0.0:
        raise ValueError("Could not resolve the notch width; increase frequency resolution")
    ql = f0 / width
    method = "numpy_lorentzian_moment"

    if SCIPY_AVAILABLE:
        try:
            from scipy.optimize import curve_fit

            def model(f: np.ndarray, f0_: float, ql_: float, smin_: float) -> np.ndarray:
                x = 2.0 * ql_ * (f - f0_) / f0_
                return 1.0 - (1.0 - smin_**2) / (1.0 + x**2)

            popt, _ = curve_fit(
                model,
                freq,
                power,
                p0=[f0, ql, max(s21_min, 1e-3)],
                maxfev=20000,
            )
            f0, ql, s21_min = float(popt[0]), float(abs(popt[1])), float(min(abs(popt[2]), 0.999))
            method = "scipy_curve_fit"
        except Exception:  # pragma: no cover - refinement is best effort
            method = "numpy_lorentzian_moment_scipy_failed"

    s21_min = min(max(s21_min, 1e-6), 0.999999)
    qc = ql / max(1.0 - s21_min, 1e-9)
    qi = ql / max(s21_min, 1e-9)
    return {
        "fit_kind": "resonator",
        "model": "symmetric_notch_hanger",
        "method": method,
        "scipy_available": SCIPY_AVAILABLE,
        "f0_ghz": f0,
        "loaded_q": ql,
        "coupling_q": qc,
        "internal_q": qi,
        "notch_depth_db": 20.0 * math.log10(max(s21_min, 1e-9)),
        "off_resonance_baseline": baseline,
        "points": int(freq.size),
        "model_validity": (
            "Symmetric-notch magnitude fit. For asymmetric Fano lineshapes or "
            "absolute coupling sign, use a full complex circle fit on I/Q data."
        ),
    }


# --------------------------------------------------------------------------- #
# JPA gain fit
# --------------------------------------------------------------------------- #

def fit_jpa_gain(frequencies_ghz: np.ndarray, gain_db: np.ndarray) -> dict[str, Any]:
    """Fit a JPA gain peak for peak gain, center, 3 dB bandwidth, and GBP."""
    freq = np.asarray(frequencies_ghz, dtype=float)
    gain = np.asarray(gain_db, dtype=float)
    if freq.size < 5 or freq.size != gain.size:
        raise ValueError("JPA gain fit needs at least 5 aligned frequency/gain points")

    peak_index = int(np.argmax(gain))
    center_ghz = _parabolic_extremum(freq, gain, peak_index)
    peak_gain_db = float(gain[peak_index])
    method = "numpy_peak_bandwidth"

    if SCIPY_AVAILABLE:
        try:
            from scipy.optimize import curve_fit

            def model(f: np.ndarray, g0: float, f0_: float, hwhm: float) -> np.ndarray:
                return g0 - 10.0 * np.log10(1.0 + ((f - f0_) / max(hwhm, 1e-9)) ** 2)

            span = max(freq.max() - freq.min(), 1e-6)
            popt, _ = curve_fit(
                model,
                freq,
                gain,
                p0=[peak_gain_db, center_ghz, span / 10.0],
                maxfev=20000,
            )
            peak_gain_db, center_ghz = float(popt[0]), float(popt[1])
            method = "scipy_curve_fit"
        except Exception:  # pragma: no cover - refinement is best effort
            method = "numpy_peak_bandwidth_scipy_failed"

    width_ghz = _threshold_width(freq, gain, peak_index, peak_gain_db - 3.0)
    bandwidth_mhz = width_ghz * 1000.0 if width_ghz else None
    voltage_gain = 10.0 ** (peak_gain_db / 20.0)
    gbp_mhz = voltage_gain * bandwidth_mhz if bandwidth_mhz is not None else None
    return {
        "fit_kind": "jpa_gain",
        "model": "lorentzian_gain_peak",
        "method": method,
        "scipy_available": SCIPY_AVAILABLE,
        "peak_gain_db": peak_gain_db,
        "center_frequency_ghz": center_ghz,
        "bandwidth_3db_mhz": bandwidth_mhz,
        "gain_bandwidth_product_mhz": gbp_mhz,
        "points": int(freq.size),
        "model_validity": (
            "Single-trace gain fit. Kerr coefficient and pump efficiency require a "
            "pump-power sweep (export_jpa_analysis / fit_jpa_pump)."
        ),
    }


def fit_jpa_pump(pump: np.ndarray, gain_db: np.ndarray) -> dict[str, Any]:
    """Estimate the oscillation threshold and pump response from a gain-vs-pump sweep."""
    pump_axis = np.asarray(pump, dtype=float)
    gain = np.asarray(gain_db, dtype=float)
    if pump_axis.size < 4 or pump_axis.size != gain.size:
        raise ValueError("Pump sweep fit needs at least 4 aligned pump/gain points")
    order = np.argsort(pump_axis)
    pump_axis, gain = pump_axis[order], gain[order]
    threshold_index = int(np.argmax(gain))
    return {
        "fit_kind": "jpa_pump",
        "model": "gain_vs_pump_threshold",
        "oscillation_threshold_pump": float(pump_axis[threshold_index]),
        "peak_gain_db": float(gain[threshold_index]),
        "pump_at_20db": _interpolate_crossing(pump_axis, gain, 20.0),
        "points": int(pump_axis.size),
        "model_validity": (
            "Threshold is the gain maximum in the supplied sweep. A calibrated Kerr "
            "coefficient still needs harmonic-balance pump modelling."
        ),
    }


def _interpolate_crossing(x: np.ndarray, y: np.ndarray, level: float) -> float | None:
    for i in range(len(x) - 1):
        if (y[i] - level) * (y[i + 1] - level) <= 0.0 and y[i] != y[i + 1]:
            frac = (level - y[i]) / (y[i + 1] - y[i])
            return float(x[i] + frac * (x[i + 1] - x[i]))
    return None


def fit_noise(
    frequencies_ghz: np.ndarray,
    noise_temperature_k: np.ndarray,
) -> dict[str, Any]:
    """Summarize a system-noise-temperature trace against the quantum limit."""
    freq = np.asarray(frequencies_ghz, dtype=float)
    noise = np.asarray(noise_temperature_k, dtype=float)
    if freq.size != noise.size or freq.size < 2:
        raise ValueError("Noise fit needs aligned frequency/noise-temperature points")
    best_index = int(np.argmin(noise))
    f0 = float(freq[best_index])
    min_noise = float(noise[best_index])
    quantum_limit = PLANCK_J_S * f0 * 1e9 / (2.0 * BOLTZMANN_J_K)
    added_quanta = min_noise / max(quantum_limit, 1e-30) - 0.5
    return {
        "fit_kind": "noise",
        "model": "noise_temperature_summary",
        "minimum_noise_temperature_k": min_noise,
        "frequency_at_minimum_ghz": f0,
        "median_noise_temperature_k": float(np.median(noise)),
        "quantum_limit_k": quantum_limit,
        "added_noise_quanta": added_quanta,
        "points": int(freq.size),
        "model_validity": "Y-factor/noise summary; calibration offsets must be removed upstream.",
    }


# --------------------------------------------------------------------------- #
# Dispatch + artifact writer
# --------------------------------------------------------------------------- #

def fit_trace(trace: dict[str, Any], fit_kind: str = "auto") -> dict[str, Any]:
    """Run the requested (or inferred) fit on a loaded trace."""
    kind = infer_fit_kind(trace) if fit_kind == "auto" else fit_kind
    if kind == "resonator":
        return fit_resonator(trace["frequency_ghz"], trace["s21_mag"])
    if kind == "jpa_gain":
        return fit_jpa_gain(trace["frequency_ghz"], trace["gain_db"])
    if kind == "jpa_pump":
        return fit_jpa_pump(trace["pump"], trace["gain_db"])
    if kind == "noise":
        return fit_noise(trace["frequency_ghz"], trace["noise_temperature_k"])
    raise ValueError(f"Unknown fit kind: {kind}")


def _plot_fit(trace: dict[str, Any], fit: dict[str, Any], plot_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    kind = fit["fit_kind"]
    if kind == "resonator":
        freq = trace["frequency_ghz"]
        ax.plot(freq, 20.0 * np.log10(np.clip(trace["s21_mag"], 1e-9, None)), ".", ms=4)
        ax.axvline(fit["f0_ghz"], color="crimson", ls="--", lw=1)
        ax.set_ylabel("|S21| (dB)")
        ax.set_title(
            f"Resonator fit: f0={fit['f0_ghz']:.4f} GHz, "
            f"Qi={fit['internal_q']:.0f}, Qc={fit['coupling_q']:.0f}"
        )
    elif kind in {"jpa_gain", "jpa_pump"}:
        x = trace["frequency_ghz"] if kind == "jpa_gain" else trace["pump"]
        ax.plot(x, trace["gain_db"], ".-", ms=4)
        ax.set_ylabel("Gain (dB)")
        ax.set_xlabel("Frequency (GHz)" if kind == "jpa_gain" else "Pump")
        ax.set_title(f"{kind} fit: peak {fit['peak_gain_db']:.2f} dB")
    else:
        ax.plot(trace["frequency_ghz"], trace["noise_temperature_k"], ".-", ms=4)
        ax.set_ylabel("Noise temperature (K)")
        ax.set_title(f"Noise fit: min {fit['minimum_noise_temperature_k']:.3f} K")
    if kind != "jpa_pump":
        ax.set_xlabel("Frequency (GHz)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def write_measurement_fit(
    data_path: str | Path,
    *,
    report_path: str | Path,
    plot_path: str | Path,
    fit_kind: str = "auto",
) -> dict[str, Any]:
    """Load a trace, fit it, write a JSON report and a plot, and return the result."""
    trace = load_measurement_trace(data_path)
    fit = fit_trace(trace, fit_kind=fit_kind)
    report = {
        "schema": "text-to-gds.measurement-fit.v1",
        "source": str(data_path),
        "available_columns": trace["columns"],
        "fit": fit,
    }
    if "frequency_ghz" in trace or "pump" in trace:
        try:
            _plot_fit(trace, fit, Path(plot_path))
            report["plot_path"] = str(plot_path)
        except Exception as exc:  # pragma: no cover - plotting is best effort
            report["plot_error"] = str(exc)
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_file)
    return report


def measurement_from_fit(fit: dict[str, Any]) -> dict[str, Any]:
    """Convert a fit result into the measurement dict consumed by record_experiment."""
    kind = fit.get("fit_kind")
    if kind == "resonator":
        return {
            "center_frequency_ghz": fit["f0_ghz"],
            "internal_q": fit["internal_q"],
            "coupling_q": fit["coupling_q"],
            "loaded_q": fit["loaded_q"],
        }
    if kind == "jpa_gain":
        return {
            "center_frequency_ghz": fit["center_frequency_ghz"],
            "peak_gain_db": fit["peak_gain_db"],
            "bandwidth_3db_mhz": fit["bandwidth_3db_mhz"],
        }
    if kind == "noise":
        return {
            "center_frequency_ghz": fit["frequency_at_minimum_ghz"],
            "noise_temperature_k": fit["minimum_noise_temperature_k"],
        }
    return {key: value for key, value in fit.items() if isinstance(value, (int, float))}
