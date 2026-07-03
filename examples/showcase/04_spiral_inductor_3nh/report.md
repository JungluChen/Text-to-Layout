# Text-to-Layout Report - SpiralInductor

## User requirement

`Create a compact planar spiral inductor targeting 3 nH with 4 turns, 4 um trace width, 2 um spacing, and two labeled ports.`

## Parsed intent

- Component: `SpiralInductor`
- Topology: `SpiralInductor`
- Target frequency: `None GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `SpiralInductor`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `SpiralInductor`
- Geometry role: `SpiralInductor`
- Polygons: `18`
- Ports: `P1, P2`
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
- `PASS` spiral_centerline_and_terminals
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Inductance is an analytical estimate only. EM extraction is required before fabrication.
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
- Prepared fasthenry files: **yes**
- Solver executed: **yes**
- Physics verified: **no**
- Evidence status: **SIMULATION_EXECUTED**
- inductance: SIMULATION_EXECUTED — fasthenry extracted 2.751263754746667 nH vs target 3.0 nH; tolerance not met or not compared — NOT physics verified
- Analytical inductance: `3.0 nH`
- Solver-extracted inductance: `2.751263754746667 nH`
- Circuit simulators are not inductance-extraction evidence.

- Extracted inductance: `2.75126 nH`
- Target inductance: `3 nH`
- Error: `-8.29%`
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
- Geometry-level inductance output was parsed from an executed solver.

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
- `optimization`: `optimization.json`
- `png`: `output.png`
- `simulation`: `simulation\simulation.json`
- `simulation_legacy`: `simulation.json`
- `svg`: `output.svg`
- `verification`: `verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
