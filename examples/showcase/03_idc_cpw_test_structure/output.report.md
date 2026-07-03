# Layout Report - TestStructure

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `598.0000 um x 1131.3620 um`
- Polygons: `48`
- Ports: `4`

## Target and analytical model

- Model: Bahl/Alley IDC + conformal-mapping CPW feed (composite analytical model)
- Target `capacitance_pf`: `0.6`
- Target `impedance_ohm`: `50.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `estimated_capacitance_pf`: `0.6`
- Estimate `feed_estimated_z0_ohm`: `50.0001`
- Estimate `feed_effective_permittivity`: `6.45`
- Estimate `target_capacitance_pf`: `0.6`
- Estimate `estimate_vs_target_pct`: `0.0`

## Verification

- `PASS` component_generated
- `PASS` positive_dimensions
- `PASS` minimum_width
- `PASS` minimum_gap
- `PASS` finger_count_sanity
- `PASS` layer_exists
- `PASS` bounding_box
- `PASS` ports_exist
- `PASS` geometry_min_spacing
- `WARN` analytical_estimate: Capacitance is an analytical estimate only. EM extraction is required before fabrication.
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

- `gds`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.gds`
- `svg`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.svg`
- `png`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.png`
- `layout_dsl`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.layout.json`
- `verification`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.verification.json`
- `evidence`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.evidence.md`
- `analytical_estimate`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.analytical_estimate.md`
- `simulation_plan`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.simulation_plan.md`
- `report`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\03_idc_cpw_test_structure\output.report.md`

## Simulation status

No EM solver was executed by this workflow. The analytical estimate is a design starting point only.

## Limitations

- The capacitance model covers the IDC region only; launch pads and feed traces add parasitic shunt capacitance that a real measurement must de-embed.
- The CPW feed impedance is an analytical estimate; no EM solver validates the launch-to-feed and feed-to-IDC transitions.
- No radiation, substrate loss, or self-resonance model is included.
