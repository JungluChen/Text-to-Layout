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
- Top cell: `TestChip_7ea7a5c7`
- Bounding box: `{"width": 2000.0, "height": 2000.0}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 71, "63/0": 120}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (21/22 checks passed)

## Simulation preparation

- Solver: `none`
- Prepared input artifacts: `[]`

## Solver execution

- Solver executed: **no**
- No solver output exists for this example; nothing electrical is claimed.

## Target comparison

- No solver-backed target comparison exists (see evidence status).

## Evidence status

- **ANALYTICAL_ONLY**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

## Limitation

Geometry-level comparison tile; sub-device numbers are analytical and no solver ran on the assembled tile. Not fabrication-ready.

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
