# Layout Report - IDC

- Verification: **PASS**
- Technology: `generic_2metal`
- Bounding box: `262.0000 um x 304.0000 um`
- Polygons: `46`
- Ports: `2`

## Target and analytical model

- Model: Bahl/Alley quasi-static interdigital capacitor
- Target `capacitance_pf`: `0.6`
- Target `frequency_ghz`: `6.0`
- Estimate `substrate_eps_r`: `11.9`
- Estimate `eps_re`: `6.45`
- Estimate `estimated_capacitance_pf`: `0.6983`
- Estimate `target_capacitance_pf`: `0.6`
- Estimate `estimate_vs_target_pct`: `16.4`
- Estimate `proposed_finger_pairs_for_target`: `20`
- Estimate `proposed_estimate_pf`: `0.6319`

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

- `gds`: `examples\benchmarks\01_idc_0p6pf\output.gds`
- `svg`: `examples\benchmarks\01_idc_0p6pf\output.svg`
- `json`: `examples\benchmarks\01_idc_0p6pf\output.json`
- `png`: `examples\benchmarks\01_idc_0p6pf\output.png`
- `layout_dsl`: `examples\benchmarks\01_idc_0p6pf\layout.json`
- `verification`: `examples\benchmarks\01_idc_0p6pf\verification.json`
- `evidence`: `examples\benchmarks\01_idc_0p6pf\evidence.md`
- `analytical_estimate`: `examples\benchmarks\01_idc_0p6pf\analytical_estimate.md`
- `simulation_plan`: `examples\benchmarks\01_idc_0p6pf\simulation_plan.md`
- `report`: `examples\benchmarks\01_idc_0p6pf\report.md`

## Simulation status

Simulation readiness is Level 2 (open-source simulation input prepared). No EM solver was executed; the analytical estimate remains a design starting point only.

## Limitations

- The Bahl model is quasi-static; accuracy depends on stack and geometry and requires EM correlation.
- It ignores finite metal thickness, fringing at finger ends, and substrate loss tangent.
- Self-resonance and Q are NOT predicted here — an EM solve is required before fabrication.
