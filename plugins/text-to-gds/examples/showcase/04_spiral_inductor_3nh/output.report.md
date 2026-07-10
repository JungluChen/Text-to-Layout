# Layout Report - SpiralInductor

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `129.1680 um x 129.1680 um`
- Polygons: `18`
- Ports: `2`

## Target and analytical model

- Model: Modified-Wheeler / Mohan planar spiral inductor
- Target `inductance_nh`: `3.0`
- Estimate `turns`: `4`
- Estimate `outer_dimension_um`: `129.168`
- Estimate `inner_dimension_um`: `85.168`
- Estimate `estimated_inductance_nh`: `3.2227`

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

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.
