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
- Top cell: `IDC_a499a822`
- Bounding box: `{"width": 238.0, "height": 274.851}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 42}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (24/25 checks passed)

## Simulation preparation

- Solver: `FasterCap`
- Prepared input artifacts: `["list_file", "manifest", "panel_file", "result", "solver_stderr", "solver_stdout"]`

## Solver execution

- Solver executed: **yes**
- Extracted capacitance: `0.598641` pF

## Target comparison

- Target: `0.6` pF; extracted: `0.598641` pF
- Error: `-0.226%` (tolerance `5.0%`)
- Within tolerance: **True**

## Evidence status

- **PHYSICS_VERIFIED**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

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
