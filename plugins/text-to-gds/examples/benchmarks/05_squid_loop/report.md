# Layout Report - SQUID

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `40.0000 um x 96.0000 um`
- Polygons: `12`
- Ports: `2`

## Target and analytical model

- Model: DC-SQUID loop, first-principles flux quantization
- Target `loop_area_um2`: `400.0`
- Estimate `flux_quantum_Wb`: `2.067833848e-15`
- Estimate `loop_area_um2`: `400.0`
- Estimate `field_modulation_period_uT`: `5.1696`

## Verification

- `PASS` component_generated
- `PASS` positive_dimensions
- `PASS` minimum_width
- `PASS` minimum_gap
- `PASS` layer_exists
- `PASS` bounding_box
- `PASS` ports_exist
- `PASS` squid_symmetry_junctions_loop_area
- `WARN` foundry_junction_stack: Generic JJ placeholders are not fabrication-ready without foundry layer and overlap rules.
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Flux modulation period is an analytical estimate only. EM extraction is required before fabrication.
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

- `gds`: `examples\benchmarks\05_squid_loop\output.gds`
- `svg`: `examples\benchmarks\05_squid_loop\output.svg`
- `json`: `examples\benchmarks\05_squid_loop\output.json`
- `png`: `examples\benchmarks\05_squid_loop\output.png`
- `layout_dsl`: `examples\benchmarks\05_squid_loop\layout.json`
- `verification`: `examples\benchmarks\05_squid_loop\verification.json`
- `evidence`: `examples\benchmarks\05_squid_loop\evidence.md`
- `analytical_estimate`: `examples\benchmarks\05_squid_loop\analytical_estimate.md`
- `simulation_plan`: `examples\benchmarks\05_squid_loop\simulation_plan.md`
- `report`: `examples\benchmarks\05_squid_loop\report.md`

## Simulation status

Simulation readiness is Level 1 (geometry generated and verified). No EM solver was executed; the analytical estimate remains a design starting point only.

## Limitations

- Junction polygons are process placeholders; critical current requires Jc and overlap data.
- The generic JJ layer is not a qualified base/counter-electrode stack.
