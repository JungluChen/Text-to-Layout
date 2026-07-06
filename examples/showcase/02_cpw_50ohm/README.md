# 50 ohm CPW feedline

**Target.** 50 ohm coplanar-waveguide feedline for microwave routing

## Prompt

```text
Create a 50 ohm CPW feedline on silicon at 6 GHz with ground-signal-ground geometry and labeled input/output ports.
```

## Parsed intent

- Component: `CPW`
- Technology: `generic_2metal`
- Targets: `{"frequency_ghz": 6.0, "impedance_ohm": 50.0}`
- Constraints: `{}`

## Layout DSL summary

- DSL component: `CPW` (schema v1.0)
- Parameters: `{"center_width_um": 10.0, "gap_um": 5.983, "length_um": 1000.0}`

## Generated geometry

![layout](output.png)

- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)

## KLayout readback

- Status: **PASS**
- Top cell: `CPW_1f1141d8`
- Bounding box: `{"width": 121.966, "height": 1000.0}` um
- Layers (GDS layer/datatype -> polygons): `{"1/0": 3}`
- Database unit: `0.001` um

## Verification result

- Verification: **PASS** (22/23 checks passed)

## Simulation preparation

- Solver: `openEMS+scikit-rf`
- Prepared input artifacts: `["driver", "manifest", "metrics_csv", "model", "result", "solver_stderr", "solver_stdout", "touchstone"]`

## Solver execution

- Solver executed: **yes**
- Extracted characteristic_impedance: `49.88827755069874` ohm

## Target comparison

- Target: `50.0` ohm; extracted: `49.88827755069874` ohm
- Error: `-0.223%` (tolerance `5.0%`)
- Within tolerance: **True**

## Evidence status

- **PHYSICS_VERIFIED**
- Geometry: **GEOMETRY_PASS**
- Fabrication status: **NOT_FABRICATION_READY**

## Limitation

Impedance is a conformal-mapping analytical estimate; no EM solver was executed. Not fabrication-ready.

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
