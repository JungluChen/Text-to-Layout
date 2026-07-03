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

- Status: **SKIPPED_SOLVER_ABSENT**
- Simulation status: **SKIPPED_SOLVER_ABSENT**
- Prepared FasterCap files: **yes**
- Solver executed: **no**
- Physics verified: **no**
- Evidence status: **SKIPPED_SOLVER_ABSENT**
- characteristic_impedance: SKIPPED_SOLVER_ABSENT — solver not installed; no physics verification was performed
- Analytical capacitance: `50.0 pF`
- Solver-extracted capacitance: `not available`
- Circuit simulators are not capacitance-extraction evidence.

- Reason: FasterCap/FastCap executable not found.

- Legacy simulation status: **SKIPPED_SOLVER_ABSENT**
- The solver is not installed; solver input files were prepared but **no physics verification was performed**.

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## What is verified

- Overall status: **NOT VERIFIED**
- Deterministic layout and geometry checks: **verified**

## What is only prepared

- Circuit backends without executed evidence: `none`
- Capacitance extraction input exists, but no solver result exists.

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
- `optimization`: `optimization.json`
- `png`: `output.png`
- `simulation`: `simulation\simulation.json`
- `simulation_legacy`: `simulation.json`
- `svg`: `output.svg`
- `verification`: `verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
