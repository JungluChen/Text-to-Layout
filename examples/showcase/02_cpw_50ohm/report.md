# Text-to-Layout Report - CPW

## User requirement

`Create a 50 ohm CPW feedline on silicon at 6 GHz with ground-signal-ground geometry and labeled input/output ports.`

## Parsed intent

- Component: `CPW`
- Topology: `CPW`
- Target frequency: `6.0 GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `CPW`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `CPW`
- Geometry role: `CPW`
- Polygons: `3`
- Ports: `RF_IN, RF_OUT, GND_L_IN, GND_L_OUT, GND_R_IN, GND_R_OUT`
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
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Characteristic impedance is an analytical estimate only. EM extraction is required before fabrication.
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

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## What is verified

- Overall status: **PHYSICS_VERIFIED**
- Deterministic layout and geometry checks: **verified**
- Geometry-level characteristic_impedance output was parsed from an executed solver.

## What is only prepared

- Circuit backends without executed evidence: `none`

## Not yet supported

- Full nonlinear pumped JPA gain, saturation, noise, and signal-idler verification.
- Foundry-qualified Josephson-junction geometry and process DRC.
- Gain is not checked because real pump, signal, and idler data are absent.

## Artifacts

- `capacitance_result`: `extraction\capacitance_result.json`
- `gds`: `output.gds`
- `intent`: `intent.json`
- `klayout_readback`: `klayout_readback.json`
- `layout`: `layout.json`
- `openems_result`: `openems_result.json`
- `optimization`: `optimization.json`
- `png`: `output.png`
- `simulation`: `simulation\simulation.json`
- `simulation_legacy`: `simulation.json`
- `svg`: `output.svg`
- `verification`: `verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
