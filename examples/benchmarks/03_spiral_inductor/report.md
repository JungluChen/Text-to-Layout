# Layout Report - SpiralInductor

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `150.0000 um x 150.0000 um`
- Polygons: `18`
- Ports: `2`

## Target and analytical model

- Model: Modified-Wheeler / Mohan planar spiral inductor
- Target `inductance_nh`: `2.0`
- Estimate `turns`: `4`
- Estimate `outer_dimension_um`: `150.0`
- Estimate `inner_dimension_um`: `50.0`
- Estimate `estimated_inductance_nh`: `1.981`

## Verification

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

- `gds`: `examples\benchmarks\03_spiral_inductor\output.gds`
- `svg`: `examples\benchmarks\03_spiral_inductor\output.svg`
- `json`: `examples\benchmarks\03_spiral_inductor\output.json`
- `png`: `examples\benchmarks\03_spiral_inductor\output.png`
- `layout_dsl`: `examples\benchmarks\03_spiral_inductor\layout.json`
- `verification`: `examples\benchmarks\03_spiral_inductor\verification.json`
- `evidence`: `examples\benchmarks\03_spiral_inductor\evidence.md`
- `analytical_estimate`: `examples\benchmarks\03_spiral_inductor\analytical_estimate.md`
- `simulation_plan`: `examples\benchmarks\03_spiral_inductor\simulation_plan.md`
- `report`: `examples\benchmarks\03_spiral_inductor\report.md`

## Simulation status

Simulation readiness is Level 2 (open-source simulation input prepared). No EM solver was executed; the analytical estimate remains a design starting point only.

## Limitations

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.
