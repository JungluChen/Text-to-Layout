# Evidence — SpiralInductor

**Model:** Modified-Wheeler / Mohan planar spiral inductor
**Target:** inductance_nh = 2.0

## Analytical estimate

- `turns` = 4
- `outer_dimension_um` = 150.0
- `inner_dimension_um` = 50.0
- `estimated_inductance_nh` = 1.981

## First-principles equations

- **Modified Wheeler (square):** `L = K1*mu0*n^2*d_avg / (1 + K2*rho)` — K1=2.34, K2=2.75; d_avg=(d_out+d_in)/2.
- **Fill ratio:** `rho = (d_out - d_in) / (d_out + d_in)` — Density of the winding.

## Proposed parameters (from target)

```json
{
  "turns": 4,
  "outer_dimension_um": 150.0,
  "trace_width_um": 8.0,
  "spacing_um": 6.0,
  "thickness_um": 0.2,
  "metal": "M1"
}
```

## Design rationale

- Turn count is the strongest inductance lever but raises resistance and capacitance.
- Trace width and spacing trade footprint, Q, and self-resonance.

## Assumptions

- Square planar spiral; uniform width and spacing; thin-film metal.
- Substrate eps_r = 11.9 (technology 'generic_2metal').

## Limitations

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.

## Recommended simulation

- **inductance_and_resistance:** FastHenry/FastHenry2 first; Q3D/HFSS is optional correlation.

## References

- S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee, 'Simple Accurate Expressions for Planar Spiral Inductances', IEEE JSSC 34(10) (1999) 1419. — Modified-Wheeler and current-sheet expressions used here.
- H. A. Wheeler, 'Simple Inductance Formulas for Radio Coils', Proc. IRE 16 (1928) 1398.

See the repository [REFERENCES.md](../../../REFERENCES.md).

## Evidence status

- A citation supports the analytical **method/model**, not this specific layout.
- This generated geometry has **not** been EM-simulated (no solver executed).
- This generated geometry has **not** been measured.
- This generated geometry is **not** fabrication-ready.
