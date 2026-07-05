# Measurement correlation: the path from simulation toy to fab-calibrated tool

**Why this exists:** every other cQED loop this project ships — EPR/loss
participation, JJ yield modeling, PDK process parameters — runs on
illustrative, literature-scale numbers explicitly marked as not
foundry-calibrated. The only thing that can ever change that is comparing
predictions against real, fabricated, cooled-down, measured devices. This
module is that comparison: a typed measurement record, a residual engine, and
a correction-factor fit that feeds directly back into the other loops'
inputs.

## The schemas

- **`SimulatedPrediction`**: whatever a design flow predicted for one design
  (`design_hash`) — frequency, and optionally capacitance, inductance, Q, T1
  — plus `source` (which backend/model produced it).
- **`MeasurementRecord`**: one real device — `device_id`, `wafer_id`,
  `design_hash` (links back to the prediction), measured frequency (required)
  and optionally capacitance/inductance/Q/T1/T2, plus `temperature_k` and
  `cooldown_id`.

Pairing is by `design_hash`: a prediction and a measurement are compared only
when they describe the same design. A quantity present on only one side is
skipped for that pair, not an error — different design flows populate
different quantities.

## `textlayout measurement compare` — residuals

```bash
textlayout measurement compare \
  --predicted examples/measurement_fixtures/predictions.json \
  --measured examples/measurement_fixtures/measurements.json \
  --out out/evidence
```

Writes a residual table (`measurement_comparison.json`/`.md`): simulated
value, measured value, absolute and percent error, per device per quantity.

## `textlayout measurement calibrate` — correction factors

```bash
textlayout measurement calibrate \
  --predicted examples/measurement_fixtures/predictions.json \
  --measured examples/measurement_fixtures/measurements.json \
  --out out/evidence
```

Fits four correction factors (documented in full in
`textlayout.measurement.correlation`):

| Factor | Definition | Feeds back into |
| --- | --- | --- |
| `capacitance_scale` | mean(measured C / simulated C) | Future capacitance predictions for this process. |
| `inductance_scale` | mean(measured L / simulated L) | Future inductance predictions. |
| `loss_tangent_scale` | mean(predicted Q / measured Q) | `textlayout.epr.materials` — scale `tan_delta` values up when real Q is lower than the model assumed. |
| `jc_scale` | `(f_measured/f_predicted)^2 / capacitance_scale`, from `f ~ sqrt(Jc/C)` | `JJProcessModel.target_jc_ua_per_um2` in `textlayout.yield_model`. |
| `jc_scale_sigma_pct` | sample std of per-device `jc_scale` (%) | `JJProcessModel.wafer_jc_sigma_pct` — an updated, measured wafer-level Jc spread. |

Writes `calibration.yaml` (a persisted, versioned, human-editable calibration
file) and `calibration_report.md`.

**On the committed synthetic example** (`examples/measurement_fixtures/`):
three devices with deliberately imperfect analytical/solver predictions give
`capacitance_scale ≈ 1.025`, `loss_tangent_scale ≈ 1.58` (the resonator's
measured Q of 9500 came in well below its predicted 15000 — a large,
realistic signal that the EPR materials DB's illustrative loss tangents are
optimistic for this synthetic process), and `jc_scale_sigma_pct ≈ 1.7%`.

## Honesty

- Every `CalibrationFile` carries `synthetic: bool` — `True` unless
  `--production` is passed, and the report renders a loud warning when it is.
- The committed example fixtures (`examples/measurement_fixtures/`) are
  explicitly synthetic (each `MeasurementRecord.notes` says so) — they exist
  to keep this loop's math tested in CI, not as a calibration claim.
- `build_calibration` and `pair_by_design_hash` reject ambiguous input
  (duplicate `design_hash` in predictions, duplicate `device_id` in
  measurements, zero overlapping pairs) rather than silently picking one.

## This is the last mile, not a shortcut

A fitted `capacitance_scale` of 1.02 does not mean "the model is now right" —
it means "the model is right *to within the residual scatter of N devices on
one process*." Treat every correction factor as provisional until it is
stable across multiple wafers and cooldowns. This module makes that
comparison possible and auditable; it does not make the underlying physics
correct by itself.
