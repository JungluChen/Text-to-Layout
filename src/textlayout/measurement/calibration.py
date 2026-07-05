"""Build and persist a :class:`CalibrationFile` from fitted correction factors."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from textlayout.measurement.correlation import fit_correction_factors
from textlayout.measurement.models import CalibrationFile, MeasurementRecord, SimulatedPrediction


def pair_by_design_hash(
    predictions: list[SimulatedPrediction], measurements: list[MeasurementRecord]
) -> list[tuple[SimulatedPrediction, MeasurementRecord]]:
    """Pair predictions to measurements sharing a design_hash.

    A prediction with no matching measurement, or a measurement with no
    matching prediction, is silently excluded — it contributes no residual,
    not an error. Raises if a design_hash appears more than once on either
    side (ambiguous pairing).
    """
    by_hash: dict[str, SimulatedPrediction] = {}
    for prediction in predictions:
        if prediction.design_hash in by_hash:
            raise ValueError(
                f"duplicate design_hash {prediction.design_hash!r} in predictions; "
                "pairing would be ambiguous"
            )
        by_hash[prediction.design_hash] = prediction

    seen_devices: set[str] = set()
    pairs: list[tuple[SimulatedPrediction, MeasurementRecord]] = []
    for measurement in measurements:
        if measurement.device_id in seen_devices:
            raise ValueError(f"duplicate device_id {measurement.device_id!r} in measurements")
        seen_devices.add(measurement.device_id)
        matched_prediction = by_hash.get(measurement.design_hash)
        if matched_prediction is not None:
            pairs.append((matched_prediction, measurement))
    return pairs


def build_calibration(
    predictions: list[SimulatedPrediction],
    measurements: list[MeasurementRecord],
    *,
    synthetic: bool = True,
) -> CalibrationFile:
    """Fit and package a calibration from paired predictions/measurements."""
    pairs = pair_by_design_hash(predictions, measurements)
    if not pairs:
        raise ValueError(
            "no prediction/measurement pairs share a design_hash; nothing to calibrate"
        )
    corrections = fit_correction_factors(pairs)
    return CalibrationFile(
        corrections=corrections,
        source_device_ids=[measurement.device_id for _, measurement in pairs],
        n_records=len(pairs),
        synthetic=synthetic,
        notes=(
            []
            if not synthetic
            else [
                "SYNTHETIC calibration: fitted from example/test measurement data, "
                "not a real cooldown. Do not apply these factors to production designs."
            ]
        ),
    )


def write_calibration(calibration: CalibrationFile, path: str | Path) -> Path:
    """Write a calibration file as YAML (human-editable, diff-friendly)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(calibration.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    return out


def load_calibration(path: str | Path) -> CalibrationFile:
    """Load a previously written calibration file (YAML or JSON)."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    data = (
        yaml.safe_load(text)
        if file_path.suffix.lower() in (".yaml", ".yml")
        else json.loads(text)
    )
    return CalibrationFile.model_validate(data)
