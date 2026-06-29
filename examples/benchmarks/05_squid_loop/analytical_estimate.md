# Analytical Estimate - SQUID

- Model: **DC-SQUID loop, first-principles flux quantization**
- Status: **analytical** (not simulated or measured)

## Target

- `loop_area_um2`: `400.0`

## Calculated values

- `flux_quantum_Wb`: `2.067833848e-15`
- `loop_area_um2`: `400.0`
- `field_modulation_period_uT`: `5.1696`

## Equations

- **Flux quantum:** `Phi_0 = h / 2e = 2.07e-15 Wb`
- **Field modulation period:** `dB = Phi_0 / A_loop`
- **Screening parameter:** `beta_L = 2 * L_loop * Ic / Phi_0`

## Assumptions

- Two symmetric junction placeholders in a thin-film superconducting loop.
- Generic technology 'generic_2metal'; no foundry junction stack is implied.

## Limitations

- Junction polygons are process placeholders; critical current requires Jc and overlap data.
- The generic JJ layer is not a qualified base/counter-electrode stack.
