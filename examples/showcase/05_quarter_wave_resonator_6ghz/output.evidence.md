# Evidence — QuarterWaveResonator

**Model:** Quarter-wave CPW hanger (Simons/Pozar initial model)
**Target:** frequency_ghz = 6.0

## Analytical estimate

- `substrate_eps_r` = 11.9
- `eps_eff` = 6.45
- `estimated_z0_ohm` = 50.04
- `scikit_rf_z0_ohm` = 50.0083
- `scikit_rf_eps_eff` = 6.449543
- `analytical_backend` = scikit-rf CPW (Ghione/Naldi)
- `target_frequency_ghz` = 6.0
- `quarter_wave_length_um` = 4918.4652

## First-principles equations

- **CPW impedance:** `Z0 = (30*pi / sqrt(eps_eff)) * K(k')/K(k)` — k = w/(w+2g), k'=sqrt(1-k^2).
- **Effective permittivity:** `eps_eff = (1 + eps_r) / 2` — Thick-substrate quasi-static CPW.
- **Phase velocity:** `v_p = c / sqrt(eps_eff)`
- **Quarter-wave length:** `L = v_p / (4 f)` — Physical length of a λ/4 resonator at f.

## Proposed parameters (from target)

```json
{
  "center_width_um": 10.0,
  "gap_um": 6.0,
  "length_um": 4918.4652,
  "coupling_gap_um": 4.0
}
```

## Design rationale

- The impedance depends only on the ratio k = w/(w+2g), not absolute size — so geometry can be scaled to satisfy the minimum-gap rule while holding Z0 fixed.
- On high-permittivity silicon, eps_eff is large, so a given Z0 needs a relatively narrow gap compared to a low-eps substrate.
- Ground-plane width and any top cover shift Z0 slightly; the thick-substrate model ignores them.
- For a λ/4 resonator, the open/short boundary and coupling capacitor pull the resonance down from the ideal v_p/4f — EM is needed for the exact f0 and Q.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal'); eps_eff = (1+eps_r)/2.
- Symmetric CPW, thick substrate, zero metal thickness, lossless.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.

## Recommended simulation

- **resonance_and_Q:** openEMS plus scikit-rf; retain Touchstone and mesh-convergence evidence.

## References

- R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001. — Conformal-mapping CPW impedance model.
- W. Hilberg, 'From approximations to exact relations for characteristic impedances', IEEE Trans. MTT-17 (1969) 259. — Closed-form K(k)/K(k') used here (error < 8e-6).
- G. Ghione and C. Naldi, 'Analytical Formulas for Coplanar Lines in Hybrid and Monolithic MICs', Electronics Letters 20(4), 1984, 179-181. — Finite-substrate quasi-static model implemented by optional scikit-rf CPW.
- A. Arsenovic et al., 'scikit-rf: An Open Source Python Package for Microwave Network Creation, Analysis, and Calibration', IEEE Microwave Magazine 23(1), 2022, 98-105, doi:10.1109/MMM.2021.3117139. — Optional BSD-3 analytical and Touchstone implementation.
- D. M. Pozar, 'Microwave Engineering', 4th ed., Wiley, 2012. — Transmission-line and λ/4 theory.

See the repository [REFERENCES.md](../../../REFERENCES.md).

## Evidence status

- A citation supports the analytical **method/model**, not this specific layout.
- This generated geometry has **not** been EM-simulated (no solver executed).
- This generated geometry has **not** been measured.
- This generated geometry is **not** fabrication-ready.
