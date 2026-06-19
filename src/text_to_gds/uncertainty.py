"""Process-aware Monte Carlo uncertainty and fabrication-yield reporting."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from text_to_gds.process_database import FabricationProcess

FLUX_QUANTUM_WB = 2.067833848e-15


def run_process_monte_carlo(
    process_data: dict[str, Any],
    *,
    report_path: str | Path,
    csv_path: str | Path,
    plot_path: str | Path,
    samples: int = 5000,
    seed: int = 42,
    junction_area_um2: float = 0.0484,
    target_frequency_ghz: float = 6.0,
    target_gain_db: float = 20.0,
    capacitance_ff: float = 100.0,
    frequency_tolerance_fraction: float = 0.05,
    minimum_gain_db: float = 19.0,
) -> dict[str, Any]:
    if samples < 100:
        raise ValueError("samples must be at least 100")
    process = FabricationProcess.from_dict(process_data)
    rng = np.random.default_rng(seed)
    jc = rng.normal(process.measured_jc, process.sigma_jc, samples)
    area = junction_area_um2 * rng.normal(1.0, process.lithography_sigma_fraction, samples) ** 2
    capacitance = capacitance_ff * rng.normal(1.0, process.capacitance_sigma_fraction, samples)
    ic_ua = np.maximum(jc * area, 1e-12)
    lj_ph = FLUX_QUANTUM_WB / (2.0 * math.pi * ic_ua * 1e-6) * 1e12
    nominal_ic = process.measured_jc * junction_area_um2
    frequency = target_frequency_ghz * np.sqrt(
        (ic_ua / nominal_ic) * (capacitance_ff / np.maximum(capacitance, 1e-12))
    )
    detuning_fraction = np.abs(frequency - target_frequency_ghz) / target_frequency_ghz
    gain = target_gain_db - 8.0 * (detuning_fraction / frequency_tolerance_fraction) ** 2
    pass_mask = (detuning_fraction <= frequency_tolerance_fraction) & (gain >= minimum_gain_db)

    report_file, csv_file, plot_file = Path(report_path), Path(csv_path), Path(plot_path)
    for path in (report_file, csv_file, plot_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample", "jc_ua_per_um2", "area_um2", "ic_ua", "lj_ph", "capacitance_ff", "frequency_ghz", "gain_db", "pass"])
        for row in zip(range(samples), jc, area, ic_ua, lj_ph, capacitance, frequency, gain, pass_mask):
            writer.writerow(row)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.8), constrained_layout=True)
    axes[0].hist(ic_ua, bins=45, color="#007aff", alpha=0.82)
    axes[0].set(xlabel="Ic (uA)", ylabel="count", title="Critical current")
    axes[1].hist(frequency, bins=45, color="#34c759", alpha=0.82)
    axes[1].set(xlabel="frequency (GHz)", title="Resonant frequency")
    axes[2].hist(gain, bins=45, color="#af52de", alpha=0.82)
    axes[2].set(xlabel="gain (dB)", title="Small-signal gain")
    fig.suptitle(f"Process yield: {100.0 * np.mean(pass_mask):.1f}%")
    fig.savefig(plot_file, dpi=200)
    plt.close(fig)

    def summary(values: np.ndarray) -> dict[str, float]:
        return {
            "mean": float(np.mean(values)),
            "standard_deviation": float(np.std(values, ddof=1)),
            "p2p5": float(np.percentile(values, 2.5)),
            "p97p5": float(np.percentile(values, 97.5)),
        }

    result = {
        "schema": "text-to-gds.uncertainty-report.v1",
        "samples": samples,
        "seed": seed,
        "process_id": process.process_id,
        "yield_fraction": float(np.mean(pass_mask)),
        "yield_percent": float(100.0 * np.mean(pass_mask)),
        "critical_current_ua": summary(ic_ua),
        "resonant_frequency_ghz": summary(frequency),
        "gain_db": summary(gain),
        "acceptance": {
            "frequency_tolerance_fraction": frequency_tolerance_fraction,
            "minimum_gain_db": minimum_gain_db,
        },
        "artifacts": {"report_path": str(report_file), "csv_path": str(csv_file), "plot_path": str(plot_file)},
        "validity": "Monte Carlo propagation through a reduced LC/gain model; external nonlinear simulation is required for signoff.",
    }
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
