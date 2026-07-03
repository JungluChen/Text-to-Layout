# Text-to-Layout Report - TestChip

## User requirement

`Create a 2 mm by 2 mm research test chip tile containing a 0.6 pF IDC, a 50 ohm CPW line, a spiral inductor, alignment marks, port labels, and a title text label.`

## Parsed intent

- Component: `TestChip`
- Topology: `TestChip`
- Target frequency: `None GHz`
- Bandwidth: `None MHz`
- Gain target: `None dB`
- Capacitor type: `TestChip`
- Requested simulators: `none`

## First-principles sizing

- See `optimization.json` and the analytical estimate artifacts.

## Generated layout

- Layout DSL component: `TestChip`
- Geometry role: `TestChip`
- Polygons: `191`
- Ports: `IDC_P1, IDC_P2, CPW_RF_IN, CPW_RF_OUT, CPW_GND_L_IN, CPW_GND_L_OUT, CPW_GND_R_IN, CPW_GND_R_OUT, SP_P1, SP_P2`
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
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Per-sub-device estimates (see sub_devices) is an analytical estimate only. EM extraction is required before fabrication.
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

- Status: **ANALYTICAL_ONLY**
- Simulation status: **ANALYTICAL_ONLY**
- Prepared FasterCap files: **yes**
- Solver executed: **no**
- Physics verified: **no**
- Evidence status: **ANALYTICAL_ONLY**
- geometry: ANALYTICAL_ONLY — estimate None (per-sub-device analytical estimates (see research report)); this is NOT a solver result
- Analytical capacitance: `None pF`
- Solver-extracted capacitance: `not available`
- Circuit simulators are not capacitance-extraction evidence.

- Legacy simulation status: **ANALYTICAL_ONLY**
- Only an analytical formula was used. **This is not a solver result.**

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
