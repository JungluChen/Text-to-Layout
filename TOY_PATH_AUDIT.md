# Toy Path Audit

Default compile mode is now `layout_quality_mode="fabrication_real"`.

Quarantined from default GDS generation:

- `ground_plane`: ground-only coupon; no etched slots, ports, nets, or extraction target.
- `jj_ic_calibration_array`: lacks verified per-junction overlap extraction and measurement routing signoff.
- `via_chain_monitor`: not yet verified as an alternating-layer chain with extracted connectivity.
- `via_stack`: single via fragment; no complete measurement device.
- `meander_inductor`: standalone symbolic inductor fragment.
- `flux_bias_line`: standalone bias-line fragment.
- `periodically_loaded_kit_unit_cell`: research/demo unit cell, not fabrication-real signoff.
- `photonic_crystal_stwpa`: research/demo TWPA cell, not fabrication-real signoff.

Allowed in default fabrication-real mode:

- `fabrication_real_cpw_resonator` / `cpw_quarter_wave_resonator`
- `fabrication_real_manhattan_jj` / `manhattan_josephson_junction`
- `fabrication_real_dc_squid` / `dc_squid_pair`
- `cpw_straight`
- `lumped_element_jpa_seed` with `jpa_gain_status="SKIPPED"` unless an executed nonlinear solver result is supplied.

Legacy/demo calls must pass `layout_quality_mode="demo"` explicitly.
