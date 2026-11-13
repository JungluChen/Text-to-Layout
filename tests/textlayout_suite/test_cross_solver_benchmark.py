"""Analytical CPW sanity and rejection of absent numerical solver evidence."""

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


def test_analytical_cpw_reference_does_not_supply_bem_result() -> None:
    geom = CPWBenchmarkGeometry()
    analytical = compute_analytical_ghione_naldi(geom)
    assert analytical.capacitance_per_m_f == pytest.approx(1.6701e-10, rel=1e-2)
    assert analytical.z0_ohm == pytest.approx(50.01, rel=1e-2)
    with pytest.raises(NotImplementedError, match="FasterCap CPW output"):
        compute_fastercap_bem_capacitance(geom, mesh_refinement_level=3)


def test_missing_fdtd_and_fem_outputs_are_rejected() -> None:
    geom = CPWBenchmarkGeometry()
    with pytest.raises(NotImplementedError, match="openEMS and Palace CPW outputs"):
        compute_high_frequency_cross_validation(geom, [2.0, 5.0, 10.0])


def test_full_cross_solver_report_requires_evidence() -> None:
    with pytest.raises(NotImplementedError, match="CPW cross-solver evidence"):
        run_cpw_cross_validation_benchmark()
