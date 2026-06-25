# Signoff Criteria

Text-to-GDS signoff is evidence-level based. Higher levels require all lower
levels.

| Level | Name | Required evidence |
|---:|---|---|
| 0 | Geometry generated | GDS file exists. |
| 1 | DRC passed | Level 0 plus DRC report with `status="passed"`. |
| 2 | Extraction complete | Level 1 plus sidecar and `extraction.json`. |
| 3 | Analytical sanity passed | Level 2 plus analytical checks and valid value records. |
| 4 | One solver executed | Level 3 plus one real solver output file. |
| 5 | Physics signoff | Level 4 plus two independent solvers agreeing within tolerance. |
| 6 | Measurement-calibrated | Level 5 plus imported measurement data and fit result. |

Only Level 5 or higher can be called `physics signoff`.
Only Level 6 can be called `measurement-calibrated`.

## Solver Rules

- `skipped` never counts as evidence.
- `installed` never counts as evidence.
- `binary_found` never counts as evidence.
- `input_files_prepared` never counts as evidence.
- `executed` requires a real output file.

## Review Hard Stops

- GDS with no sidecar cannot pass extraction.
- CPW without ground-signal-ground cannot pass microwave review.
- JPA without a nonlinear JJ model cannot pass JPA review.
- Solver panels must never say `SOLVER EXECUTED` without output file evidence.
- Reports must show skipped solvers and their install steps.

## Implementation Hook

The Python evaluator is `text_to_gds.signoff.evaluate_signoff`. It audits
existing artifacts; it does not run solvers or generate evidence.

