"""Analytical field reference and geometry-unit tests; no solver execution."""

from __future__ import annotations

import math

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


def test_parallel_plate_analytical_reference_and_qui_units() -> None:
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

    assert c_expected > 0.0


def test_22_finger_idc_analytical_formula() -> None:
    # 22 fingers = 11 pairs, overlap = 200 um, substrate = silicon (eps_r = 11.7)
    finger_pairs = 11
    overlap_um = 200.0
    eps_r = 11.7
    c_bahl = idc_capacitance_pf(finger_pairs, overlap_um, eps_r)
    assert c_bahl > 0.0

# ------------------------------------------------------------------ FastHenry2 analytical references


def test_single_turn_planar_loop_analytical_formula() -> None:
    inner_w, inner_h, trace_w, thick = 96.0, 96.0, 4.0, 0.2
    l_analytical_ph = rectangular_loop_inductance_ph(inner_w, inner_h, trace_w, thick)
    assert l_analytical_ph > 0.0
    # Expected inductance for ~100 um loop is ~250-350 pH
    assert 200.0 < l_analytical_ph < 450.0

def test_4_turn_square_spiral_analytical_formula() -> None:
    turns = 4
    outer_um = 150.0
    inner_um = 30.0
    # Mohan modified Wheeler formula
    l_mohan_nh = spiral_inductance_nh(turns, outer_um, inner_um)
    assert l_mohan_nh > 0.0
    # 4-turn 150 um spiral has inductance ~1.5 nH
    assert 1.0 < l_mohan_nh < 5.0
