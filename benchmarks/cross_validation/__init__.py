"""Cross-solver electromagnetic validation benchmarks."""

from benchmarks.cross_validation.cpw_cross_validation import (
    CPWBenchmarkGeometry,
    CrossSolverBenchmarkReport,
    compute_analytical_ghione_naldi,
    compute_fastercap_bem_capacitance,
    compute_high_frequency_cross_validation,
    run_cpw_cross_validation_benchmark,
)

__all__ = [
    "CPWBenchmarkGeometry",
    "CrossSolverBenchmarkReport",
    "compute_analytical_ghione_naldi",
    "compute_fastercap_bem_capacitance",
    "compute_high_frequency_cross_validation",
    "run_cpw_cross_validation_benchmark",
]
