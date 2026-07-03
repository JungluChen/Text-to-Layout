# Solver Evidence Contract

Text-to-GDS must never report solver execution unless a real solver produced a
verifiable output file.

## Status Labels

| Label | Meaning | Can count as evidence |
|---|---|---|
| `executed` | A real solver command ran and produced the declared output file. | Yes |
| `installed` | The package or binary is available locally. | No |
| `binary_found` | An executable was found but not run for this artifact. | No |
| `input_files_prepared` | Solver input files were generated. | No |
| `skipped` | Solver was unavailable or intentionally not run. | No |
| `failed` | Solver was attempted and failed, or evidence is incomplete. | No |
| `planned` | Future integration or handoff only. | No |

## Required Executed Solver Fields

Every executed solver record must include:

- `solver`
- `version`
- `command`
- `runtime`
- `input_file`
- `output_file`
- `convergence`

For FasterCap/FastCap, `simulation_result.json` additionally requires
`solver_executed=true`, `capacitance_matrix_parsed=true`, a non-empty captured
stdout/stderr pair, `mutual_capacitance_pf`, and `target_comparison`. The
`physics_verified` field is derived from
`target_comparison.within_tolerance`; it is never accepted as an independent
claim.

The `output_file` must exist and be non-empty. Touchstone, CSV, JSON, HDF5, and
native solver logs are acceptable when the adapter documents how values were
parsed from them.

## Numeric Value Contract

Every physical numeric value in reports and signoff records must include:

- `value`
- `unit`
- `source`
- `method`
- `confidence`
- `file_path`

`source="LLM"` is invalid for physical values. Analytical values are allowed
only as estimates or sanity checks. Simulation values require solver output
files. Measurement values require imported data files such as CSV, Touchstone,
or HDF5.

## Hard Stops

- A skipped solver cannot count as evidence.
- A missing output file makes `executed` invalid.
- A generated solver deck is not solver execution.
- A rendered plot is not solver evidence unless it is derived from a validated
  solver output file.
- A report must show `SKIPPED`, `FAILED`, or `INPUT FILES PREPARED` honestly
  when execution evidence is absent.
