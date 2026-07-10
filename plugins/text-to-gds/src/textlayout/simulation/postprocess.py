"""Simulator-agnostic waveform parsing and FFT post-processing.

Every circuit backend (JoSIM, PSCAN2, WRspice) funnels its raw transient
output through these functions so the resonance and gain math is written —
and tested — exactly once. Nothing here talks to a subprocess; the inputs are
plain time/value arrays, which is also what makes the synthetic-data tests
meaningful.

The gain extraction implements the two-tone recipe described in
``docs/references/jtwpa_numerical_simulations_review.md`` (clean-room, after
Levochkina et al., arXiv:2402.12037): discard the initial propagation
transient, FFT input and output records with a Hann window, read the
amplitude at the signal frequency, and optionally at the idler.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TypedDict

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


class Waveform(TypedDict):
    """Uniform in-memory transient record: one time base, named signals."""

    time_s: list[float]
    signals: dict[str, list[float]]


def parse_waveform_table(path: str | Path) -> Waveform:
    """Parse comma- or whitespace-delimited tabular transient output.

    Handles the CSV/DAT shapes produced by JoSIM (``time,V(OUT),...``) and by
    the generated PSCAN2/WRspice runners. The first column is always time.
    """
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("empty transient output")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(("*", "#"))
    ]
    delimiter = "," if "," in lines[0] else None
    headers = [
        item.strip() for item in (lines[0].split(delimiter) if delimiter else lines[0].split())
    ]
    if len(headers) < 2:
        raise ValueError("transient output needs time and at least one signal")
    columns: list[list[float]] = [[] for _ in headers]
    for line in lines[1:]:
        tokens = [item.strip() for item in (line.split(delimiter) if delimiter else line.split())]
        if len(tokens) != len(headers):
            continue
        try:
            values = [float(token) for token in tokens]
        except ValueError:
            continue
        for column, value in zip(columns, values, strict=True):
            column.append(value)
    if len(columns[0]) < 4:
        raise ValueError("fewer than four numeric transient samples")
    return {"time_s": columns[0], "signals": dict(zip(headers[1:], columns[1:], strict=True))}


def _uniform_dt(time_s: list[float]) -> float | None:
    if len(time_s) < 8:
        return None
    dt = float(np.median(np.diff(np.asarray(time_s, dtype=np.float64))))
    if not math.isfinite(dt) or dt <= 0:
        return None
    return dt


def amplitude_spectrum(
    time_s: list[float], signal: list[float], *, discard_s: float = 0.0
) -> tuple[FloatArray, FloatArray] | None:
    """Hann-windowed single-sided amplitude spectrum after a discard window.

    Returns ``(frequencies_hz, amplitudes)`` scaled so a pure sine of
    amplitude ``A`` reads back as ``A`` at its bin, or ``None`` when the
    record is too short or non-uniform.
    """
    if len(time_s) != len(signal):
        return None
    times = np.asarray(time_s, dtype=np.float64)
    values = np.asarray(signal, dtype=np.float64)
    if discard_s > 0.0:
        keep = times >= (times[0] + discard_s)
        times, values = times[keep], values[keep]
    dt = _uniform_dt(times.tolist())
    if dt is None:
        return None
    values = values - float(np.mean(values))
    window = np.hanning(len(values))
    spectrum = np.abs(np.fft.rfft(values * window))
    # Hann coherent gain is 0.5; 2/N restores single-sided sine amplitude.
    amplitudes = spectrum * (2.0 / (len(values) * 0.5))
    frequencies = np.fft.rfftfreq(len(values), dt)
    return frequencies.astype(np.float64), amplitudes.astype(np.float64)


def estimate_resonance_ghz(time_s: list[float], signal: list[float]) -> float | None:
    """Estimate the dominant non-DC transient frequency by an FFT."""
    result = amplitude_spectrum(time_s, signal)
    if result is None:
        return None
    frequencies, amplitudes = result
    if len(amplitudes) <= 1 or not np.any(amplitudes[1:] > 0):
        return None
    index = int(np.argmax(amplitudes[1:]) + 1)
    return float(frequencies[index] / 1e9)


def tone_amplitude(
    time_s: list[float],
    signal: list[float],
    frequency_hz: float,
    *,
    discard_s: float = 0.0,
) -> float | None:
    """Amplitude at (the bin nearest to) one tone, after the discard window."""
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    result = amplitude_spectrum(time_s, signal, discard_s=discard_s)
    if result is None:
        return None
    frequencies, amplitudes = result
    index = int(np.argmin(np.abs(frequencies - frequency_hz)))
    # Allow ±1 bin of leakage around the nearest bin.
    low, high = max(index - 1, 0), min(index + 2, len(amplitudes))
    return float(np.max(amplitudes[low:high]))


def pump_signal_gain(
    time_s: list[float],
    input_signal: list[float],
    output_signal: list[float],
    *,
    signal_frequency_hz: float,
    pump_frequency_hz: float | None = None,
    discard_s: float = 0.0,
) -> dict[str, float] | None:
    """FFT-based signal gain (and optional idler amplitude) for a two-tone run.

    Gain is ``20*log10(A_out/A_in)`` at the signal tone. When the pump
    frequency is given, the four-wave-mixing idler ``f_i = 2*f_p - f_s`` is
    also reported. This is measurement math only — whether the underlying data
    came from a real simulator run is decided (and labelled) by the caller.
    """
    a_in = tone_amplitude(time_s, input_signal, signal_frequency_hz, discard_s=discard_s)
    a_out = tone_amplitude(time_s, output_signal, signal_frequency_hz, discard_s=discard_s)
    if a_in is None or a_out is None or a_in <= 0.0 or a_out <= 0.0:
        return None
    metrics: dict[str, float] = {
        "signal_frequency_hz": signal_frequency_hz,
        "input_signal_amplitude": a_in,
        "output_signal_amplitude": a_out,
        "signal_gain_db": 20.0 * math.log10(a_out / a_in),
    }
    if pump_frequency_hz is not None and pump_frequency_hz > 0:
        idler_hz = 2.0 * pump_frequency_hz - signal_frequency_hz
        if idler_hz > 0:
            idler = tone_amplitude(time_s, output_signal, idler_hz, discard_s=discard_s)
            metrics["idler_frequency_hz"] = idler_hz
            if idler is not None:
                metrics["output_idler_amplitude"] = idler
    return metrics
