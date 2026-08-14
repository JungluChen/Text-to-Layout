# Signoff Criteria

**Document class: MANUAL_DOCUMENTATION.** This is a normative contract, not an
execution or platform-status record.

Text-to-Layout signoff is evidence-level based. Higher levels require all lower
levels.

<!-- SIGNOFF_LEVEL_TABLE_BEGIN -->
| Level | Label | Requires |
| ---: | --- | --- |
| 0 | Geometry generated | GDS exists and passed layout verification. |
| 1 | DRC passed | Level 0 plus the design-rule check passed. |
| 2 | Extraction complete | Level 1 plus extraction/readback completed. |
| 3 | Analytical sanity | Level 2 plus analytical sanity checks. |
| 4 | One solver executed | Level 3 plus one valid solver-backed canonical record, or the temporary single-record `evidence=` compatibility input. |
| 5 | **Physics signoff** | Level 4 plus at least two canonical `PHYSICS_VERIFIED` records from independent solver families (distinct backends) and a passing computed agreement record for the same design hash, analysis scope, and quantity. |
| 6 | **Measurement-calibrated** | Level 5 plus a `CalibrationFile` with `synthetic=False`. |
<!-- SIGNOFF_LEVEL_TABLE_END -->

Only Level 5 or higher can be called `physics signoff`.
Only Level 6 can be called `measurement-calibrated`.

## Solver Rules

- `skipped` never counts as evidence.
- `installed` never counts as evidence.
- `binary_found` never counts as evidence.
- `input_files_prepared` never counts as evidence.
- `executed` requires a real, non-empty, content-hashed output file.
- Two runs of the same backend are one solver family and cannot establish Level 5.
- A caller-supplied `passed=true` flag is not an agreement calculation.
- Quantity-level `PHYSICS_VERIFIED` means one solver met its target; it is not
  design-level Level 5 signoff.

## Review Hard Stops

- GDS with no sidecar cannot pass extraction.
- CPW without ground-signal-ground cannot pass microwave review.
- JPA without a nonlinear JJ model cannot pass JPA review.
- Solver panels must never say `SOLVER EXECUTED` without output file evidence.
- Reports must show skipped solvers and their install steps.

## Implementation Hook

The authoritative Python evaluator is `textlayout.signoff.evaluate_signoff`
and its result schema is `textlayout.signoff.v2`. The deprecated
`text_to_gds.signoff.evaluate_signoff` projects structured evidence into the
same evaluator; its historical `solver_agreement.passed` shortcut no longer
grants Level 5. Evaluators audit existing artifacts; they do not run solvers or
generate evidence.
