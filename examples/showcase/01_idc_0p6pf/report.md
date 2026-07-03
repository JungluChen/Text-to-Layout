# Text-to-Layout Report - IDC

## User requirement

`Create a 0.6 pF interdigitated capacitor on silicon at 6 GHz with 2 um minimum gap, 4 um finger width, and two RF ports.`

## Parsed intent

- Component: `IDC`
- Topology: `IDC`
- Target frequency: `6.0 GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `IDC`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `IDC`
- Geometry role: `idc`
- Polygons: `42`
- Ports: `P1, P2`
- SQUID-equivalent placeholder: `not requested`

## Verification results

- Geometry verification: **PASS**
- `PASS` component_generated
- `PASS` positive_dimensions
- `PASS` minimum_width
- `PASS` minimum_gap
- `PASS` finger_count_sanity
- `PASS` layer_exists
- `PASS` bounding_box
- `PASS` ports_exist
- `PASS` idc_two_net_connectivity
- `PASS` idc_no_comb_shorts
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Capacitance is an analytical estimate only. EM extraction is required before fabrication.
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

- Status: **PHYSICS_VERIFIED**
- Simulation status: **PHYSICS_VERIFIED**
- Prepared FasterCap files: **yes**
- Solver executed: **yes**
- Physics verified: **yes**
- Evidence status: **PHYSICS_VERIFIED**
- capacitance: PHYSICS_VERIFIED — FasterCap extracted 0.598641 pF vs target 0.6 pF (error 0.23% <= 5.0%)
- Analytical capacitance: `0.5583 pF`
- Solver-extracted capacitance: `0.598641`
- Circuit simulators are not capacitance-extraction evidence.

- Extracted mutual capacitance: `0.598641 pF`
- Target capacitance: `0.6 pF`
- Error: `-0.23%`
- Tolerance: `+/-5.00%`
- Reason: extracted value is within tolerance.

- Legacy simulation status: **PHYSICS_VERIFIED**
- The solver executed, its output was parsed, and the extracted value is within tolerance of the target.

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## Closed-loop analytical tuning

- Converged: **True**
- Final parameters: `{"finger_pairs": 20, "finger_width_um": 4.0, "gap_um": 2.0, "overlap_um": 220.8512, "bus_width_um": 25.0, "metal_layer": "M1"}`
- This optimizer is analytical unless extraction iterations are recorded.

## What is verified

- Overall status: **PHYSICS_VERIFIED**
- Deterministic layout and geometry checks: **verified**
- Geometry-level capacitance output was parsed from an executed solver.

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
