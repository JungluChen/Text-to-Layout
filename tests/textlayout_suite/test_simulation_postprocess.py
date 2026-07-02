"""Synthetic-data tests for the shared waveform/FFT post-processing."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from textlayout.simulation.postprocess import (
    estimate_resonance_ghz,
    parse_waveform_table,
    pump_signal_gain,
    tone_amplitude,
)


def _two_tone(
    duration_s: float,
    dt_s: float,
    tones: list[tuple[float, float]],
    *,
    start_s: float = 0.0,
) -> tuple[list[float], list[float]]:
    time = np.arange(0.0, duration_s, dt_s)
    signal = np.zeros_like(time)
    for amplitude, frequency_hz in tones:
        signal += amplitude * np.sin(2.0 * math.pi * frequency_hz * time)
    signal[time < start_s] = 0.0
    return time.tolist(), signal.tolist()


def test_parse_waveform_table_csv_and_whitespace(tmp_path: Path) -> None:
    csv_file = tmp_path / "wave.csv"
    csv_file.write_text(
        "time,V(OUT)\n" + "".join(f"{i * 1e-12},{i * 0.5}\n" for i in range(10)),
        encoding="ascii",
    )
    parsed = parse_waveform_table(csv_file)
    assert parsed["signals"]["V(OUT)"][2] == 1.0

    dat_file = tmp_path / "wave.dat"
    dat_file.write_text(
        "# comment line is skipped\ntime v(out) i(l1)\n"
        + "".join(f"{i * 1e-12} {i * 2.0} {i * 3.0}\n" for i in range(10)),
        encoding="ascii",
    )
    parsed = parse_waveform_table(dat_file)
    assert list(parsed["signals"]) == ["v(out)", "i(l1)"]
    assert len(parsed["time_s"]) == 10

    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="ascii")
    with pytest.raises(ValueError):
        parse_waveform_table(empty)


def test_synthetic_lc_resonance_extraction() -> None:
    # f0 = 1/(2*pi*sqrt(L*C)) for L = 0.3 nH, C = 0.6 pF is ~11.86 GHz.
    f0_hz = 1.0 / (2.0 * math.pi * math.sqrt(0.3e-9 * 0.6e-12))
    time, signal = _two_tone(30e-9, 1e-12, [(1.0, f0_hz)])
    measured = estimate_resonance_ghz(time, signal)
    assert measured == pytest.approx(f0_hz / 1e9, rel=0.01)


def test_tone_amplitude_reads_exact_bin_amplitude() -> None:
    # 10000 points at 1 ps -> 100 MHz bins; 6 GHz sits exactly on bin 60.
    time, signal = _two_tone(10e-9, 1e-12, [(2.0, 6.0e9), (0.25, 8.0e9)])
    assert tone_amplitude(time, signal, 6.0e9) == pytest.approx(2.0, rel=0.05)
    assert tone_amplitude(time, signal, 8.0e9) == pytest.approx(0.25, rel=0.05)
    with pytest.raises(ValueError):
        tone_amplitude(time, signal, -1.0)


def test_synthetic_fft_gain_extraction_with_idler_and_discard() -> None:
    # Two-tone experiment on synthetic data: fs = 6 GHz, fp = 7 GHz,
    # idler at 2*fp - fs = 8 GHz. The first 10 ns are deliberately zeroed
    # (a fake start-up transient) and excluded via the discard window.
    fs, fp = 6.0e9, 7.0e9
    time, vin = _two_tone(20e-9, 1e-12, [(0.1, fs), (1.0, fp)], start_s=10e-9)
    _, vout = _two_tone(20e-9, 1e-12, [(1.0, fs), (1.0, fp), (0.05, 2 * fp - fs)], start_s=10e-9)
    metrics = pump_signal_gain(
        time,
        vin,
        vout,
        signal_frequency_hz=fs,
        pump_frequency_hz=fp,
        discard_s=10e-9,
    )
    assert metrics is not None
    assert metrics["signal_gain_db"] == pytest.approx(20.0, abs=0.5)
    assert metrics["idler_frequency_hz"] == pytest.approx(8.0e9)
    assert metrics["output_idler_amplitude"] == pytest.approx(0.05, rel=0.15)


def test_gain_extraction_refuses_empty_tones() -> None:
    time = [i * 1e-12 for i in range(1000)]
    silence = [0.0] * 1000
    assert (
        pump_signal_gain(time, silence, silence, signal_frequency_hz=6.0e9, discard_s=0.0) is None
    )
