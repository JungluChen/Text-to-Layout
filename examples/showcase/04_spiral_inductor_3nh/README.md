# Spiral inductor, 3 nH

**Target.** Compact planar spiral inductor targeting 3 nH

## Prompt

```text
Create a compact planar spiral inductor targeting 3 nH with 4 turns, 4 um trace width, 2 um spacing, and two labeled ports.
```

## Parsed intent

- Component: `SpiralInductor`
- Technology: `generic_2metal`
- Targets: `{"inductance_nh": 3.0}`
- Constraints: `{}`

## Layout DSL summary

- DSL component: `SpiralInductor` (schema v1.0)
- Parameters: `{"turns": 4, "outer_dimension_um": 129.168, "trace_width_um": 4.0, "spacing_um": 2.0, "thickness_um": 0.2}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `SpiralInductor_9b0396ff`
- Bounding box: `{"width": 129.168, "height": 129.168}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 18}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (22/23 checks passed)

## Simulation preparation

- Solver: `fasthenry`
- Prepared input artifacts: `["input", "manifest", "result", "solver_stderr", "solver_stdout", "zc_matrix"]`

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `SIMULATION_EXECUTED`
- **Confidence:** `SIMULATED`
- Evidence id: `731a7af91767c62aaf145ef32dc1d176`
- Analysis scope: `spiral_winding`
- Solver: `fasthenry FastHenry 3.0.1`
- Runtime: `0.2` s (return code `0`)
- Extracted inductance: `2.958308` nH
- Target: `3.000000` nH
- Error: `-1.390%` (tolerance `±5.00%`)
- Analytical inductance: `3.2227` nH (Modified-Wheeler / Mohan planar spiral inductor) — an estimate, **not** a solver result
- Convergence: `none_recorded`, converged: **False**
  - FastHenry ran once at the deck's default single-filament discretisation: the deck declares no nhinc/nwinc, and no refinement sweep exists. Current crowding in a spiral is unresolved, so no convergence is evidenced.
- Provenance gap: `solver_executable_hash_unrecorded`

- **Fabrication readiness:** `NOT_FABRICATION_READY` — no DRC/LVS signoff has been performed for this showcase.
<!-- END GENERATED: evidence-status -->

## Limitation

FastHenry execution is environment-dependent; conductivity and thickness remain generic process assumptions. Not fabrication-ready.

## Files

- [`prompt.txt`](prompt.txt)
- [`intent.json`](intent.json)
- [`layout.json`](layout.json)
- [`output.gds`](output.gds)
- [`output.svg`](output.svg)
- [`output.png`](output.png)
- [`verification.json`](verification.json)
- [`klayout_readback.json`](klayout_readback.json)
- [`simulation.json`](simulation.json)
- [`optimization.json`](optimization.json)
- [`workflow_trace.json`](workflow_trace.json)
- [`report.md`](report.md)
- [`extraction/`](extraction/) — solver inputs and solver-owned outputs (when executed)

Regenerate with: `uv run python scripts/generate_showcase_examples.py --force`
