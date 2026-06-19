from __future__ import annotations

import numpy as np

from text_to_gds.fitting import (
    fit_jpa_gain,
    fit_resonator,
    load_measurement_trace,
    measurement_from_fit,
    write_measurement_fit,
)


def _notch_trace(f0=6.0, qi=20000.0, qc=10000.0):
    ql = 1.0 / (1.0 / qi + 1.0 / qc)
    s21_min = ql / qi
    freq = np.linspace(f0 - 0.005, f0 + 0.005, 1201)
    x = 2.0 * ql * (freq - f0) / f0
    power = 1.0 - (1.0 - s21_min**2) / (1.0 + x**2)
    return freq, np.sqrt(power)


def test_fit_resonator_recovers_f0_and_quality_factors():
    freq, mag = _notch_trace(f0=6.0, qi=20000.0, qc=10000.0)
    fit = fit_resonator(freq, mag)
    assert fit["f0_ghz"] == np.float64(fit["f0_ghz"])
    assert abs(fit["f0_ghz"] - 6.0) < 1e-3
    assert 0.9 < fit["internal_q"] / 20000.0 < 1.1
    assert 0.9 < fit["coupling_q"] / 10000.0 < 1.1
    assert fit["loaded_q"] < fit["internal_q"]


def test_fit_jpa_gain_recovers_peak_and_bandwidth():
    f0, g0, hwhm = 6.0, 20.0, 0.05013
    freq = np.linspace(f0 - 0.3, f0 + 0.3, 601)
    gain = g0 - 10.0 * np.log10(1.0 + ((freq - f0) / hwhm) ** 2)
    fit = fit_jpa_gain(freq, gain)
    assert abs(fit["peak_gain_db"] - 20.0) < 0.5
    assert abs(fit["center_frequency_ghz"] - 6.0) < 1e-2
    assert 90.0 < fit["bandwidth_3db_mhz"] < 110.0
    assert fit["gain_bandwidth_product_mhz"] > 0.0


def test_write_measurement_fit_from_csv_and_record(tmp_path):
    freq, mag = _notch_trace()
    csv_path = tmp_path / "s21.csv"
    lines = ["frequency_ghz,s21_db"]
    lines += [f"{f:.9f},{20.0 * np.log10(m):.9f}" for f, m in zip(freq, mag, strict=True)]
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    trace = load_measurement_trace(csv_path)
    assert "s21_mag" in trace and "frequency_ghz" in trace

    result = write_measurement_fit(
        csv_path,
        report_path=tmp_path / "s21.fit.json",
        plot_path=tmp_path / "s21.fit.png",
    )
    assert result["fit"]["fit_kind"] == "resonator"
    assert (tmp_path / "s21.fit.json").exists()
    assert (tmp_path / "s21.fit.png").exists()

    measurement = measurement_from_fit(result["fit"])
    assert abs(measurement["center_frequency_ghz"] - 6.0) < 1e-3
