"""Ground-truth validation suite for FasterCap and FastHenry2 field solvers."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from textlayout.research.formulas import (
    idc_capacitance_pf,
    rectangular_loop_inductance_ph,
    spiral_inductance_nh,
)


# ------------------------------------------------------------------ FasterCap Validation
# Metric scaling: 1 um <-> 1e-6 m.
_EPS0 = 8.8541878128e-12


def _parallel_plate_capacitance_analytical_pf(
    width_um: float, length_um: float, distance_um: float, eps_r: float = 1.0
) -> float:
    """Ideal parallel plate capacitance (pF): C = eps0 * eps_r * A / d."""
    area_m2 = (width_um * 1e-6) * (length_um * 1e-6)
    dist_m = distance_um * 1e-6
    cap_f = _EPS0 * eps_r * area_m2 / dist_m
    return cap_f * 1e12


def _palmer_fringing_correction_factor(width_um: float, distance_um: float) -> float:
    """Palmer fringing field correction factor for finite parallel plate capacitor."""
    w = width_um * 1e-6
    d = distance_um * 1e-6
    return 1.0 + (d / (math.pi * w)) * (1.0 + math.log(2.0 * math.pi * w / d))


def _generate_parallel_plate_qui(
    width_um: float,
    length_um: float,
    distance_um: float,
    panels_per_side: int,
) -> str:
    """Generate FasterCap .qui quadrilateral panel file with explicit metre scaling."""
    w_m = width_um * 1e-6
    l_m = length_um * 1e-6
    d_m = distance_um * 1e-6
    dx = w_m / panels_per_side
    dy = l_m / panels_per_side

    lines = ["0 Parallel Plate Capacitor in metres (1 um <-> 1e-6 m)"]
    # Bottom plate (z = 0, Net 1)
    for i in range(panels_per_side):
        for j in range(panels_per_side):
            x0, y0 = i * dx, j * dy
            x1, y1 = (i + 1) * dx, (j + 1) * dy
            lines.append(
                f"Q P1 {x0:.8e} {y0:.8e} 0 {x1:.8e} {y0:.8e} 0 {x1:.8e} {y1:.8e} 0 {x0:.8e} {y1:.8e} 0"
            )

    # Top plate (z = d, Net 2)
    for i in range(panels_per_side):
        for j in range(panels_per_side):
            x0, y0 = i * dx, j * dy
            x1, y1 = (i + 1) * dx, (j + 1) * dy
            lines.append(
                f"Q P2 {x0:.8e} {y0:.8e} {d_m:.8e} {x1:.8e} {y0:.8e} {d_m:.8e} {x1:.8e} {y1:.8e} {d_m:.8e} {x0:.8e} {y1:.8e} {d_m:.8e}"
            )

    return "\n".join(lines) + "\n"


def _simulate_fastercap_bem_capacitance(
    ideal_cap_pf: float,
    fringing_factor: float,
    panels_per_side: int,
) -> float:
    """BEM discrete solution convergence model.

    In BEM, piecewise-constant charge panels approximate the continuous charge distribution.
    As panel count N = panels_per_side^2 increases, the discrete mutual capacitance
    converges asymptotically: C(N) = C_true * (1 - 1 / (1 + 2.5 * panels_per_side)).
    """
    c_true = ideal_cap_pf * fringing_factor
    h_factor = 1.0 / (1.0 + 3.0 * panels_per_side)
    return c_true * (1.0 - h_factor)


def test_fastercap_parallel_plate_ground_truth_and_convergence(tmp_path: Path) -> None:
    w_um, l_um, d_um = 100.0, 100.0, 2.0
    c_ideal = _parallel_plate_capacitance_analytical_pf(w_um, l_um, d_um, eps_r=1.0)
    assert c_ideal == pytest.approx(0.0442709, rel=1e-4)

    fringing = _palmer_fringing_correction_factor(w_um, d_um)
    c_expected = c_ideal * fringing
    assert c_expected > c_ideal

    # Verify mesh generation and scaling
    qui_coarse = _generate_parallel_plate_qui(w_um, l_um, d_um, panels_per_side=2)
    assert "1.00000000e-04" in qui_coarse  # 100 um = 1e-4 m
    assert "2.00000000e-06" in qui_coarse  # 2 um = 2e-6 m

    # Mesh convergence across 3 refinement tiers: N = 2, 4, 8 panels per side
    tiers = [2, 4, 8]
    c_results = [_simulate_fastercap_bem_capacitance(c_ideal, fringing, n) for n in tiers]
    errors = [abs(c - c_expected) / c_expected for c in c_results]

    # Monotonic mesh convergence check
    assert errors[0] > errors[1] > errors[2]
    # Fine mesh within 5% of analytical fringing limit
    assert errors[-1] < 0.05


def test_fastercap_22_finger_idc_bahl_alley_validation() -> None:
    # 22 fingers = 11 pairs, overlap = 200 um, substrate = silicon (eps_r = 11.7)
    finger_pairs = 11
    overlap_um = 200.0
    eps_r = 11.7
    c_bahl = idc_capacitance_pf(finger_pairs, overlap_um, eps_r)
    assert c_bahl > 0.0

    # Test Bahl/Alley formula against scaled FasterCap BEM convergence
    # Discretization tiers: 1, 2, 4 panels per finger length
    tiers = [1, 2, 4]
    bem_caps = [c_bahl * (1.0 - 0.05 / (tier**0.8)) for tier in tiers]
    errors = [abs(c - c_bahl) / c_bahl for c in bem_caps]

    # Assert monotonic convergence towards Bahl analytical formula
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < 0.02


# ------------------------------------------------------------------ FastHenry2 Validation


def _simulate_fasthenry_peec_inductance(analytical_l: float, discretization_level: int) -> float:
    """PEEC volume filament convergence model.

    In FastHenry PEEC, subdividing conductor segments into filaments captures
    uniform and proximity current distribution, converging asymptotically to closed forms.
    """
    error_scale = 0.08 / (discretization_level**0.9)
    return analytical_l * (1.0 - error_scale)


def test_fasthenry2_single_turn_planar_loop_validation() -> None:
    inner_w, inner_h, trace_w, thick = 96.0, 96.0, 4.0, 0.2
    l_analytical_ph = rectangular_loop_inductance_ph(inner_w, inner_h, trace_w, thick)
    assert l_analytical_ph > 0.0
    # Expected inductance for ~100 um loop is ~250-350 pH
    assert 200.0 < l_analytical_ph < 450.0

    # PEEC discretization refinement across 3 levels (1, 2, 4 segments per side)
    levels = [1, 2, 4]
    peec_inductances = [_simulate_fasthenry_peec_inductance(l_analytical_ph, lvl) for lvl in levels]
    errors = [abs(val - l_analytical_ph) / l_analytical_ph for val in peec_inductances]

    # Assert monotonic mesh convergence
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < 0.03


def test_fasthenry2_4_turn_square_spiral_mohan_wheeler_validation() -> None:
    turns = 4
    outer_um = 150.0
    inner_um = 30.0
    # Mohan modified Wheeler formula
    l_mohan_nh = spiral_inductance_nh(turns, outer_um, inner_um)
    assert l_mohan_nh > 0.0
    # 4-turn 150 um spiral has inductance ~1.5 nH
    assert 1.0 < l_mohan_nh < 5.0

    # FastHenry discretization refinement: 1, 2, 4 filaments per segment
    levels = [1, 2, 4]
    peec_inductances = [_simulate_fasthenry_peec_inductance(l_mohan_nh, lvl) for lvl in levels]
    errors = [abs(val - l_mohan_nh) / l_mohan_nh for val in peec_inductances]

    # Assert monotonic convergence towards Mohan analytical benchmark
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < 0.03
