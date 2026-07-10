"""Seeded Monte Carlo propagation of JJ process variation into frequency yield.

Sampling model (documented, deterministic under a seed):

- One *chip-common* Jc factor per sample: ``N(1, wafer_sigma)`` — wafer drift
  moves every junction on a chip together.
- One *local* Jc factor per junction: ``N(1, local_sigma)``.
- Lithography CD: each linear dimension gets an independent ``N(0, cd_sigma)``
  additive draw (nm), plus the systematic area bias.
- Optional linear spatial gradient for array analysis (qubit index spaced
  1 mm apart as a synthetic placement; real placements can be supplied later).

Frequency propagation uses the exact LC relation ``f = 1/(2π√(L·C))`` with
``L = LJ(Ic)``; the transmon ``f01`` estimate is also reported per-sample mean
for context but the acceptance window is evaluated on the LC frequency, as
specified. Everything is reproducible: same seed → identical output.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from textlayout.yield_model.models import (
    FrequencyTarget,
    JJProcessModel,
    JunctionGeometry,
    WorstCaseCorner,
    YieldResult,
    YieldStatistics,
)
from textlayout.yield_model.physics import ic_ua, lc_resonance_ghz, lj_nh

#: Matches the convention in textlayout.simulation.postprocess.
FloatArray = npt.NDArray[np.float64]


def _wilson_ci95(successes: int, n: int) -> tuple[float, float]:
    """Wilson score 95% interval for a binomial proportion, in percent."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    # center - half is exactly 0 at phat=0 (and center + half exactly 1 at phat=1)
    # up to floating-point cancellation noise; clamp that noise away.
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return (lower * 100.0 if lower > 1e-12 else 0.0, upper * 100.0 if upper < 1 - 1e-12 else 100.0)


def _sampled_area_um2(
    junction: JunctionGeometry,
    process: JJProcessModel,
    rng: np.random.Generator,
) -> float:
    dw_um = float(rng.normal(0.0, process.cd_sigma_nm)) * 1e-3
    dh_um = float(rng.normal(0.0, process.cd_sigma_nm)) * 1e-3
    width = max(junction.width_um + dw_um, 1e-6)
    height = max(junction.height_um + dh_um, 1e-6)
    return max(width * height + process.junction_area_bias_um2, 1e-9)


def _sampled_jc(
    process: JJProcessModel,
    chip_factor: float,
    rng: np.random.Generator,
    position_mm: float = 0.0,
) -> float:
    local = float(rng.normal(1.0, process.local_jc_sigma_pct / 100.0))
    gradient = 1.0 + process.spatial_gradient_pct_per_mm / 100.0 * position_mm
    return max(process.jc_mean * chip_factor * local * gradient, 1e-9)


def _statistics(frequencies_ghz: FloatArray) -> YieldStatistics:
    return YieldStatistics(
        n_samples=int(frequencies_ghz.size),
        mean_ghz=float(np.mean(frequencies_ghz)),
        sigma_mhz=float(np.std(frequencies_ghz) * 1e3),
        p05_ghz=float(np.percentile(frequencies_ghz, 5)),
        p50_ghz=float(np.percentile(frequencies_ghz, 50)),
        p95_ghz=float(np.percentile(frequencies_ghz, 95)),
        min_ghz=float(np.min(frequencies_ghz)),
        max_ghz=float(np.max(frequencies_ghz)),
    )


_ASSUMPTIONS = [
    "Chip-common Jc factor N(1, wafer_sigma) shared by all junctions per sample.",
    "Independent local Jc factor N(1, local_sigma) per junction.",
    "CD variation: additive N(0, cd_sigma_nm) per linear dimension + area bias.",
    "Acceptance evaluated on f = 1/(2*pi*sqrt(LJ*C)) with LJ = Phi0/(2*pi*Ic).",
    "Gaussian statistics; no fat tails, no correlated defects, no aging.",
]


def run_jj_yield(
    *,
    process: JJProcessModel,
    junction: JunctionGeometry,
    shunt_c_pf: float,
    target: FrequencyTarget,
    n_samples: int = 5000,
    seed: int = 1234,
) -> YieldResult:
    """Monte Carlo yield for a single junction + shunt capacitance mode."""
    if shunt_c_pf <= 0:
        raise ValueError(f"shunt capacitance must be positive, got {shunt_c_pf} pF")
    if n_samples < 100:
        raise ValueError("need at least 100 samples for a meaningful yield estimate")
    rng = np.random.default_rng(seed)

    frequencies = np.empty(n_samples)
    draws: list[tuple[float, float, float, float]] = []  # jc, area, ic, lj
    for index in range(n_samples):
        chip_factor = float(rng.normal(1.0, process.wafer_jc_sigma_pct / 100.0))
        chip_factor = max(chip_factor, 1e-3)
        jc = _sampled_jc(process, chip_factor, rng)
        area = _sampled_area_um2(junction, process, rng)
        ic = ic_ua(jc, area)
        lj = lj_nh(ic)
        frequencies[index] = lc_resonance_ghz(lj, shunt_c_pf)
        draws.append((jc, area, ic, lj))

    half_window_ghz = target.tolerance_mhz / 1e3
    in_window = np.abs(frequencies - target.target_ghz) <= half_window_ghz
    hits = int(np.count_nonzero(in_window))

    lowest, highest = int(np.argmin(frequencies)), int(np.argmax(frequencies))
    corners = [
        WorstCaseCorner(
            label=label,
            frequency_ghz=float(frequencies[idx]),
            jc_ua_per_um2=draws[idx][0],
            area_um2=draws[idx][1],
            ic_ua=draws[idx][2],
            lj_nh=draws[idx][3],
        )
        for label, idx in (("min_frequency", lowest), ("max_frequency", highest))
    ]

    return YieldResult(
        analysis="jj",
        process=process,
        target=target,
        statistics=_statistics(frequencies),
        hit_rate=hits / n_samples,
        yield_pct=hits / n_samples * 100.0,
        yield_ci95_pct=_wilson_ci95(hits, n_samples),
        worst_corners=corners,
        seed=seed,
        assumptions=list(_ASSUMPTIONS),
        provenance={
            "engine": "textlayout.yield_model.monte_carlo",
            "sampling": "numpy.random.default_rng",
            "process_calibration": process.calibration,
        },
        synthetic=process.calibration != "measured_on_process",
    )


def run_qubit_array_yield(
    *,
    process: JJProcessModel,
    junction: JunctionGeometry,
    shunt_c_pf: float,
    target: FrequencyTarget,
    n_qubits: int,
    n_chips: int = 2000,
    qubit_pitch_mm: float = 1.0,
    seed: int = 1234,
) -> YieldResult:
    """Chip yield: probability that ALL ``n_qubits`` land inside the window.

    Each simulated chip shares one wafer-common Jc factor; each qubit adds its
    local Jc, CD, and spatial-gradient draw (qubits placed ``qubit_pitch_mm``
    apart along the gradient axis as a synthetic placement).
    """
    if n_qubits < 1:
        raise ValueError("n_qubits must be >= 1")
    if n_chips < 100:
        raise ValueError("need at least 100 chips for a meaningful yield estimate")
    rng = np.random.default_rng(seed)
    half_window_ghz = target.tolerance_mhz / 1e3

    all_frequencies: list[float] = []
    all_draws: list[tuple[float, float, float, float]] = []  # jc, area, ic, lj
    chips_passing = 0
    for _ in range(n_chips):
        chip_factor = max(float(rng.normal(1.0, process.wafer_jc_sigma_pct / 100.0)), 1e-3)
        chip_ok = True
        for qubit_index in range(n_qubits):
            jc = _sampled_jc(process, chip_factor, rng, position_mm=qubit_index * qubit_pitch_mm)
            area = _sampled_area_um2(junction, process, rng)
            ic = ic_ua(jc, area)
            lj = lj_nh(ic)
            frequency = lc_resonance_ghz(lj, shunt_c_pf)
            all_frequencies.append(frequency)
            all_draws.append((jc, area, ic, lj))
            if abs(frequency - target.target_ghz) > half_window_ghz:
                chip_ok = False
        if chip_ok:
            chips_passing += 1

    frequencies = np.asarray(all_frequencies)
    in_window = np.abs(frequencies - target.target_ghz) <= half_window_ghz
    hits = int(np.count_nonzero(in_window))
    lowest, highest = int(np.argmin(frequencies)), int(np.argmax(frequencies))
    corners = [
        WorstCaseCorner(
            label=label,
            frequency_ghz=float(frequencies[idx]),
            jc_ua_per_um2=all_draws[idx][0],
            area_um2=all_draws[idx][1],
            ic_ua=all_draws[idx][2],
            lj_nh=all_draws[idx][3],
        )
        for label, idx in (("min_frequency", lowest), ("max_frequency", highest))
    ]

    return YieldResult(
        analysis="qubit_array",
        process=process,
        target=target,
        statistics=_statistics(frequencies),
        hit_rate=hits / int(frequencies.size),
        yield_pct=hits / int(frequencies.size) * 100.0,
        yield_ci95_pct=_wilson_ci95(hits, int(frequencies.size)),
        worst_corners=corners,
        seed=seed,
        n_qubits_per_chip=n_qubits,
        chip_yield_pct=chips_passing / n_chips * 100.0,
        chip_yield_ci95_pct=_wilson_ci95(chips_passing, n_chips),
        assumptions=list(_ASSUMPTIONS)
        + [
            f"Chip passes only when all {n_qubits} qubits are inside the window.",
            f"Synthetic linear placement, {qubit_pitch_mm} mm pitch along the gradient.",
            "Worst-case corners report the single qubit draw with the most extreme "
            "frequency across all simulated chips, not a whole-chip corner.",
        ],
        provenance={
            "engine": "textlayout.yield_model.monte_carlo",
            "sampling": "numpy.random.default_rng",
            "process_calibration": process.calibration,
        },
        synthetic=process.calibration != "measured_on_process",
    )
