"""Theory/simulation/measurement comparison artifacts for JPA review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from textlayout._legacy.theory.kerr_jpa import gain_bandwidth_product, kerr_jpa_gain
from textlayout._legacy.theory.quantum_noise import quantum_limited_noise_temperature


def write_analytical_verification(
    *,
    report_path: str | Path,
    plot_path: str | Path,
    center_frequency_ghz: float = 6.0,
    kappa_mhz: float = 120.0,
    pump_coupling_mhz: float = 55.0,
    simulation: dict[str, Any] | None = None,
    measurement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detuning_mhz = np.linspace(-300.0, 300.0, 1201)
    gain_power = kerr_jpa_gain(
        detuning_mhz * 1e6,
        kappa_hz=kappa_mhz * 1e6,
        pump_coupling_hz=pump_coupling_mhz * 1e6,
    )
    gain_db = 10.0 * np.log10(gain_power)
    peak = float(np.max(gain_db))
    mask = gain_db >= peak - 3.0
    bandwidth_mhz = float(detuning_mhz[mask][-1] - detuning_mhz[mask][0])
    gbp_mhz = gain_bandwidth_product(10.0 ** (peak / 10.0), bandwidth_mhz)
    quantum_limit_k = quantum_limited_noise_temperature(center_frequency_ghz * 1e9)

    comparisons = []
    theory_metrics = {
        "center_frequency_ghz": center_frequency_ghz,
        "peak_gain_db": peak,
        "bandwidth_3db_mhz": bandwidth_mhz,
        "sqrt_gain_bandwidth_mhz": gbp_mhz,
        "quantum_limited_noise_temperature_k": quantum_limit_k,
    }
    for source, payload in (("simulation", simulation), ("measurement", measurement)):
        if payload is None:
            continue
        metrics = payload.get("physical_performance", payload.get("metrics", payload))
        comparisons.append(
            {
                "source": source,
                "peak_gain_db": metrics.get("estimated_peak_gain_db", metrics.get("peak_gain_db")),
                "bandwidth_3db_mhz": metrics.get("bandwidth_3db_mhz"),
                "noise_temperature_k": metrics.get("noise_temperature_k"),
            }
        )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_file, report_file = Path(plot_path), Path(report_path)
    plot_file.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    ax.plot(center_frequency_ghz + detuning_mhz / 1000.0, gain_db, label="analytical Kerr JPA")
    ax.axhline(peak - 3.0, color="black", linestyle="--", linewidth=0.8, label="-3 dB")
    ax.set(xlabel="frequency (GHz)", ylabel="gain (dB)", title="JPA analytical verification")
    ax.legend()
    fig.savefig(plot_file, dpi=200)
    plt.close(fig)
    result = {
        "schema": "text-to-gds.analytical-verification.v1",
        "theory": theory_metrics,
        "comparisons": comparisons,
        "artifacts": {"report_path": str(report_file), "plot_path": str(plot_file)},
        "validity": "Small-signal analytical model; compare against executed simulation and calibrated measurement before signoff.",
    }
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
