# Text-to-Layout Report - QuarterWaveResonator

## User requirement

`Create a 6 GHz quarter-wave resonator on silicon with a weakly coupled input line, open end, shorted end, and port labels.`

## Parsed intent

- Component: `QuarterWaveResonator`
- Topology: `QuarterWaveResonator`
- Target frequency: `6.0 GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `QuarterWaveResonator`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `QuarterWaveResonator`
- Geometry role: `QuarterWaveResonator`
- Polygons: `8`
- Ports: `RF_IN, RF_OUT, GND_TOP_IN, GND_TOP_OUT, GND_BOTTOM_IN, GND_BOTTOM_OUT`
- SQUID-equivalent placeholder: `not requested`

## Verification results

- Geometry verification: **PASS**
- `PASS` component_generated
- `PASS` positive_dimensions
- `PASS` minimum_width
- `PASS` minimum_gap
- `PASS` layer_exists
- `PASS` bounding_box
- `PASS` ports_exist
- `PASS` explicit_rf_ground_ports
- `PASS` resonator_open_short_boundaries
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Resonance frequency is an analytical estimate only. EM extraction is required before fabrication.
- `PASS` research_evidence
- `PASS` simulation_workflow_documented
- `PASS` gdsfactory_component_sanity
- `PASS` output_gds_exists
- `PASS` output_svg_exists
- `PASS` output_png_exists
- `PASS` output_layout_dsl_exists
- `PASS` output_verification_exists
- `PASS` output_evidence_exists
- `PASS` output_analytical_estimate_exists
- `PASS` output_simulation_plan_exists
- `PASS` output_report_exists
- `PASS` klayout_gds_readback

<!-- BEGIN GENERATED: evidence-status -->

## Evidence status

<!-- Generated from evidence/canonical.json. Do not edit by hand. -->

- **Status:** `SIMULATION_INVALID`
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

**NOT_FABRICATION_READY.**
<!-- END GENERATED: evidence-status -->

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## What is verified

- Overall status: **NOT VERIFIED**
- Deterministic layout and geometry checks: **verified**
- Geometry-level resonance_frequency output was parsed from an executed solver.

## What is only prepared

- Circuit backends without executed evidence: `none`

## Not yet supported

- Full nonlinear pumped JPA gain, saturation, noise, and signal-idler verification.
- Foundry-qualified Josephson-junction geometry and process DRC.
- Gain is not checked because real pump, signal, and idler data are absent.

## Artifacts

- `capacitance_result`: `extraction/capacitance_result.json`
- `gds`: `output.gds`
- `intent`: `intent.json`
- `klayout_readback`: `klayout_readback.json`
- `layout`: `layout.json`
- `openems_result`: `openems_result.json`
- `optimization`: `optimization.json`
- `png`: `output.png`
- `simulation`: `simulation/simulation.json`
- `simulation_legacy`: `simulation.json`
- `svg`: `output.svg`
- `verification`: `verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
