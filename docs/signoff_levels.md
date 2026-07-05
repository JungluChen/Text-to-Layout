# Signoff levels — `textlayout.signoff`

**Level 6 requires measurement correlation, not only simulation.** A design
that reaches Level 5 (a real solver executed, output parsed, result within
tolerance) is still *simulated*, not *measured*. Level 6 is reserved for the
one thing that closes that gap: a real, non-synthetic
[`CalibrationFile`](measurement_calibration.md) correlating this design's
prediction against an actual fabricated, cooled-down device.

## The seven levels

Sequential and gated — each level requires every prior level to already hold;
a design cannot skip from Level 3 straight to claiming Level 6.

| Level | Label | Requires |
| --- | --- | --- |
| -1 | No geometry | — |
| 0 | Geometry generated | GDS exists and passed layout verification |
| 1 | DRC passed | Level 0 + design-rule check passed |
| 2 | Extraction complete | Level 1 (this path's verification already includes extraction) |
| 3 | Analytical sanity | Level 2 |
| 4 | One solver executed | Level 3 + `QuantityEvidence.status` is `SIMULATION_EXECUTED` or `PHYSICS_VERIFIED` |
| 5 | **Physics signoff** | Level 4 + `QuantityEvidence.is_physics_verified` (within tolerance) |
| 6 | **Measurement-calibrated** | Level 5 + a `CalibrationFile` with `synthetic=False` |

## Usage

```python
from textlayout.signoff import evaluate_signoff

result = evaluate_signoff(
    geometry_pass=True,
    drc_passed=True,
    verification_passed=True,
    evidence=capacitance_evidence,   # a textlayout.evidence.QuantityEvidence
    calibration=calibration_file,    # a textlayout.measurement.CalibrationFile, or None
)
print(result.level, result.label, result.blockers)
```

`result.blockers` always explains exactly what stopped a design from
advancing — never a bare number with no justification. Two examples:

- **Physics-verified, no calibration:** `level=5`, blocker: *"Level 5
  (physics signoff) reached, but no measurement correlation exists. Level 6
  requires a real, non-synthetic CalibrationFile ... simulation evidence
  alone is not enough."*
- **Physics-verified, but the only calibration on file is synthetic:**
  `level=5` (not 6), blocker names `synthetic=True` explicitly — a synthetic
  calibration (e.g. the committed `examples/measurement_fixtures/`) can
  exercise the calibration *math*, but can never itself justify Level 6.

## Why this exists

Every other illustrative-to-calibrated path in this project (EPR loss
tangents, PDK process parameters, JJ yield statistics) can be fitted against
measurement data via `textlayout measurement calibrate` — but a fitted
calibration file existing is not the same claim as "this specific design was
correlated against a real device." Level 6 is the one place that distinction
is enforced structurally, not just documented in prose.
