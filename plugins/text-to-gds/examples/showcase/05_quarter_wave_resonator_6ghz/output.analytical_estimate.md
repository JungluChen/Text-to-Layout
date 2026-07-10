# Analytical Estimate - QuarterWaveResonator

- Model: **Quarter-wave CPW hanger (Simons/Pozar initial model)**
- Status: **analytical** (not simulated or measured)

## Target

- `frequency_ghz`: `6.0`

## Calculated values

- `substrate_eps_r`: `11.9`
- `eps_eff`: `6.45`
- `estimated_z0_ohm`: `50.04`
- `scikit_rf_z0_ohm`: `50.0083`
- `scikit_rf_eps_eff`: `6.449543`
- `analytical_backend`: `scikit-rf CPW (Ghione/Naldi)`
- `target_frequency_ghz`: `6.0`
- `quarter_wave_length_um`: `4918.4652`

## Equations

- **CPW impedance:** `Z0 = (30*pi / sqrt(eps_eff)) * K(k')/K(k)` - k = w/(w+2g), k'=sqrt(1-k^2).
- **Effective permittivity:** `eps_eff = (1 + eps_r) / 2` - Thick-substrate quasi-static CPW.
- **Phase velocity:** `v_p = c / sqrt(eps_eff)`
- **Quarter-wave length:** `L = v_p / (4 f)` - Physical length of a λ/4 resonator at f.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal'); eps_eff = (1+eps_r)/2.
- Symmetric CPW, thick substrate, zero metal thickness, lossless.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.
