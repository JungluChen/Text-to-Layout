"""Schemas for the simulation-to-measurement correlation loop.

Why this exists: every other cQED loop in this project (EPR/coherence, JJ
yield, PDK process parameters) runs on either analytical models or
illustrative example numbers. The only way any of those numbers become
trustworthy for a specific process is correlation against real fabricated,
cooled-down, measured devices. This module is the typed bridge: a
measurement record schema, a residual comparison engine, and a
correction-factor fit that can feed back into the PDK's `junction_process`
statistics or the EPR materials database.

This is explicitly the last-mile calibration step, not a substitute for it:
every result here is `synthetic=True` until it runs on real committed
measurement data, and even then the fitted corrections are only as good as
the sample size behind them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MEASUREMENT_SCHEMA = "textlayout.measurement-record.v1"
PREDICTION_SCHEMA = "textlayout.simulated-prediction.v1"
CALIBRATION_SCHEMA = "textlayout.calibration.v1"


class MeasurementRecord(BaseModel):
    """One real, cooled-down, measured device."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=MEASUREMENT_SCHEMA)
    device_id: str
    wafer_id: str
    design_hash: str = Field(description="Identifies which design/spec this device came from.")
    measured_frequency_ghz: float = Field(gt=0)
    measured_capacitance_pf: float | None = Field(default=None, gt=0)
    measured_inductance_nh: float | None = Field(default=None, gt=0)
    measured_q: float | None = Field(default=None, gt=0)
    measured_t1_us: float | None = Field(default=None, gt=0)
    measured_t2_us: float | None = Field(default=None, gt=0)
    temperature_k: float = Field(gt=0)
    cooldown_id: str
    chip_id: str | None = Field(default=None)
    device_type: str | None = Field(
        default=None, description="idc | cpw | spiral | resonator | qubit | ..."
    )
    measurement_source: str = Field(
        default="unspecified",
        description="Instrument/lab/provenance of the measurement, or 'synthetic_fixture'.",
    )
    synthetic: bool = Field(
        default=True,
        description="False ONLY for real cooled-down hardware data. Defaults to "
        "True so forgetting the flag can never promote fixture data.",
    )
    notes: list[str] = Field(default_factory=list)


class SimulatedPrediction(BaseModel):
    """The simulated/analytical prediction for the SAME design as a measurement.

    Fields are optional except ``design_hash``/``predicted_frequency_ghz``
    because different design flows populate different quantities (e.g. an
    IDC has capacitance but not Q; a resonator has Q but maybe not a
    standalone inductance).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=PREDICTION_SCHEMA)
    design_hash: str
    predicted_frequency_ghz: float = Field(gt=0)
    predicted_capacitance_pf: float | None = Field(default=None, gt=0)
    predicted_inductance_nh: float | None = Field(default=None, gt=0)
    predicted_q: float | None = Field(default=None, gt=0)
    predicted_t1_us: float | None = Field(default=None, gt=0)
    source: str = Field(
        description="Where the prediction came from, e.g. 'FasterCap 6.0.7' or "
        "'textlayout.epr.AnalyticalEPRBackend'."
    )
    device_type: str | None = Field(default=None)
    pdk_name: str | None = Field(default=None)
    pdk_version: str | None = Field(default=None)
    pdk_hash: str | None = Field(
        default=None, description="sha256 of the PDK file backing this prediction."
    )
    evidence_status: str | None = Field(
        default=None, description="PHYSICS_VERIFIED | SIMULATION_EXECUTED | ANALYTICAL_ONLY | ..."
    )
    evidence_path: str | None = Field(default=None)


class ResidualRecord(BaseModel):
    """One quantity's simulated-vs-measured comparison for one device."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    device_id: str
    design_hash: str
    quantity: str = Field(description="frequency_ghz | capacitance_pf | inductance_nh | q | t1_us")
    simulated_value: float
    measured_value: float
    unit: str
    error_absolute: float
    error_percent: float


class CorrectionFactors(BaseModel):
    """Fitted multiplicative corrections from a set of (prediction, measurement) pairs.

    Every scale is defined as measured/predicted (or the physically appropriate
    transform of that ratio) so a factor of 1.0 means "the model already
    matches measurement" and factors are directly usable to rescale future
    predictions from the same process.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capacitance_scale: float | None = Field(
        default=None, gt=0, description="mean(measured_C / simulated_C)."
    )
    inductance_scale: float | None = Field(
        default=None, gt=0, description="mean(measured_L / simulated_L)."
    )
    loss_tangent_scale: float | None = Field(
        default=None,
        gt=0,
        description="mean(predicted_Q / measured_Q) -- >1 means real loss exceeds the "
        "model's assumed loss tangent (Q_measured lower than predicted).",
    )
    jc_scale: float | None = Field(
        default=None,
        gt=0,
        description="Implied Jc scale from frequency residuals: "
        "(f_measured/f_predicted)^2 / capacitance_scale, assuming f ~ sqrt(Jc/C).",
    )
    jc_scale_sigma_pct: float | None = Field(
        default=None,
        ge=0,
        description="Sample std of per-device jc_scale (%) -- an updated wafer-level "
        "Jc sigma estimate, not a single-device number.",
    )
    n_capacitance_pairs: int = Field(default=0, ge=0)
    n_inductance_pairs: int = Field(default=0, ge=0)
    n_loss_pairs: int = Field(default=0, ge=0)
    n_jc_pairs: int = Field(default=0, ge=0)
    method: str = Field(default="sample_mean_ratio")


class CalibrationFile(BaseModel):
    """A persisted, versioned calibration -- the artifact `measurement calibrate` writes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=CALIBRATION_SCHEMA)
    corrections: CorrectionFactors
    source_device_ids: list[str]
    n_records: int = Field(ge=0)
    synthetic: bool = Field(
        default=True, description="True unless every input measurement is from a real cooldown."
    )
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
