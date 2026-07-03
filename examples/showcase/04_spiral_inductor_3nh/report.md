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

- Status: **SKIPPED_SOLVER_ABSENT**
- Simulation status: **SKIPPED_SOLVER_ABSENT**
- Prepared FasterCap files: **yes**
- Solver executed: **no**
- Physics verified: **no**
- Evidence status: **SKIPPED_SOLVER_ABSENT**
- inductance: SKIPPED_SOLVER_ABSENT — solver not installed; no physics verification was performed
- Analytical capacitance: `3.0 pF`
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

- `capacitance_result`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\extraction\capacitance_result.json`
- `gds`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.gds`
- `intent`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\intent.json`
- `klayout_readback`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\klayout_readback.json`
- `layout`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\layout.json`
- `optimization`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\optimization.json`
- `png`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.png`
- `simulation`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\simulation\simulation.json`
- `simulation_legacy`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\simulation.json`
- `svg`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.svg`
- `verification`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\verification.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
