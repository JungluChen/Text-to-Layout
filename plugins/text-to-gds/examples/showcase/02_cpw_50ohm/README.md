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

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `PHYSICS_VERIFIED`
- **Confidence:** `VERIFIED`
- Evidence id: `525c5c091c57223099a616761124d031`
- Analysis scope: `through_line_center_conductor`
- Solver: `openEMS+scikit-rf openEMS via Octave frontend`
- Runtime: `1223.2` s (return code `0`)
- Extracted characteristic_impedance: `49.712535` ohm
- Target: `50.000000` ohm
- Error: `-0.575%` (tolerance `±5.00%`)
- Analytical characteristic_impedance: `50.0` ohm (Conformal-mapping CPW (Simons/Hilberg) + λ/4 transmission-line theory) — an estimate, **not** a solver result
- Convergence: `fdtd_energy_decay_and_excitation_support`, converged: **True**
  - no mesh-refinement study was performed; only time-domain convergence is evidenced

### Superseded claim (audit history — not an active result)

- Withdrawn status: `CHARACTERISTIC_IMPEDANCE_EXTRACTED`
- Withdrawn value: `49.88827755069874` ohm
- Why withdrawn: not reproducible from the committed openems_result.s2p. Re-extracting at the design frequency gives 49.712535 ohm; sample_frequency_ghz, s11_magnitude and return_loss_db all reproduce exactly, so the file and the parser agree and only this number is stale. No output hash existed at the time, so it cannot be established whether the Touchstone file or the impedance estimator changed.
- Provenance gap: `solver_executable_hash_unrecorded`

**NOT_FABRICATION_READY.**
<!-- END GENERATED: evidence-status -->

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
