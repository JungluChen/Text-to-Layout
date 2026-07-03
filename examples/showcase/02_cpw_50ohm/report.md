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

## Extraction status

- Status: **SIMULATION_EXECUTED**
- Simulation status: **SIMULATION_EXECUTED**
- Prepared openEMS+scikit-rf files: **yes**
- Solver executed: **yes**
- Physics verified: **no**
- Evidence status: **SIMULATION_EXECUTED**
- characteristic_impedance: SIMULATION_EXECUTED — openEMS+scikit-rf extracted 30.917129182835225 ohm vs target 50.0 ohm; tolerance not met or not compared — NOT physics verified
- Analytical characteristic_impedance: `50.0 ohm`
- Solver-extracted characteristic_impedance: `30.917129182835225 ohm`
- Circuit simulators are not characteristic_impedance-extraction evidence.

- Extracted characteristic_impedance: `30.9171 ohm`
- Target characteristic_impedance: `50 ohm`
- Error: `-38.166%`
- Tolerance: `+/-5.00%`
- Reason: extracted value is outside tolerance.

- Legacy simulation status: **SIMULATION_EXECUTED**
- The solver executed and a value was extracted, but the result does not meet tolerance (or no target was stated) — **not physics verified**.

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## What is verified

- Overall status: **NOT VERIFIED**
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
