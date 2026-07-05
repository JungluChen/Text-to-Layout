"""Simulation-to-measurement correlation: the path from illustrative to calibrated.

Every other cQED loop in this project (EPR participation, JJ yield, PDK
process parameters) runs on illustrative, literature-scale numbers. This
package is the mechanism that replaces them with real, process-specific
values: compare simulated/predicted quantities against real measured devices,
fit correction factors, and persist a calibration file that downstream loops
can consume.

See :mod:`textlayout.measurement.correlation` for the residual/fit math and
:mod:`textlayout.measurement.calibration` for pairing and persistence.
"""

from textlayout.measurement.calibration import (
    build_calibration,
    load_calibration,
    pair_by_design_hash,
    write_calibration,
)
from textlayout.measurement.correlation import (
    compare_all,
    compare_pair,
    fit_correction_factors,
)
from textlayout.measurement.models import (
    CALIBRATION_SCHEMA,
    MEASUREMENT_SCHEMA,
    PREDICTION_SCHEMA,
    CalibrationFile,
    CorrectionFactors,
    MeasurementRecord,
    ResidualRecord,
    SimulatedPrediction,
)
from textlayout.measurement.report import (
    render_calibration_markdown,
    render_comparison_markdown,
    write_calibration_report,
    write_comparison_report,
)

__all__ = [
    "CALIBRATION_SCHEMA",
    "MEASUREMENT_SCHEMA",
    "PREDICTION_SCHEMA",
    "CalibrationFile",
    "CorrectionFactors",
    "MeasurementRecord",
    "ResidualRecord",
    "SimulatedPrediction",
    "build_calibration",
    "compare_all",
    "compare_pair",
    "fit_correction_factors",
    "load_calibration",
    "pair_by_design_hash",
    "render_calibration_markdown",
    "render_comparison_markdown",
    "write_calibration",
    "write_calibration_report",
    "write_comparison_report",
]
