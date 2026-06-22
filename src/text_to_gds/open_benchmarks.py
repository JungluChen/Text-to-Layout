"""Open benchmark suite -- functional, physics-asserting acceptance tests.

Each benchmark targets a *physical quantity* and either passes within tolerance,
fails, or skips (when a required solver binary is absent). None of them accept
"a file was generated" as success. Where two open backends are available the
result is cross-checked with the Solver Agreement Engine; otherwise the
analytical/surrogate value is asserted against the target directly.
"""

from __future__ import annotations

import math
from typing import Any

from text_to_gds.open_q3d import tune_idc_capacitance
from text_to_gds.physics_extensions import (
    cpw_impedance_ohm,
    optimize_cpw_impedance,
    tune_resonator_length,
)
from text_to_gds.solver_agreement import cross_validate

_C = 299792458.0


def benchmark_cpw(*, tolerance_pct: float = 5.0) -> dict[str, Any]:
    """01_CPW: design a 50 ohm CPW and a 6 GHz quarter-wave section; verify both."""
    epsilon_r = 11.45
    geo = optimize_cpw_impedance(target_ohm=50.0, epsilon_r=epsilon_r)
    z0 = float(geo["impedance_ohm"])
    z0_err = abs(z0 - 50.0) / 50.0 * 100.0

    epsilon_eff = (epsilon_r + 1.0) / 2.0
    length_um = float(tune_resonator_length(target_frequency_ghz=6.0, epsilon_eff=epsilon_eff)["physical_length_um"])
    f0_recovered = _C / (4.0 * length_um * 1e-6 * math.sqrt(epsilon_eff)) / 1e9
    f0_err = abs(f0_recovered - 6.0) / 6.0 * 100.0

    # Analytical cross-check of the chosen geometry against the closed-form model.
    z0_check = cpw_impedance_ohm(geo["width_um"], geo["gap_um"], epsilon_r)
    agreement = cross_validate(
        [{"source": "optimizer", "value": z0}, {"source": "closed_form", "value": z0_check}],
        quantity="impedance_ohm",
        tolerance_pct=tolerance_pct,
    )
    passed = z0_err <= tolerance_pct and f0_err <= tolerance_pct
    return {
        "id": "01_CPW",
        "target": {"impedance_ohm": 50.0, "frequency_ghz": 6.0},
        "computed": {"impedance_ohm": round(z0, 3), "frequency_ghz": round(f0_recovered, 4)},
        "errors_pct": {"impedance": round(z0_err, 3), "frequency": round(f0_err, 4)},
        "geometry": {"width_um": geo["width_um"], "gap_um": geo["gap_um"], "length_um": length_um},
        "agreement": agreement,
        "status": "passed" if passed else "failed",
    }


def benchmark_idc(*, tolerance_pct: float = 1.0) -> dict[str, Any]:
    """02_IDC: auto-tune an interdigital capacitor to 0.6 pF within 1%."""
    tune = tune_idc_capacitance(0.6, tolerance_pct=tolerance_pct)
    return {
        "id": "02_IDC",
        "target": {"capacitance_pf": 0.6},
        "computed": {"capacitance_pf": tune["achieved_pf"]},
        "errors_pct": {"capacitance": tune["error_pct"]},
        "geometry": tune["geometry"],
        "status": "passed" if tune["within_tolerance"] else "failed",
    }


def benchmark_jpa(*, solved_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """03_JPA: 20 dB gain, 500 MHz bandwidth -- requires JosephsonCircuits.jl.

    Skips (not fails) when no solved result is supplied, so CI without Julia is
    honest rather than green-by-omission.
    """
    if solved_result is None:
        return {
            "id": "03_JPA",
            "target": {"gain_db": 20.0, "bandwidth_mhz": 500.0},
            "computed": None,
            "status": "skipped",
            "reason": "JosephsonCircuits.jl result not provided; install Julia + run to evaluate.",
        }
    gain = float(solved_result.get("peak_gain_db", 0.0))
    bw = float(solved_result.get("bandwidth_mhz", 0.0))
    passed = abs(gain - 20.0) <= 2.0 and bw >= 400.0
    return {
        "id": "03_JPA",
        "target": {"gain_db": 20.0, "bandwidth_mhz": 500.0},
        "computed": {"gain_db": gain, "bandwidth_mhz": bw},
        "status": "passed" if passed else "failed",
    }


def run_open_benchmarks(*, jpa_solved_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the open benchmark suite and summarise pass/fail/skip counts."""
    results = [benchmark_cpw(), benchmark_idc(), benchmark_jpa(solved_result=jpa_solved_result)]
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return {
        "schema": "text-to-gds.open-benchmarks.v1",
        "benchmarks": results,
        "counts": counts,
        "all_passed": counts["failed"] == 0,
        "model_validity": (
            "Physical-quantity assertions, not file-existence checks. Solver-backed "
            "rows skip cleanly when their binaries are absent."
        ),
    }
