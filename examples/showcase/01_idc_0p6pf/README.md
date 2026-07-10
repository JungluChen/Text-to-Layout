# IDC capacitor, 0.6 pF

**Target.** 0.6 pF interdigitated capacitor for a lumped LC / JPA front end

## Prompt

```text
Create a 0.6 pF interdigitated capacitor on silicon at 6 GHz with 2 um minimum gap, 4 um finger width, and two RF ports.
```

## Parsed intent

- Component: `IDC`
- Technology: `generic_2metal`
- Targets: `{"capacitance_pf": 0.6, "frequency_ghz": 6.0}`
- Constraints: `{"min_gap_um": 2.0, "min_width_um": 4.0}`

## Layout DSL summary

- DSL component: `IDC` (schema v1.0)
- Parameters: `{"finger_pairs": 20, "finger_width_um": 4.0, "gap_um": 2.0, "overlap_um": 220.8512, "bus_width_um": 25.0, "metal_layer": "M1"}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `IDC_4beb67ec`
- Bounding box: `{"width": 238.0, "height": 274.851}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 42}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (24/25 checks passed)

## Simulation preparation

- Solver: `FasterCap`
- Prepared input artifacts: `["list_file", "manifest", "panel_file", "result", "solver_stderr", "solver_stdout"]`

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `PHYSICS_VERIFIED`
- **Confidence:** `VERIFIED`
- Evidence id: `15feda89b0a0e45314a933af087d234b`
- Analysis scope: `idc_electrodes`
- Solver: `FasterCap Running FasterCap version 6.0.7`
- Runtime: `18.3` s (return code `0`)
- Extracted capacitance: `0.598641` pF
- Target: `0.600000` pF
- Error: `-0.227%` (tolerance `±5.00%`)
- Analytical capacitance: `0.5583` pF (Bahl/Alley quasi-static closed form (Bahl 2003, Alley 1970)) — an estimate, **not** a solver result
- Convergence: `fastercap_automatic_refinement`, converged: **True**
  - solver refined its panel discretisation until the relative change fell below 1% (-a flag), and exited 0
- Provenance gap: `solver_executable_hash_unrecorded`

- **Fabrication readiness:** `NOT_FABRICATION_READY` — no DRC/LVS signoff has been performed for this showcase.
<!-- END GENERATED: evidence-status -->

## Limitation

Effective-medium electrostatic model; no self-resonance, loss, or finite-thickness model. Not fabrication-ready.

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
