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
from textlayout.measurement.loaders import load_measurements, load_predictions
from textlayout.measurement.overlay import (
    FIT_INSUFFICIENT,
    FIT_OK,
    FIT_UNSTABLE,
    OVERLAY_SCHEMA,
    STATUS_MEASUREMENT,
    STATUS_SYNTHETIC_ONLY,
    CalibrationOverlay,
    FittedFactor,
    apply_overlay_to_pdk,
    build_overlay,
    load_overlay,
    write_overlay,
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
    COMPARISON_INSUFFICIENT,
    COMPARISON_MATCHED,
    COMPARISON_PARTIAL,
    ComparisonSummary,
    QuantityStats,
    build_comparison_summary,
    render_calibration_markdown,
    render_comparison_markdown,
    write_calibration_report,
    write_comparison_bundle,
    write_comparison_report,
)

__all__ = [
    "CALIBRATION_SCHEMA",
    "COMPARISON_INSUFFICIENT",
    "COMPARISON_MATCHED",
    "COMPARISON_PARTIAL",
    "FIT_INSUFFICIENT",
    "FIT_OK",
    "FIT_UNSTABLE",
    "MEASUREMENT_SCHEMA",
    "OVERLAY_SCHEMA",
    "PREDICTION_SCHEMA",
    "STATUS_MEASUREMENT",
    "STATUS_SYNTHETIC_ONLY",
    "CalibrationFile",
    "CalibrationOverlay",
    "CorrectionFactors",
    "FittedFactor",
    "MeasurementRecord",
    "ResidualRecord",
    "SimulatedPrediction",
    "apply_overlay_to_pdk",
    "build_calibration",
    "ComparisonSummary",
    "QuantityStats",
    "build_comparison_summary",
    "build_overlay",
    "compare_all",
    "compare_pair",
    "fit_correction_factors",
    "load_calibration",
    "load_measurements",
    "load_overlay",
    "load_predictions",
    "pair_by_design_hash",
    "render_calibration_markdown",
    "render_comparison_markdown",
    "write_calibration",
    "write_calibration_report",
    "write_comparison_bundle",
    "write_comparison_report",
    "write_overlay",
]
