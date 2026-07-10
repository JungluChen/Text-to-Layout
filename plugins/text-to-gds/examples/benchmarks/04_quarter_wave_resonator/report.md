# Layout Report - QuarterWaveResonator

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `500.0000 um x 4990.4652 um`
- Polygons: `8`
- Ports: `6`

## Target and analytical model

- Model: Quarter-wave CPW hanger (Simons/Pozar initial model)
- Target `frequency_ghz`: `6.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `eps_eff`: `6.45`
- Estimate `estimated_z0_ohm`: `50.04`
- Estimate `scikit_rf_z0_ohm`: `50.0083`
- Estimate `scikit_rf_eps_eff`: `6.449543`
- Estimate `analytical_backend`: `scikit-rf CPW (Ghione/Naldi)`
- Estimate `target_frequency_ghz`: `6.0`
- Estimate `quarter_wave_length_um`: `4918.4652`

## Verification

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

- `gds`: `examples\benchmarks\04_quarter_wave_resonator\output.gds`
- `svg`: `examples\benchmarks\04_quarter_wave_resonator\output.svg`
- `json`: `examples\benchmarks\04_quarter_wave_resonator\output.json`
- `png`: `examples\benchmarks\04_quarter_wave_resonator\output.png`
- `layout_dsl`: `examples\benchmarks\04_quarter_wave_resonator\layout.json`
- `verification`: `examples\benchmarks\04_quarter_wave_resonator\verification.json`
- `evidence`: `examples\benchmarks\04_quarter_wave_resonator\evidence.md`
- `analytical_estimate`: `examples\benchmarks\04_quarter_wave_resonator\analytical_estimate.md`
- `simulation_plan`: `examples\benchmarks\04_quarter_wave_resonator\simulation_plan.md`
- `report`: `examples\benchmarks\04_quarter_wave_resonator\report.md`

## Simulation status

Simulation readiness is Level 2 (open-source simulation input prepared). No EM solver was executed; the analytical estimate remains a design starting point only.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.
