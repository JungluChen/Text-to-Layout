# Evidence — SQUID

**Model:** DC-SQUID loop, first-principles flux quantization
**Target:** loop_area_um2 = 400.0

## Analytical estimate

- `flux_quantum_Wb` = 2.067833848e-15
- `loop_area_um2` = 400.0
- `field_modulation_period_uT` = 5.1696

## First-principles equations

- **Flux quantum:** `Phi_0 = h / 2e = 2.07e-15 Wb`
- **Field modulation period:** `dB = Phi_0 / A_loop`
- **Screening parameter:** `beta_L = 2 * L_loop * Ic / Phi_0`

## Proposed parameters (from target)

```json
{
  "loop_inner_width_um": 20.0,
  "loop_inner_height_um": 20.0,
  "trace_width_um": 4.0,
  "junction_gap_um": 2.0,
  "junction_width_um": 2.0,
  "pad_width_um": 40.0,
  "pad_height_um": 30.0,
  "metal": "M1",
  "junction_layer": "JJ"
}
```

## Design rationale

- Loop area sets the field modulation period.
- Matched junction critical currents are required for symmetric modulation.

## Assumptions

- Two symmetric junction placeholders in a thin-film superconducting loop.
- Generic technology 'generic_2metal'; no foundry junction stack is implied.

## Limitations

- Junction polygons are process placeholders; critical current requires Jc and overlap data.
- The generic JJ layer is not a qualified base/counter-electrode stack.

## Recommended simulation

- **loop_inductance:** FastHenry or Elmer after a foundry stack and conductor thickness are supplied.
- **junction_response:** Use a validated Josephson circuit solver with extracted Ic and L.

## References

- J. Clarke & A. I. Braginski (eds.), 'The SQUID Handbook', Vol. 1, Wiley, 2004.
- M. Tinkham, 'Introduction to Superconductivity', 2nd ed., Dover, 2004. — Flux quantization and Josephson relations.
