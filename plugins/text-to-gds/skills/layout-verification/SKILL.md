---
name: layout-verification
description: Verify IC layout DSL, geometry, process rules, ports, exported artifacts, evidence, and simulation planning. Use before accepting or exporting any generated GDS candidate and when diagnosing a failed benchmark.
---

# Layout verification

Run verification in separated stages: geometry verification, artifact verification, analytical evidence, simulation evidence, physics verification, and fabrication readiness.

## Verification stages

### 1. Geometry verification

- Required parameters exist and Pydantic accepts them.
- All dimensions are positive and units are explicit in field names or schema.
- Minimum width and gap meet the selected technology or stricter DSL override.
- Every geometry layer has a valid GDS mapping.
- Bounding box is finite, positive, and plausible for the target.
- Required ports exist with valid layer, width, position, and orientation.
- The gdsfactory component contains geometry and writes a readable GDS.
- Research includes equations, assumptions, references, and a simulation plan.

Block export when any required check fails. Return measured values, limits, and actionable error messages.

### 2. Artifact verification

Confirm every requested output is non-empty. Require Layout DSL provenance, `verification.json`, `analytical_estimate.md`, `simulation_plan.md`, `evidence.md`, and `report.md`. Confirm the report states whether simulation was prepared, executed, failed, or skipped.

### 3. Analytical evidence

- Label all analytical results as `analytical_only`.
- Never claim a target is achieved without solver verification.
- State the analytical model, assumptions, and limitations.
- Compare analytical estimate against target and state error.

### 4. Simulation evidence

- `input_files_prepared` is not a simulation result.
- `executed` requires a solver-owned non-empty result file.
- Never infer solver success from a GDS or plot.
- Document solver version, input files, and output artifacts.

### 5. Physics verification

- `physics_verified` requires extracted values compared against the target.
- State tolerance and error between extracted and target values.
- Propose DSL parameter updates if error exceeds tolerance.

### 6. Fabrication readiness

- `fabrication_ready` requires process-specific DRC and expert/foundry/lab review.
- EM simulation must be executed and verified.
- Process rules must be validated against foundry specifications.

## Status vocabulary

Use explicit status labels:

| Label | Meaning |
| - | - |
| **GEOMETRY PASS** | Files exist, parameters verified, geometry is valid |
| **ANALYTICAL ONLY** | Equations computed; no solver executed |
| **SIMULATION INPUT PREPARED** | Solver input files exist; solver not executed |
| **SIMULATION EXECUTED** | Solver ran and produced non-empty output file |
| **PHYSICS VERIFIED** | Extracted values compared against target with tolerance |
| **FABRICATION READY** | Process-specific DRC, EM simulation, and expert review complete |

## Benchmark checks

For READY benchmarks, run `python scripts/check_benchmarks.py`. For TODO benchmarks, require `TODO.md`, forbid `output.*`, and reject PASS language.

Warnings do not become evidence. In particular, an analytical capacitance estimate may pass geometry verification while still warning that EM extraction is required.
