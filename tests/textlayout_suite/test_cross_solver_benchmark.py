"""Unit tests for the independent cross-solver EM baseline verification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from benchmarks.cross_validation import (  # noqa: E402
    CPWBenchmarkGeometry,
    compute_analytical_ghione_naldi,
    compute_fastercap_bem_capacitance,
    compute_high_frequency_cross_validation,
    run_cpw_cross_validation_benchmark,
)


def test_cross_solver_fastercap_bem_vs_ghione_naldi() -> None:
    geom = CPWBenchmarkGeometry()
    analytical = compute_analytical_ghione_naldi(geom)
    fastercap = compute_fastercap_bem_capacitance(geom, mesh_refinement_level=3)

    # Assert error <= 1.0% requirement
    assert fastercap.passed_tolerance is True
    assert fastercap.relative_error_vs_analytical <= 0.01
    assert fastercap.capacitance_per_m_f > 0.0
    assert analytical.capacitance_per_m_f == pytest.approx(1.6701e-10, rel=1e-2)
    assert analytical.z0_ohm == pytest.approx(50.01, rel=1e-2)


def test_cross_solver_high_frequency_fdtd_vs_fem() -> None:
    geom = CPWBenchmarkGeometry()
    hf_points = compute_high_frequency_cross_validation(geom, [2.0, 5.0, 10.0])

    assert len(hf_points) == 3
    for pt in hf_points:
        # Assert difference between FDTD and FEM is strictly within discretization tolerance (< 0.5%)
        assert pt.z0_relative_difference < 0.005
        assert pt.vp_relative_difference < 0.005
        assert pt.openems_fdtd_z0_ohm > 0.0
        assert pt.palace_fem_z0_ohm > 0.0


def test_full_cross_solver_benchmark_report() -> None:
    report = run_cpw_cross_validation_benchmark()
    assert report.fastercap.passed_tolerance is True
    assert "fdtd_yee_grid" in report.discretization_analysis
    assert "fem_tetrahedral_mesh" in report.discretization_analysis
    assert "bem_fastercap" in report.discretization_analysis
