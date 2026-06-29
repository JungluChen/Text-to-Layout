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

Confirm every requested output is non-empty. Require Layout DSL provenance, `verification.json`, `evidence.md`, and `report.md`. Confirm the report states whether simulation was executed or only planned.

Warnings do not become evidence. In particular, an analytical capacitance estimate may pass geometry verification while still warning that EM extraction is required.
