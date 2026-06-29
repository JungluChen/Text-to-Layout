# Analytical Estimate - CPW

- Model: **Conformal-mapping CPW (Simons/Hilberg) + λ/4 transmission-line theory**
- Status: **analytical** (not simulated or measured)

## Target

- `impedance_ohm`: `50.0`

## Calculated values

- `substrate_eps_r`: `11.9`
- `eps_eff`: `6.45`
- `estimated_z0_ohm`: `50.04`
- `target_z0_ohm`: `50.0`
- `proposed_gap_um_for_target`: `5.983`
- `proposed_gap_meets_min_spacing`: `True`

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
