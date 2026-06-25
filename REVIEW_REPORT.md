# Review Report — Text-to-GDS

**Schema:** `text-to-gds.review-report.v1`  
**Generated:** (run date)  
**Device:** (pcell name)  
**GDS:** (path)  
**Sidecar:** (path)

---

> This file is the output template for `review_committee()`. Each design run
> that reaches the review stage should produce a review report in this format.
> A copy is written to `workspace/artifacts/<name>.review_report.md`.

---

## Committee Verdict

| Field | Value |
|---|---|
| **Score** | (min of all reviewer scores) |
| **Approved** | True / False |
| **Error count** | (number of error-severity findings) |
| **Warning count** | (number of warning-severity findings) |
| **Pass threshold** | 90 |

---

## Signoff Level

| Level | Status |
|---|---|
| 0 Geometry generated | PASS / FAIL |
| 1 DRC passed | PASS / FAIL |
| 2 Extraction complete | PASS / FAIL |
| 3 Analytical sanity | PASS / FAIL |
| 4 One solver executed | PASS / FAIL |
| 5 Physics signoff | PASS / FAIL |
| 6 Measurement-calibrated | PASS / FAIL |

**Claimed level:** (level claimed by user or pipeline)  
**Achieved level:** (level awarded by `evaluate_signoff()`)  
**Label:** iteration evidence / physics signoff / measurement-calibrated / blocked

---

## Solver Evidence Table

| Solver | Status | Output file | Evidence |
|---|---|---|---|
| JosephsonCircuits.jl | executed / skipped / failed | path or — | Yes / No |
| scqubits | executed / skipped / failed | path or — | Yes / No |
| openEMS | executed / skipped / failed | path or — | Yes / No |
| JoSIM | executed / skipped / failed | path or — | Yes / No |
| Palace | executed / skipped / failed | path or — | Yes / No |
| Elmer FEM | executed / skipped / failed | path or — | Yes / No |

**Independent solver agreement:** PASS / FAIL / N/A (< 2 solvers)

---

## Reviewer Results

### Physics Review

**Score:** (0–100)  
**Passed:** True / False

| Severity | Finding | Recommendation |
|---|---|---|
| error / warning / info | (message) | (action) |

### Microwave Review

**Score:** (0–100)  
**Passed:** True / False

| Severity | Finding | Recommendation |
|---|---|---|
| error / warning / info | (message) | (action) |

### Fabrication Review

**Score:** (0–100)  
**Passed:** True / False

| Severity | Finding | Recommendation |
|---|---|---|
| error / warning / info | (message) | (action) |

### Measurement Review

**Score:** (0–100)  
**Passed:** True / False

| Severity | Finding | Recommendation |
|---|---|---|
| error / warning / info | (message) | (action) |

### Literature Review

**Score:** (0–100)  
**Passed:** True / False

| Severity | Finding | Recommendation |
|---|---|---|
| error / warning / info | (message) | (action) |

---

## Blocking Issues

Blocking issues prevent signoff and must be resolved before re-review.

1. (blocking finding message — error severity only)
2. ...

---

## Repair Suggestions

For each blocking issue, the suggested repair:

1. (issue): (suggested fix)
2. ...

---

## Auto-Repair History

| Iteration | Score | Approved | Blockers |
|---|---|---|---|
| 1 | (score) | True/False | (list) |
| 2 | (score) | True/False | (list) |
| ... | | | |

**Final status:** accepted / failed  
**Reason if failed:** (iteration budget exhausted / repair stalled / hard stop)

---

## Proven Values

Physical values with full provenance that survived all reviewer checks:

| Quantity | Value | Unit | Method | Source | Confidence |
|---|---|---|---|---|---|
| Z0 | 50.0 | Ω | conformal CPW | extracted | 0.86 |
| Ic | 0.658 | µA | geometry_extracted | sidecar | 0.92 |
| Lj | 500.0 | pH | calculated | Ambegaokar-Baratoff | 0.90 |
| f0 | 6.0 | GHz | simulated | JosephsonCircuits.jl | 0.95 |

---

## Limitations

(Explicit list of what was not verified and why)

- Palace eigenmode not run: Palace executable not found.
- openEMS FDTD not run: Octave not installed.
- Qiskit Metal backend skipped: PySide2 incompatible with Python 3.12.

---

## Next Actions

(Explicit list of what the engineer must do to advance the signoff level)

1. Install Octave to enable openEMS FDTD execution (→ Level 4/5).
2. Run Palace eigenmode solver for independent resonance verification (→ Level 5).
3. Import VNA measurement data and run `fit_measurement()` (→ Level 6).
