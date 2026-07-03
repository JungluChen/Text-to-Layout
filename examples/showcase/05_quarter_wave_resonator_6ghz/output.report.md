# Layout Report - QuarterWaveResonator

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `500.0000 um x 4988.4652 um`
- Polygons: `8`
- Ports: `6`

## Target and analytical model

- Model: Quarter-wave CPW hanger (Simons/Pozar initial model)
- Target `frequency_ghz`: `6.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `eps_eff`: `6.45`
- Estimate `estimated_z0_ohm`: `50.04`
- Estimate `analytical_backend`: `built-in Simons/Hilberg (install text-to-gds[rf] for scikit-rf correlation)`
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
- `PASS` output_png_exists
- `PASS` output_layout_dsl_exists
- `PASS` output_verification_exists
- `PASS` output_evidence_exists
- `PASS` output_analytical_estimate_exists
- `PASS` output_simulation_plan_exists
- `PASS` output_report_exists
- `PASS` klayout_gds_readback

## Artifacts

- `gds`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.gds`
- `svg`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.svg`
- `png`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.png`
- `layout_dsl`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.layout.json`
- `verification`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.verification.json`
- `evidence`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.evidence.md`
- `analytical_estimate`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.analytical_estimate.md`
- `simulation_plan`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.simulation_plan.md`
- `report`: `C:\Users\justi\Desktop\Layout\text-to-gds\examples\showcase\05_quarter_wave_resonator_6ghz\output.report.md`

## Simulation status

No EM solver was executed by this workflow. The analytical estimate is a design starting point only.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.
