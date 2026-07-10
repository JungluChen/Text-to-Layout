"""Calibration overlays: robust correction-factor fits bound to a base PDK.

The overlay is the Sprint-5 contract artifact: a *non-destructive* file that
records which exact base PDK (name, version, sha256) a set of fitted
correction factors applies to, how each factor was fitted (median ratio,
MAD spread, 3-MAD outlier exclusion, minimum-sample gate), and — always —
whether the inputs were synthetic. Applying an overlay writes a NEW PDK
file; the base PDK is never edited.

Honesty gates, in order of precedence per factor:

- fewer matched pairs than ``min_samples``  -> ``INSUFFICIENT_MEASUREMENT_DATA``
  (no scale is emitted at all — a fit from two points is a guess, not a fit);
- robust spread (1.4826*MAD/median) above ``max_stable_spread_pct`` ->
  ``UNSTABLE_FIT`` (the scale is recorded for diagnosis but must not be
  applied, and ``apply_overlay_to_pdk`` refuses to use it);
- otherwise ``FIT_OK``.

Any synthetic input record forces the whole overlay to
``SYNTHETIC_CALIBRATION_ONLY`` — synthetic fixtures can exercise every code
path but can never produce a measurement-calibrated (let alone
foundry-calibrated) status.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from textlayout.measurement.calibration import pair_by_design_hash
from textlayout.measurement.models import MeasurementRecord, SimulatedPrediction
from textlayout.pdk.loader import load_pdk
from textlayout.pdk.models import CALIBRATION_ILLUSTRATIVE, CALIBRATION_INTERNAL
from textlayout.pdk.provenance import describe_pdk_file

OVERLAY_SCHEMA = "textlayout.pdk-calibration-overlay.v1"

STATUS_SYNTHETIC_ONLY = "SYNTHETIC_CALIBRATION_ONLY"
STATUS_MEASUREMENT = "MEASUREMENT_CALIBRATED"

FIT_OK = "FIT_OK"
FIT_INSUFFICIENT = "INSUFFICIENT_MEASUREMENT_DATA"
FIT_UNSTABLE = "UNSTABLE_FIT"

#: (factor name, how the per-pair ratio is computed). ``loss_tangent_scale``
#: is predicted_Q/measured_Q: lower measured Q than predicted means the real
#: process is lossier than the model, so the effective loss tangent scales UP.
_RATIO_FACTORS: tuple[tuple[str, str, str, bool], ...] = (
    ("capacitance_scale", "predicted_capacitance_pf", "measured_capacitance_pf", False),
    ("inductance_scale", "predicted_inductance_nh", "measured_inductance_nh", False),
    ("frequency_scale", "predicted_frequency_ghz", "measured_frequency_ghz", False),
    ("q_scale", "predicted_q", "measured_q", False),
    ("t1_scale", "predicted_t1_us", "measured_t1_us", False),
    ("loss_tangent_scale", "predicted_q", "measured_q", True),  # inverted ratio
)


class FittedFactor(BaseModel):
    """One correction factor with its fit provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    scale: float | None = Field(
        default=None, gt=0, description="Median(measured/predicted) ratio; None if not fitted."
    )
    uncertainty_pct: float | None = Field(
        default=None,
        ge=0,
        description="Robust spread: 1.4826*MAD/median as a percentage.",
    )
    n_pairs: int = Field(ge=0)
    outlier_device_ids: list[str] = Field(
        default_factory=list,
        description="Devices whose ratio sat more than 3 MAD from the median "
        "(excluded from the fit, flagged here).",
    )
    status: str = Field(description="FIT_OK | INSUFFICIENT_MEASUREMENT_DATA | UNSTABLE_FIT")
    method: str = Field(default="median_ratio_mad")
    unit: str = Field(default="dimensionless (measured/predicted)")


class CalibrationOverlay(BaseModel):
    """The persisted overlay artifact — never a destructive edit to the base PDK."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=OVERLAY_SCHEMA)
    base_pdk_name: str
    base_pdk_version: str
    base_pdk_hash_sha256: str
    base_pdk_path: str
    calibration_status: str = Field(
        description="SYNTHETIC_CALIBRATION_ONLY | MEASUREMENT_CALIBRATED"
    )
    is_synthetic: bool
    fabrication_readiness: str = Field(default="NOT_FABRICATION_READY")
    fit_method: str = Field(
        default="median ratio, 1.4826*MAD spread, 3-MAD outlier exclusion, "
        "minimum-sample gate"
    )
    fit_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    factors: dict[str, FittedFactor]
    jc_sigma_update_pct: float | None = Field(
        default=None,
        ge=0,
        description="Robust spread of per-device implied Jc scale (%) — a wafer-level "
        "Jc sigma estimate. None when the Jc fit did not pass its gates.",
    )
    input_files: list[str]
    records_used: list[str] = Field(description="Matched measurement device_ids.")
    records_rejected: list[str] = Field(
        default_factory=list, description="Unmatched or outlier device_ids."
    )
    warnings: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def _robust_fit(
    name: str,
    samples: list[tuple[str, float]],
    *,
    min_samples: int,
    max_stable_spread_pct: float,
) -> FittedFactor:
    if len(samples) < min_samples:
        return FittedFactor(
            name=name,
            n_pairs=len(samples),
            status=FIT_INSUFFICIENT,
        )
    ratios = [value for _, value in samples]
    median = statistics.median(ratios)
    mad = statistics.median([abs(value - median) for value in ratios])
    spread = 1.4826 * mad
    outliers = [
        device_id for device_id, value in samples if mad > 0 and abs(value - median) > 3 * spread
    ]
    kept = [value for device_id, value in samples if device_id not in outliers]
    if len(kept) < min_samples:
        return FittedFactor(
            name=name,
            n_pairs=len(samples),
            outlier_device_ids=outliers,
            status=FIT_INSUFFICIENT,
        )
    median = statistics.median(kept)
    mad = statistics.median([abs(value - median) for value in kept])
    uncertainty_pct = (1.4826 * mad / median * 100.0) if median else None
    status = (
        FIT_UNSTABLE
        if uncertainty_pct is not None and uncertainty_pct > max_stable_spread_pct
        else FIT_OK
    )
    return FittedFactor(
        name=name,
        scale=median,
        uncertainty_pct=uncertainty_pct,
        n_pairs=len(samples),
        outlier_device_ids=outliers,
        status=status,
    )


def build_overlay(
    predictions: list[SimulatedPrediction],
    measurements: list[MeasurementRecord],
    *,
    base_pdk_path: str | Path,
    input_files: list[str],
    min_samples: int = 3,
    max_stable_spread_pct: float = 50.0,
) -> CalibrationOverlay:
    """Fit a calibration overlay against a specific base PDK file."""
    provenance = describe_pdk_file(base_pdk_path)
    pairs = pair_by_design_hash(predictions, measurements)
    matched_ids = [measurement.device_id for _, measurement in pairs]
    unmatched = [
        measurement.device_id
        for measurement in measurements
        if measurement.device_id not in matched_ids
    ]
    is_synthetic = (not measurements) or any(m.synthetic for m in measurements)

    factors: dict[str, FittedFactor] = {}
    for name, pred_attr, meas_attr, inverted in _RATIO_FACTORS:
        samples = []
        for prediction, measurement in pairs:
            pred = getattr(prediction, pred_attr)
            meas = getattr(measurement, meas_attr)
            if pred and meas:
                samples.append(
                    (measurement.device_id, (pred / meas) if inverted else (meas / pred))
                )
        factors[name] = _robust_fit(
            name, samples, min_samples=min_samples, max_stable_spread_pct=max_stable_spread_pct
        )

    # Implied Jc scale from frequency residuals: f ~ sqrt(Jc/C) with a fixed
    # junction area, so Jc_scale = (f_m/f_p)^2 / C_scale (per-pair C ratio
    # when both sides carry capacitance; 1.0 otherwise, documented).
    jc_samples: list[tuple[str, float]] = []
    for prediction, measurement in pairs:
        if not (prediction.predicted_frequency_ghz and measurement.measured_frequency_ghz):
            continue
        c_ratio = (
            measurement.measured_capacitance_pf / prediction.predicted_capacitance_pf
            if prediction.predicted_capacitance_pf and measurement.measured_capacitance_pf
            else 1.0
        )
        f_ratio = measurement.measured_frequency_ghz / prediction.predicted_frequency_ghz
        jc_samples.append((measurement.device_id, f_ratio * f_ratio / c_ratio))
    factors["jc_mean_scale"] = _robust_fit(
        "jc_mean_scale",
        jc_samples,
        min_samples=min_samples,
        max_stable_spread_pct=max_stable_spread_pct,
    )
    jc_factor = factors["jc_mean_scale"]
    jc_sigma_update = (
        jc_factor.uncertainty_pct if jc_factor.status == FIT_OK else None
    )

    warnings = []
    if is_synthetic:
        warnings.append(
            "SYNTHETIC calibration: fitted from example/fixture data, not a real "
            "cooldown. These factors demonstrate the pipeline; they say nothing "
            "about any real process."
        )
    for factor in factors.values():
        if factor.status == FIT_UNSTABLE:
            warnings.append(
                f"{factor.name}: robust spread {factor.uncertainty_pct:.1f}% exceeds "
                f"{max_stable_spread_pct:g}% — flagged UNSTABLE_FIT and never applied."
            )
        if factor.outlier_device_ids:
            warnings.append(
                f"{factor.name}: outlier device(s) excluded from the fit: "
                f"{', '.join(factor.outlier_device_ids)}."
            )
    outlier_ids = sorted(
        {device_id for factor in factors.values() for device_id in factor.outlier_device_ids}
    )

    return CalibrationOverlay(
        base_pdk_name=provenance.pdk_name,
        base_pdk_version=provenance.pdk_version,
        base_pdk_hash_sha256=provenance.file_hash_sha256,
        base_pdk_path=str(base_pdk_path),
        calibration_status=STATUS_SYNTHETIC_ONLY if is_synthetic else STATUS_MEASUREMENT,
        is_synthetic=is_synthetic,
        factors=factors,
        jc_sigma_update_pct=jc_sigma_update,
        input_files=[str(f) for f in input_files],
        records_used=matched_ids,
        records_rejected=sorted(set(unmatched) | set(outlier_ids)),
        warnings=warnings,
    )


def write_overlay(overlay: CalibrationOverlay, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(overlay.to_dict(), sort_keys=False), encoding="utf-8")
    return out


def load_overlay(path: str | Path) -> CalibrationOverlay:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return CalibrationOverlay.model_validate(data)


def apply_overlay_to_pdk(
    base_pdk_path: str | Path, overlay: CalibrationOverlay, out_path: str | Path
) -> Path:
    """Write a NEW calibrated PDK file; never touches the base file.

    Applies only ``FIT_OK`` factors that map onto PDK fields:
    ``loss_tangent_scale`` -> substrate.loss_tangent,
    ``jc_mean_scale`` -> junction_process.target_jc_ua_per_um2,
    ``jc_sigma_update_pct`` -> junction_process.jc_sigma_pct.
    A synthetic overlay yields calibration_status ``illustrative`` (with an
    explicit note); only real measurement data earns ``internal_calibrated``.
    Foundry calibration is out of reach of this tool by definition.
    """
    base = Path(base_pdk_path)
    out = Path(out_path)
    if out.resolve() == base.resolve():
        raise ValueError(
            f"refusing to overwrite the base PDK {base}; calibration output must "
            "be a new file"
        )
    provenance = describe_pdk_file(base)
    if provenance.file_hash_sha256 != overlay.base_pdk_hash_sha256:
        raise ValueError(
            f"overlay was fitted against {overlay.base_pdk_name} "
            f"(sha256 {overlay.base_pdk_hash_sha256[:12]}...) but {base} hashes to "
            f"{provenance.file_hash_sha256[:12]}... — refusing to apply a "
            "calibration to a PDK it was not fitted for"
        )

    data = yaml.safe_load(base.read_text(encoding="utf-8"))
    applied: list[str] = []

    loss = overlay.factors.get("loss_tangent_scale")
    if loss and loss.status == FIT_OK and loss.scale is not None:
        substrate = data.get("substrate", {})
        substrate["loss_tangent"] = float(substrate["loss_tangent"]) * loss.scale
        applied.append(f"substrate.loss_tangent *= {loss.scale:.6g}")

    jc = overlay.factors.get("jc_mean_scale")
    junction = data.get("junction_process")
    if jc and jc.status == FIT_OK and jc.scale is not None and isinstance(junction, dict):
        junction["target_jc_ua_per_um2"] = float(junction["target_jc_ua_per_um2"]) * jc.scale
        applied.append(f"junction_process.target_jc_ua_per_um2 *= {jc.scale:.6g}")
        if overlay.jc_sigma_update_pct is not None:
            junction["jc_sigma_pct"] = overlay.jc_sigma_update_pct
            applied.append(
                f"junction_process.jc_sigma_pct = {overlay.jc_sigma_update_pct:.4g}"
            )

    suffix = "_synthetic_calibrated" if overlay.is_synthetic else "_calibrated"
    data["name"] = f"{data['name']}{suffix}"
    data["calibration_status"] = (
        CALIBRATION_ILLUSTRATIVE if overlay.is_synthetic else CALIBRATION_INTERNAL
    )
    data["foundry_validated"] = False
    data["source"] = (
        f"{data.get('source', '')} | Calibrated from overlay "
        f"({overlay.calibration_status}, fitted {overlay.fit_timestamp}, base sha256 "
        f"{overlay.base_pdk_hash_sha256[:12]}...): {'; '.join(applied) or 'no factors applied'}. "
        + (
            "SYNTHETIC inputs — numbers demonstrate the pipeline only. "
            if overlay.is_synthetic
            else ""
        )
        + "NOT fabrication-ready."
    )
    load_pdk_check = data  # validated below through the real loader
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(load_pdk_check, sort_keys=False), encoding="utf-8")
    load_pdk(out)  # round-trip validation: the calibrated file must be a valid PDK
    return out
