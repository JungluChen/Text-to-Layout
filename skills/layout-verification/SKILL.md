---
name: layout-verification
description: Verify IC layout DSL, geometry, process rules, ports, exported artifacts, evidence, and simulation planning. Use before accepting or exporting any generated GDS candidate and when diagnosing a failed benchmark.
---

# Layout verification

Run verification in two stages: pre-export geometry checks, then post-export artifact checks.

## Pre-export checks

- Required parameters exist and Pydantic accepts them.
- All dimensions are positive and units are explicit in field names or schema.
- Minimum width and gap meet the selected technology or stricter DSL override.
- Every geometry layer has a valid GDS mapping.
- Bounding box is finite, positive, and plausible for the target.
- Required ports exist with valid layer, width, position, and orientation.
- The gdsfactory component contains geometry and writes a readable GDS.
- Research includes equations, assumptions, references, and a simulation plan.

Block export when any required check fails. Return measured values, limits, and actionable error messages.

## Post-export checks

Confirm every requested output is non-empty. Require Layout DSL provenance, `verification.json`, `analytical_estimate.md`, `simulation_plan.md`, `evidence.md`, and `report.md`. Confirm the report states whether simulation was prepared, executed, failed, or skipped.

For READY benchmarks, run `python scripts/check_benchmarks.py`. For TODO benchmarks, require `TODO.md`, forbid `output.*`, and reject PASS language.

Warnings do not become evidence. In particular, an analytical capacitance estimate may pass geometry verification while still warning that EM extraction is required.
