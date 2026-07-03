# Layout Report - TestChip

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `2000.0000 um x 2000.0000 um`
- Polygons: `191`
- Ports: `10`

## Target and analytical model

- Model: Composite per-sub-device analytical models (Bahl IDC, conformal CPW, Wheeler spiral)
- Target `capacitance_pf`: `0.6`
- Target `impedance_ohm`: `50.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `idc_estimated_capacitance_pf`: `0.6319`
- Estimate `cpw_estimated_z0_ohm`: `50.0001`
- Estimate `cpw_effective_permittivity`: `6.45`
- Estimate `spiral_estimated_inductance_nh`: `3.0`

## Verification

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

## Artifacts

- `gds`: `output.gds`
- `svg`: `output.svg`
- `png`: `output.png`
- `layout_dsl`: `output.layout.json`
- `verification`: `output.verification.json`
- `evidence`: `output.evidence.md`
- `analytical_estimate`: `output.analytical_estimate.md`
- `simulation_plan`: `output.simulation_plan.md`
- `report`: `output.report.md`

## Simulation status

No EM solver was executed by this workflow. The analytical estimate is a design starting point only.

## Limitations

- This tile is a geometry-level comparison candidate; no sub-block on the tile has been simulated in place, and inter-device coupling is not modeled.
- All electrical numbers are per-sub-device analytical estimates, valid only in isolation.
- Alignment marks and the title label are lithographic aids with no electrical model.
- The tile is not fabrication-ready: process DRC, density rules, and dicing margins are not checked.
