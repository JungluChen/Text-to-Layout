"""Simulation-vs-measurement residual comparison and correction-factor fitting.

Pairing: a :class:`SimulatedPrediction` and a :class:`MeasurementRecord` are
compared only when their ``design_hash`` matches — comparing unrelated
designs would produce meaningless residuals. Every quantity present on BOTH
sides is compared; a quantity present on only one side is silently skipped
for that pair (not an error — different design flows populate different
quantities).

Correction-factor derivation (documented, not hidden in code):

- ``capacitance_scale`` / ``inductance_scale``: sample mean of
  measured/simulated ratio across all pairs where both sides have that
  quantity.
- ``loss_tangent_scale``: sample mean of predicted_Q/measured_Q. Lower
  measured Q than predicted means the real process has more loss than the
  model assumed, so the effective loss tangent should scale UP by this factor
  for closer future predictions.
- ``jc_scale``: assumes ``f ~ sqrt(Jc / C)`` for a fixed junction area (from
  ``f = 1/(2*pi*sqrt(LJ*C))`` with ``LJ = Phi0/(2*pi*Ic)``, ``Ic = Jc*A``), so
  ``Jc_scale = (f_measured/f_predicted)^2 / capacitance_scale``. When no
  independent capacitance measurement exists, ``capacitance_scale`` defaults
  to 1.0 for this one derivation (documented explicitly in the result's
  ``method`` string via the caller).
- ``jc_scale_sigma_pct``: the sample standard deviation of the per-device
  ``jc_scale``, expressed as a percentage — an updated *wafer-level Jc sigma*
  estimate from real yield data, not a per-device number.
"""

from __future__ import annotations

import statistics

from textlayout.measurement.models import (
    CorrectionFactors,
    MeasurementRecord,
    ResidualRecord,
    SimulatedPrediction,
)

_QUANTITIES: tuple[tuple[str, str, str], ...] = (
    ("frequency_ghz", "predicted_frequency_ghz", "measured_frequency_ghz"),
    ("capacitance_pf", "predicted_capacitance_pf", "measured_capacitance_pf"),
    ("inductance_nh", "predicted_inductance_nh", "measured_inductance_nh"),
    ("q", "predicted_q", "measured_q"),
    ("t1_us", "predicted_t1_us", "measured_t1_us"),
)


def compare_pair(
    prediction: SimulatedPrediction, measurement: MeasurementRecord
) -> list[ResidualRecord]:
    """Residuals for every quantity present on both sides of one device."""
    if prediction.design_hash != measurement.design_hash:
        raise ValueError(
            f"design_hash mismatch: prediction={prediction.design_hash!r} "
            f"measurement={measurement.design_hash!r}; refusing to compare unrelated designs"
        )
    residuals: list[ResidualRecord] = []
    for quantity, pred_attr, meas_attr in _QUANTITIES:
        sim_value = getattr(prediction, pred_attr)
        meas_value = getattr(measurement, meas_attr)
        if sim_value is None or meas_value is None:
            continue
        error_abs = meas_value - sim_value
        error_pct = error_abs / sim_value * 100.0
        residuals.append(
            ResidualRecord(
                device_id=measurement.device_id,
                design_hash=measurement.design_hash,
                quantity=quantity,
                simulated_value=sim_value,
                measured_value=meas_value,
                unit=_unit_for(quantity),
                error_absolute=error_abs,
                error_percent=error_pct,
            )
        )
    return residuals


def compare_all(
    pairs: list[tuple[SimulatedPrediction, MeasurementRecord]],
) -> list[ResidualRecord]:
    """Residuals across every (prediction, measurement) pair, in order."""
    residuals: list[ResidualRecord] = []
    for prediction, measurement in pairs:
        residuals.extend(compare_pair(prediction, measurement))
    return residuals


def _unit_for(quantity: str) -> str:
    return {
        "frequency_ghz": "GHz",
        "capacitance_pf": "pF",
        "inductance_nh": "nH",
        "q": "dimensionless",
        "t1_us": "us",
    }[quantity]


def fit_correction_factors(
    pairs: list[tuple[SimulatedPrediction, MeasurementRecord]],
) -> CorrectionFactors:
    """Fit capacitance/inductance/loss-tangent/Jc correction factors from measured pairs.

    Raises :class:`ValueError` if ``pairs`` is empty — a correction fit needs
    at least one measurement.
    """
    if not pairs:
        raise ValueError("cannot fit correction factors from zero measurement pairs")
    for prediction, measurement in pairs:
        if prediction.design_hash != measurement.design_hash:
            raise ValueError(
                f"design_hash mismatch in pair: {prediction.design_hash!r} vs "
                f"{measurement.design_hash!r}"
            )

    capacitance_ratios = [
        measurement.measured_capacitance_pf / prediction.predicted_capacitance_pf
        for prediction, measurement in pairs
        if prediction.predicted_capacitance_pf and measurement.measured_capacitance_pf
    ]
    inductance_ratios = [
        measurement.measured_inductance_nh / prediction.predicted_inductance_nh
        for prediction, measurement in pairs
        if prediction.predicted_inductance_nh and measurement.measured_inductance_nh
    ]
    loss_ratios = [
        prediction.predicted_q / measurement.measured_q
        for prediction, measurement in pairs
        if prediction.predicted_q and measurement.measured_q
    ]
    capacitance_scale = (
        sum(capacitance_ratios) / len(capacitance_ratios) if capacitance_ratios else None
    )

    jc_scales: list[float] = []
    for prediction, measurement in pairs:
        c_scale_for_pair = (
            measurement.measured_capacitance_pf / prediction.predicted_capacitance_pf
            if prediction.predicted_capacitance_pf and measurement.measured_capacitance_pf
            else 1.0  # no independent C measurement: assume C is as predicted for this derivation
        )
        frequency_ratio = measurement.measured_frequency_ghz / prediction.predicted_frequency_ghz
        jc_scales.append(frequency_ratio * frequency_ratio / c_scale_for_pair)

    jc_scale = sum(jc_scales) / len(jc_scales) if jc_scales else None
    jc_sigma_pct = (
        statistics.pstdev(jc_scales) / jc_scale * 100.0
        if jc_scale and len(jc_scales) >= 2
        else None
    )

    return CorrectionFactors(
        capacitance_scale=capacitance_scale,
        inductance_scale=(
            sum(inductance_ratios) / len(inductance_ratios) if inductance_ratios else None
        ),
        loss_tangent_scale=sum(loss_ratios) / len(loss_ratios) if loss_ratios else None,
        jc_scale=jc_scale,
        jc_scale_sigma_pct=jc_sigma_pct,
        n_capacitance_pairs=len(capacitance_ratios),
        n_inductance_pairs=len(inductance_ratios),
        n_loss_pairs=len(loss_ratios),
        n_jc_pairs=len(jc_scales),
    )
