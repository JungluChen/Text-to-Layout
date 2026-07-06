# Quarter-wave CPW resonator, 6 GHz

**Target.** 6 GHz quarter-wave CPW resonator layout candidate

## Prompt

```text
Create a 6 GHz quarter-wave resonator on silicon with a weakly coupled input line, open end, shorted end, and port labels.
```

## Parsed intent

- Component: `QuarterWaveResonator`
- Technology: `generic_2metal`
- Targets: `{"frequency_ghz": 6.0}`
- Constraints: `{}`

## Layout DSL summary

- DSL component: `QuarterWaveResonator` (schema v1.0)
- Parameters: `{"center_width_um": 10.0, "gap_um": 6.0, "length_um": 4918.4652, "coupling_gap_um": 4.0}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `QuarterWaveResonator_67cd5f63`
- Bounding box: `{"width": 500.0, "height": 4988.465}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 8}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (23/24 checks passed)

## Simulation preparation

- Solver: `openEMS+scikit-rf`
- Prepared input artifacts: `["driver", "manifest", "model", "result", "solver_stderr", "solver_stdout", "touchstone"]`

## Solver execution

- Solver executed: **yes**
- Extracted resonance_frequency: `3.0` GHz

## Target comparison

- Target: `6.0` GHz; extracted: `3.0` GHz
- Error: `-50.0%` (tolerance `5.0%`)
- Within tolerance: **False**

## Evidence status

- **SIMULATION_EXECUTED**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

## Limitation

Solver executed; result is outside the declared tolerance (error -50.0%). Length uses the analytical lambda/4 estimate with effective permittivity; boundary placement and mesh convergence must be reviewed before signoff. Not fabrication-ready.

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
