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
- Parameters: `{"turns": 4, "outer_dimension_um": 123.6974, "trace_width_um": 4.0, "spacing_um": 2.0, "thickness_um": 0.2}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `SpiralInductor_96c1c09e`
- Bounding box: `{"width": 123.697, "height": 123.697}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 18}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (22/23 checks passed)

## Simulation preparation

- Solver: `FastHenry`
- Prepared input artifacts: `["input", "manifest"]`

## Solver execution

- Solver executed: **no**
- No solver output exists for this example; nothing electrical is claimed.

## Target comparison

- No solver-backed target comparison exists (see evidence status).

## Evidence status

- **SKIPPED_SOLVER_ABSENT**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

## Limitation

Inductance is a modified-Wheeler analytical estimate; FastHenry execution is optional/future. Not fabrication-ready.

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
