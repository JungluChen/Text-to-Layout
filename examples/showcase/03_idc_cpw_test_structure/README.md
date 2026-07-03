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
- Top cell: `TestStructure_9f8e3598`
- Bounding box: `{"width": 598.0, "height": 1131.362}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 48}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (22/23 checks passed)

## Simulation preparation

- Solver: `FasterCap`
- Prepared input artifacts: `["list_file", "manifest", "panel_file", "result", "solver_stderr", "solver_stdout"]`

## Solver execution

- Solver executed: **yes**
- Extracted capacitance: `0.610019` pF

## Target comparison

- Target: `0.6` pF; extracted: `0.610019` pF
- Error: `1.67%` (tolerance `5.0%`)
- Within tolerance: **True**

## Evidence status

- **PHYSICS_VERIFIED**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

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
