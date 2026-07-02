# Acceptance — A_infeasible_5mhz_lc

**Prompt:** Design a fully on-chip passive lumped LC resonator that reaches 5 MHz.

**Verdict:** `INFEASIBLE`

## Evidence ladder

- [ ] geometry generated
- [ ] artifact generated
- [x] analytical estimate
- [ ] solver input prepared
- [ ] solver executed
- [ ] extracted and compared
- [ ] physics verified
- [ ] fabrication ready

## Analytical estimate

- `target_frequency_hz` = 5000000.0
- `required_LC_product_s2` = 1.0132118364233776e-15
- `best_comfortable_on_chip_f0_hz` = 159154943.09189534
- `best_aggressive_on_chip_f0_hz` = 50329212.10448704
- `required_L_for_C_100pF_H` = 1.0132118364233776e-05
- `LC_shortfall_factor` = 101.32118364233777

## Notes

- Required L*C = 1.013e-15 s^2 to reach 5 MHz.
- Most aggressive practical on-chip pairing (L=100 nH, C=100 pF) resonates at 50.3 MHz — 101x short in the L*C product.
- To hit 5 MHz with C=100 pF you would need L=10.13 uH, far beyond any on-chip spiral.
- No geometry, GDS, or SVG was generated; refusing to fake the layout is the pass.

## Alternatives

- Off-chip discrete inductor and/or capacitor.
- Active gm-C / gyrator (synthetic inductor) realization.
- Mechanical / crystal / ceramic resonator.
- Operate at a much higher frequency (>= 159 MHz on-chip).

## References

- S. S. Mohan et al., IEEE JSSC 34(10), 1999 — on-chip spiral inductance limits.
- I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003.
- D. M. Pozar, 'Microwave Engineering', 4th ed., Wiley, 2012 — LCR resonance.

## Status contract

- `GEOMETRY_PASS` means geometry and artifacts are valid and an analytical
  estimate exists — it is **not** a physics claim.
- `PHYSICS_VERIFIED` requires a real solver run, a parsed result, and a
  target comparison within tolerance.
- No acceptance result is ever `fabrication_ready`.
