# Text-to-Layout Report - TestStructure

## User requirement

`Create a test structure with a 0.6 pF IDC connected to two 50 ohm CPW feedlines, with GSG-style launch regions, ground clearance, and measurement-friendly port labels.`

## Parsed intent

- Component: `TestStructure`
- Topology: `TestStructure`
- Target frequency: `None GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `TestStructure`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `TestStructure`
- Geometry role: `TestStructure`
- Polygons: `48`
- Ports: `P1, P2, GND_L, GND_R`
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
- capacitance: PHYSICS_VERIFIED — FasterCap extracted 0.610019 pF vs target 0.6 pF (error 1.67% <= 5.0%)
- Analytical capacitance: `0.6 pF`
- Solver-extracted capacitance: `0.610019`
- Circuit simulators are not capacitance-extraction evidence.

- Extracted mutual capacitance: `0.610019 pF`
- Target capacitance: `0.6 pF`
- Error: `+1.67%`
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
- Final parameters: `{"finger_pairs": 20, "finger_width_um": 4.0, "gap_um": 2.0, "overlap_um": 237.362, "bus_width_um": 25.0, "feed_width_um": 10.0, "feed_gap_um": 5.983}`
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

- `capacitance_result`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\extraction\capacitance_result.json`
- `gds`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.gds`
- `intent`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\intent.json`
- `klayout_readback`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\klayout_readback.json`
- `layout`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\layout.json`
- `optimization`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\optimization.json`
- `png`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.png`
- `simulation`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\simulation\simulation.json`
- `simulation_legacy`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\simulation.json`
- `svg`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.svg`
- `verification`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
