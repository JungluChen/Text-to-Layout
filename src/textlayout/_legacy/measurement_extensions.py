"""SCPI instrument adapters, calibration, automated extraction, and stability analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

BOLTZMANN = 1.380649e-23
PLANCK = 6.62607015e-34


@dataclass
class SCPIInstrument:
    """Transport-neutral SCPI driver with explicit safety limits."""

    resource: str
    write: Callable[[str], Any]
    query: Callable[[str], str]
    maximum_power_dbm: float = 0.0

    def identify(self) -> str:
        return self.query("*IDN?").strip()

    def set_output(self, enabled: bool) -> None:
        self.write(f"OUTP {'ON' if enabled else 'OFF'}")

    def set_power_dbm(self, power_dbm: float) -> None:
        if power_dbm > self.maximum_power_dbm:
            raise ValueError(f"Requested power {power_dbm} dBm exceeds limit {self.maximum_power_dbm} dBm")
        self.write(f"SOUR:POW {power_dbm}")


def instrument_driver(kind: str, resource: str, write: Callable[[str], Any], query: Callable[[str], str], *, maximum_power_dbm: float = 0.0) -> SCPIInstrument:
    supported = {"keysight_vna", "rohde_schwarz_vna", "signal_generator", "spectrum_analyzer"}
    if kind not in supported:
        raise ValueError(f"Unsupported instrument kind {kind!r}")
    return SCPIInstrument(resource, write, query, maximum_power_dbm)


def apply_vna_calibration(measured: list[complex], error_tracking: list[complex], directivity: list[complex] | None = None) -> list[complex]:
    values = np.asarray(measured, dtype=complex)
    tracking = np.asarray(error_tracking, dtype=complex)
    direct = np.zeros_like(values) if directivity is None else np.asarray(directivity, dtype=complex)
    if values.shape != tracking.shape or direct.shape != values.shape:
        raise ValueError("Calibration arrays must have equal shape")
    return ((values - direct) / np.where(np.abs(tracking) > 0.0, tracking, np.nan)).tolist()


def solt_calibration(*, open_measured: list[complex], short_measured: list[complex], load_measured: list[complex]) -> dict[str, Any]:
    open_v, short_v, load_v = map(lambda value: np.asarray(value, dtype=complex), (open_measured, short_measured, load_measured))
    if not (open_v.shape == short_v.shape == load_v.shape):
        raise ValueError("SOLT standard arrays must match")
    directivity = load_v
    tracking = (open_v - short_v) / 2.0
    source_match = (open_v + short_v) / 2.0 - directivity
    def encode(values: np.ndarray) -> list[list[float]]:
        return [[float(value.real), float(value.imag)] for value in values]
    return {"method": "SOLT", "directivity": encode(directivity), "tracking": encode(tracking), "source_match": encode(source_match)}


def trl_calibration(*, thru: list[complex], line: list[complex], line_delay_s: float, frequencies_hz: list[float]) -> dict[str, Any]:
    thru_v, line_v, frequency = np.asarray(thru, complex), np.asarray(line, complex), np.asarray(frequencies_hz, float)
    if not (thru_v.shape == line_v.shape == frequency.shape) or line_delay_s <= 0.0:
        raise ValueError("TRL arrays must match and delay must be positive")
    measured_phase = np.unwrap(np.angle(line_v / np.where(abs(thru_v) > 0.0, thru_v, np.nan)))
    ideal_phase = -2.0 * np.pi * frequency * line_delay_s
    phase_error = measured_phase - ideal_phase
    return {"method": "TRL", "phase_error_rad": phase_error.tolist(), "rms_phase_error_rad": float(np.sqrt(np.mean(phase_error**2)))}


def power_calibration(commanded_dbm: list[float], measured_dbm: list[float]) -> dict[str, float]:
    commanded, measured = np.asarray(commanded_dbm), np.asarray(measured_dbm)
    if commanded.shape != measured.shape or commanded.size < 2:
        raise ValueError("At least two matched power samples are required")
    slope, offset = np.polyfit(commanded, measured, 1)
    residual = measured - (slope * commanded + offset)
    return {"slope": float(slope), "offset_db": float(offset), "rms_error_db": float(np.sqrt(np.mean(residual**2)))}


def find_resonance(frequency_hz: list[float], response_db: list[float], *, kind: str = "dip") -> dict[str, float]:
    frequency, response = np.asarray(frequency_hz), np.asarray(response_db)
    if frequency.shape != response.shape or frequency.size < 3:
        raise ValueError("At least three response samples are required")
    index = int(np.argmin(response) if kind == "dip" else np.argmax(response))
    baseline = float(np.median(np.r_[response[: max(index // 4, 1)], response[min(index + 1, len(response) - 1) :]]))
    depth = abs(float(response[index]) - baseline)
    return {"frequency_hz": float(frequency[index]), "response_db": float(response[index]), "contrast_db": depth}


def optimize_measurement_axis(axis: list[float], metric: list[float], *, objective: str = "maximum") -> dict[str, float]:
    x, y = np.asarray(axis), np.asarray(metric)
    if x.shape != y.shape or x.size == 0:
        raise ValueError("Axis and metric must have equal non-zero length")
    index = int(np.argmax(y) if objective == "maximum" else np.argmin(y))
    return {"setting": float(x[index]), "metric": float(y[index])}


def measure_gain(reference_db: list[float], pumped_db: list[float]) -> dict[str, Any]:
    reference, pumped = np.asarray(reference_db), np.asarray(pumped_db)
    if reference.shape != pumped.shape:
        raise ValueError("Gain traces must match")
    gain = pumped - reference
    return {"gain_db": gain.tolist(), "peak_gain_db": float(np.max(gain)), "peak_index": int(np.argmax(gain))}


def extract_bandwidth(frequency_hz: list[float], gain_db: list[float], *, drop_db: float = 3.0) -> dict[str, float]:
    frequency, gain = np.asarray(frequency_hz), np.asarray(gain_db)
    peak = float(np.max(gain))
    passing = np.where(gain >= peak - drop_db)[0]
    if passing.size == 0:
        return {"bandwidth_hz": 0.0, "lower_hz": math.nan, "upper_hz": math.nan}
    lower, upper = float(frequency[passing[0]]), float(frequency[passing[-1]])
    return {"bandwidth_hz": upper - lower, "lower_hz": lower, "upper_hz": upper}


def extract_p1db(input_power_dbm: list[float], gain_db: list[float]) -> dict[str, float]:
    power, gain = np.asarray(input_power_dbm), np.asarray(gain_db)
    small_signal = float(np.median(gain[: max(3, len(gain) // 10)]))
    indices = np.where(gain <= small_signal - 1.0)[0]
    return {"small_signal_gain_db": small_signal, "p1db_dbm": float(power[indices[0]]) if indices.size else math.nan}


def extract_ip3(input_power_dbm: list[float], fundamental_dbm: list[float], im3_dbm: list[float]) -> dict[str, float]:
    power, fundamental, im3 = map(np.asarray, (input_power_dbm, fundamental_dbm, im3_dbm))
    if not (power.shape == fundamental.shape == im3.shape) or power.size < 2:
        raise ValueError("IP3 arrays must match")
    fundamental_fit = np.polyfit(power, fundamental, 1)
    im3_fit = np.polyfit(power, im3, 1)
    intercept_input = (fundamental_fit[1] - im3_fit[1]) / (im3_fit[0] - fundamental_fit[0])
    intercept_output = np.polyval(fundamental_fit, intercept_input)
    return {"iip3_dbm": float(intercept_input), "oip3_dbm": float(intercept_output)}


def y_factor_noise_temperature(*, hot_power_w: float, cold_power_w: float, hot_temperature_k: float, cold_temperature_k: float) -> dict[str, float]:
    if min(hot_power_w, cold_power_w, hot_temperature_k, cold_temperature_k) <= 0.0:
        raise ValueError("Y-factor inputs must be positive")
    y = hot_power_w / cold_power_w
    if y <= 1.0:
        raise ValueError("Hot/cold Y factor must exceed one")
    noise = (hot_temperature_k - y * cold_temperature_k) / (y - 1.0)
    return {"y_factor": y, "noise_temperature_k": noise}


def quantum_efficiency(*, added_noise_photons: float) -> float:
    if added_noise_photons < 0.0:
        raise ValueError("Added noise must be non-negative")
    return 1.0 / (1.0 + 2.0 * added_noise_photons)


def squeezing_analysis(i_samples: list[float], q_samples: list[float], *, vacuum_variance: float = 0.5) -> dict[str, Any]:
    samples = np.column_stack([i_samples, q_samples])
    covariance = np.cov(samples, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    return {"covariance": covariance.tolist(), "principal_variances": eigenvalues.tolist(), "squeezing_db": float(10.0 * math.log10(max(eigenvalues[0] / vacuum_variance, 1e-30))), "angle_deg": float(math.degrees(math.atan2(eigenvectors[1, 0], eigenvectors[0, 0])))}


def iq_histogram(i_samples: list[float], q_samples: list[float], *, bins: int = 64) -> dict[str, Any]:
    histogram, i_edges, q_edges = np.histogram2d(i_samples, q_samples, bins=bins)
    return {"histogram": histogram.astype(int).tolist(), "i_edges": i_edges.tolist(), "q_edges": q_edges.tolist(), "sample_count": len(i_samples)}


def reconstruct_wigner(i_samples: list[float], q_samples: list[float], *, bins: int = 64) -> dict[str, Any]:
    """Return a normalized phase-space quasidistribution proxy from IQ samples."""
    histogram = iq_histogram(i_samples, q_samples, bins=bins)
    density = np.asarray(histogram["histogram"], dtype=float)
    density /= max(float(np.sum(density)), 1.0)
    return {**histogram, "schema": "text-to-gds.wigner-proxy.v1", "quasiprobability": density.tolist(), "model_validity": "Husimi-like histogram proxy; true Wigner tomography requires calibrated displaced-parity measurements."}


def drift_analysis(timestamps_s: list[float], values: list[float]) -> dict[str, float]:
    time, data = np.asarray(timestamps_s), np.asarray(values)
    if time.shape != data.shape or time.size < 2:
        raise ValueError("At least two timestamped values are required")
    slope, intercept = np.polyfit(time - time[0], data, 1)
    residual = data - (slope * (time - time[0]) + intercept)
    return {"drift_per_second": float(slope), "drift_per_hour": float(slope * 3600.0), "rms_residual": float(np.sqrt(np.mean(residual**2))), "peak_to_peak": float(np.ptp(data))}


def long_term_stability(timestamps_s: list[float], values: list[float]) -> dict[str, Any]:
    drift = drift_analysis(timestamps_s, values)
    data = np.asarray(values)
    drift["relative_std_fraction"] = float(np.std(data) / max(abs(np.mean(data)), 1e-30))
    return {"schema": "text-to-gds.long-term-stability.v1", **drift}
