# Research test-chip tile, 2 mm x 2 mm

**Target.** Multi-device comparison tile (IDC + CPW + spiral + marks + title)

## Prompt

```text
Create a 2 mm by 2 mm research test chip tile containing a 0.6 pF IDC, a 50 ohm CPW line, a spiral inductor, alignment marks, port labels, and a title text label.
```

## Parsed intent

- Component: `TestChip`
- Technology: `generic_2metal`
- Targets: `{"capacitance_pf": 0.6, "impedance_ohm": 50.0}`
- Constraints: `{}`

## Layout DSL summary

- DSL component: `TestChip` (schema v1.0)
- Parameters: `{"idc_finger_pairs": 20, "cpw_center_width_um": 10.0, "cpw_gap_um": 5.983, "spiral_turns": 4, "spiral_outer_dimension_um": 123.6974, "spiral_trace_width_um": 4.0, "spiral_spacing_um": 2.0, "tile_width_um": 2000.0, "tile_height_um": 2000.0}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `TestChip_0d4392ba`
- Bounding box: `{"width": 2000.0, "height": 2000.0}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 71, "63/0": 120}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (21/22 checks passed)

## Simulation preparation

- Solver: `none`
- Prepared input artifacts: `[]`

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `ANALYTICAL_ONLY`
- **Confidence:** `ANALYTICAL`
- Evidence id: `209c3057e9809607dcfe30a0dad5b742`
- Analysis scope: `full_tile`
- Extracted geometry: **none** — no value was extracted from this run

**NOT_FABRICATION_READY.**
<!-- END GENERATED: evidence-status -->

## Tile sub-block evidence

- Full-tile solver executed: **False**
- Full-tile status: **NOT_MODELED**
- This is a layout integration candidate with sub-block evidence, not a full-chip EM-verified design. Inter-block coupling, package, transitions, and whole-tile modes are not modeled.

- **IDC** sub-block: `SIMULATION_EXECUTED` via `FasterCap` — FasterCap extraction of the geometry-identical IDC sub-block; extracted `0.6973109999999999` vs target `0.6` (mutual_capacitance_pf); error `16.218%` (tolerance `5.0%`); within tolerance: **False**
- **CPW** sub-block: `SKIPPED_SOLVER_ABSENT` via `openEMS` — openEMS preparation for the geometry-identical CPW sub-block
- **SpiralInductor** sub-block: `SIMULATION_EXECUTED` via `fasthenry` — FastHenry extraction of the geometry-identical spiral sub-block; no tile prompt target
- **Resonator** sub-block: `SKIPPED_SOLVER_ABSENT` via `openEMS` — Nominal 6 GHz resonator reference sub-block; not embedded in the current tile geometry
- **AlignmentMarksAndLabels** sub-block: `GEOMETRY_ONLY` via `none` — Alignment marks and title labels in the assembled tile

Full-tile EM solve status: **NOT EXECUTED**. Sub-block evidence above is not a full-tile verification; alignment marks, title, inter-block coupling, package, transitions, and whole-tile modes are not modeled.

## Limitation

No full-tile solver ran. The tile map records exact-parameter sub-block execution or preparation without promoting it to tile verification. Not fabrication-ready.

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
- [`tile_simulation_map.json`](tile_simulation_map.json) — sub-block scope map
- [`extraction/`](extraction/) — solver inputs and solver-owned outputs (when executed)

Regenerate with: `uv run python scripts/generate_showcase_examples.py --force`
