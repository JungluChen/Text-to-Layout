# IDC + CPW test structure

**Target.** 0.6 pF IDC with CPW launches for on-chip measurement

## Prompt

```text
Create a test structure with a 0.6 pF IDC connected to two 50 ohm CPW feedlines, with GSG-style launch regions, ground clearance, and measurement-friendly port labels.
```

## Parsed intent

- Component: `TestStructure`
- Technology: `generic_2metal`
- Targets: `{"capacitance_pf": 0.6, "impedance_ohm": 50.0}`
- Constraints: `{}`

## Layout DSL summary

- DSL component: `TestStructure` (schema v1.0)
- Parameters: `{"finger_pairs": 20, "finger_width_um": 4.0, "gap_um": 2.0, "overlap_um": 237.362, "bus_width_um": 25.0, "feed_width_um": 10.0, "feed_gap_um": 5.983}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `TestStructure_256dc46d`
- Bounding box: `{"width": 598.0, "height": 1131.362}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 48}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (22/23 checks passed)

## Simulation preparation

- Solver: `FasterCap`
- Prepared input artifacts: `["list_file", "manifest", "panel_file", "result", "solver_stderr", "solver_stdout"]`

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `PHYSICS_VERIFIED`
- **Confidence:** `VERIFIED`
- Evidence id: `2f2dd2bd9082a2cacf6a5b402f2d9c60`
- Analysis scope: `embedded_idc_region_only`
- Solver: `FasterCap Running FasterCap version 6.0.7`
- Runtime: `2.5` s (return code `0`)
- Extracted capacitance: `0.610019` pF
- Target: `0.600000` pF
- Error: `+1.670%` (tolerance `±5.00%`)
- Analytical capacitance: `0.6` pF (Bahl/Alley quasi-static closed form (Bahl 2003, Alley 1970)) — an estimate, **not** a solver result
- Convergence: `fastercap_automatic_refinement`, converged: **True**
  - solver refined its panel discretisation until the relative change fell below 1% (-a flag), and exited 0
- Provenance gap: `solver_executable_hash_unrecorded`

**NOT_FABRICATION_READY.**
<!-- END GENERATED: evidence-status -->

## Region-level evidence

- FasterCap verification applies only to the embedded IDC extraction region. CPW launches, feedlines, and transitions are not full-wave verified unless a whole-structure openEMS execution is available.
- **embedded_idc**: `PHYSICS_VERIFIED` via `FasterCap`; FasterCap verification applies only to the embedded IDC extraction region.
- **cpw_launch_and_feed**: `SKIPPED_SOLVER_ABSENT` via `openEMS`; Standalone feed model; it excludes launch pads and the IDC transition.
- **transition_region**: `NOT_MODELED` via `not modeled`; No full-wave transition model was executed.

- Whole structure verified: **false**

## Limitation

Only the embedded IDC region is extracted; launches, feeds, and transitions are not simulated. Not fabrication-ready.

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
