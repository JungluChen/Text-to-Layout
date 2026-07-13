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
- `WARN` analytical_estimate: Initial sizing used an analytical model; final capacitance evidence comes from FasterCap extraction.
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

- **Scientific validation level:** `NUMERICALLY_CONVERGED`
- **Target tolerance passed:** `True`
- **Confidence:** `VERIFIED`
- Evidence id: `2f2dd2bd9082a2cacf6a5b402f2d9c60`
- Analysis scope: `embedded_idc_region_only`
- Solver: `FasterCap Running FasterCap version 6.0.7`
- Runtime: `2.5` s (return code `0`)
- Extracted capacitance: `0.610019` pF
- Target: `0.600000` pF
- Error: `+1.670%` (tolerance `±5.00%`)
- Analytical capacitance: `0.6` pF (Bahl/Alley quasi-static closed form (Bahl 2003, Alley 1970)) — an estimate, **not** a solver result
- Convergence: `fastercap_automatic_refinement`, converged: **True**
  - solver refined its panel discretisation until the relative change fell below 1% (-a flag), and exited 0
- Provenance gap: `solver_executable_hash_unrecorded`
- Missing scientific-validation gate: `solver identity hash or immutable container digest`
- Missing scientific-validation gate: `non-empty passing physical sanity checks`
- Missing scientific-validation gate: `split execution/generation environment identity`

- **Fabrication readiness:** `NOT_FABRICATION_READY` — no DRC/LVS signoff has been performed for this showcase.
<!-- END GENERATED: evidence-status -->

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

## Region-level evidence

- FasterCap verification applies only to the embedded IDC extraction region. CPW launches, feedlines, and transitions are not full-wave verified unless a whole-structure openEMS execution is available.
- **embedded_idc**: `PHYSICS_VERIFIED` via `FasterCap`; FasterCap verification applies only to the embedded IDC extraction region.
- **cpw_launch_and_feed**: `SKIPPED_SOLVER_ABSENT` via `openEMS`; Standalone feed model; it excludes launch pads and the IDC transition.
- **transition_region**: `NOT_MODELED` via `not modeled`; No full-wave transition model was executed.

- Whole structure verified: **false**

## Limitations

- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.
- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.
