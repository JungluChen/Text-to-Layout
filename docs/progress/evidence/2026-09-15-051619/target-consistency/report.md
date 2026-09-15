# Text-to-Layout Report - QuarterWaveResonator

## User requirement

`Design for 6 quarter_wave_frequency_ghz with typed requirements`

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

- Geometry verification: **FAIL**
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
- `PASS` independent_gds_readback
- `FAIL` requirements_target: analytical estimate: error=2.2112920383676737e-07%, tolerance=1e-12%

## Extraction status

- Status: **EXTRACTION_INPUT_PREPARED**
- Simulation status: **EXTRACTION_INPUT_PREPARED**
- Prepared openEMS files: **yes**
- Solver executed: **no**
- Physics verified: **no**
- Evidence status: **SIMULATION_INPUT_PREPARED**
- resonance_frequency: SIMULATION_INPUT_PREPARED — solver input files exist; no physics verification was performed
- Analytical resonance_frequency: `6.0 GHz`
- Solver-extracted resonance_frequency: `not available`
- Circuit simulators are not resonance_frequency-extraction evidence.

- Legacy simulation status: **SIMULATION_INPUT_PREPARED**
- Solver input files were prepared but the solver was not executed; **no physics verification was performed**.

## JoSIM status

- Not requested.

## PSCAN2 status

- Not requested.

## WRspice status

- Not requested.

## What is verified

- Overall status: **NOT VERIFIED**
- Deterministic layout and geometry checks: **failed**

## What is only prepared

- Circuit backends without executed evidence: `none`
- Resonance_frequency extraction input exists, but no solver result exists.

## Not yet supported

- Full nonlinear pumped JPA gain, saturation, noise, and signal-idler verification.
- Foundry-qualified Josephson-junction geometry and process DRC.
- Gain is not checked because real pump, signal, and idler data are absent.

## Artifacts

- `capacitance_result`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/extraction/capacitance_result.json`
- `design_review`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/design_review.json`
- `gds`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/output.gds`
- `intent`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/intent.json`
- `klayout_readback`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/klayout_readback.json`
- `layout`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/layout.json`
- `openems_result`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/openems_result.json`
- `optimization`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/optimization.json`
- `png`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/output.png`
- `report`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/report.md`
- `requirements`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/requirements.json`
- `requirements_verification`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/requirements_verification.json`
- `simulation`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/simulation/simulation.json`
- `simulation_legacy`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/simulation.json`
- `svg`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/output.svg`
- `verification`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/verification.json`
- `workflow_trace`: `/Users/ludko/Desktop/text2layout/Text-to-Layout/out/daily/2026-09-15-051619/target-consistency/workflow_trace.json`

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
