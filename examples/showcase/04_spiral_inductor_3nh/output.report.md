# Layout Report - SpiralInductor

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `123.6974 um x 123.6974 um`
- Polygons: `18`
- Ports: `2`

## Target and analytical model

- Model: Modified-Wheeler / Mohan planar spiral inductor
- Target `inductance_nh`: `3.0`
- Estimate `turns`: `4`
- Estimate `outer_dimension_um`: `123.6974`
- Estimate `inner_dimension_um`: `79.6974`
- Estimate `estimated_inductance_nh`: `3.0`

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

- `gds`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.gds`
- `svg`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.svg`
- `png`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.png`
- `layout_dsl`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.layout.json`
- `verification`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.verification.json`
- `evidence`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.evidence.md`
- `analytical_estimate`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.analytical_estimate.md`
- `simulation_plan`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.simulation_plan.md`
- `report`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\04_spiral_inductor_3nh\output.report.md`

## Simulation status

No EM solver was executed by this workflow. The analytical estimate is a design starting point only.

## Limitations

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.
