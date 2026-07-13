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

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Scientific validation level:** `SIMULATION_INVALID`
- **Target tolerance passed:** `None`
- **Confidence:** `NONE`
- Evidence id: `b5e514d1281a9d0fd74c2f47cbb42128`
- Analysis scope: `resonator_plus_coupler`
- Solver: `openEMS+scikit-rf openEMS via Octave frontend`
- Runtime: `1011.4` s (return code `0`)
- Extracted resonance_frequency: **none** — no value was extracted from this run
- Analytical resonance_frequency: `6.0` GHz (Quarter-wave CPW hanger (Simons/Pozar initial model)) — an estimate, **not** a solver result
- Convergence: `fdtd_energy_decay_and_excitation_support`, converged: **True**
  - no mesh-refinement study was performed; only time-domain convergence is evidenced
- **Invalidation reason:** openems_result.s2p: 401/401 S-parameter samples are non-finite (NaN/Inf) — the solver produced no usable output (typically zero injected port energy); refusing to extract numbers from it

### Superseded claim (audit history — not an active result)

- Withdrawn status: `RESONANCE_FREQUENCY_EXTRACTED`
- Withdrawn value: `3.0` GHz
- Why withdrawn: 3.0 GHz is the first point of the sweep, not a resonance. An argmin over all-NaN magnitudes returns index 0 because every NaN comparison is False, so the sweep's lower bound was reported as 'the resonance'.
- Provenance gap: `solver_executable_hash_unrecorded`

- **Fabrication readiness:** `NOT_FABRICATION_READY` — no DRC/LVS signoff has been performed for this showcase.
<!-- END GENERATED: evidence-status -->

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
