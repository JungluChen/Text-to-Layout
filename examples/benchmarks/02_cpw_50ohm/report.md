# Layout Report - CPW

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `122.0000 um x 1000.0000 um`
- Polygons: `3`
- Ports: `6`

## Target and analytical model

- Model: Conformal-mapping CPW (Simons/Hilberg) + λ/4 transmission-line theory
- Target `impedance_ohm`: `50.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `eps_eff`: `6.45`
- Estimate `estimated_z0_ohm`: `50.04`
- Estimate `scikit_rf_z0_ohm`: `50.0083`
- Estimate `scikit_rf_eps_eff`: `6.449543`
- Estimate `analytical_backend`: `scikit-rf CPW (Ghione/Naldi)`
- Estimate `target_z0_ohm`: `50.0`
- Estimate `proposed_gap_um_for_target`: `5.983`
- Estimate `proposed_gap_meets_min_spacing`: `True`

## Verification

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
- `PASS` output_json_exists
- `PASS` output_png_exists
- `PASS` output_layout_dsl_exists
- `PASS` output_verification_exists
- `PASS` output_evidence_exists
- `PASS` output_analytical_estimate_exists
- `PASS` output_simulation_plan_exists
- `PASS` output_report_exists
- `PASS` klayout_gds_readback

## Artifacts

- `gds`: `examples\benchmarks\02_cpw_50ohm\output.gds`
- `svg`: `examples\benchmarks\02_cpw_50ohm\output.svg`
- `json`: `examples\benchmarks\02_cpw_50ohm\output.json`
- `png`: `examples\benchmarks\02_cpw_50ohm\output.png`
- `layout_dsl`: `examples\benchmarks\02_cpw_50ohm\layout.json`
- `verification`: `examples\benchmarks\02_cpw_50ohm\verification.json`
- `evidence`: `examples\benchmarks\02_cpw_50ohm\evidence.md`
- `analytical_estimate`: `examples\benchmarks\02_cpw_50ohm\analytical_estimate.md`
- `simulation_plan`: `examples\benchmarks\02_cpw_50ohm\simulation_plan.md`
- `report`: `examples\benchmarks\02_cpw_50ohm\report.md`

## Simulation status

Simulation readiness is Level 2 (open-source simulation input prepared). No EM solver was executed; the analytical estimate remains a design starting point only.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.
