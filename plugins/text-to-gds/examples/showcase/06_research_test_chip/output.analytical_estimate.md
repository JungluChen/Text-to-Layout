# Analytical Estimate - TestChip

- Model: **Composite per-sub-device analytical models (Bahl IDC, conformal CPW, Wheeler spiral)**
- Status: **analytical** (not simulated or measured)

## Target

- `capacitance_pf`: `0.6`
- `impedance_ohm`: `50.0`

## Calculated values

- `substrate_eps_r`: `11.9`
- `idc_estimated_capacitance_pf`: `0.6319`
- `cpw_estimated_z0_ohm`: `50.0001`
- `cpw_effective_permittivity`: `6.45`
- `spiral_estimated_inductance_nh`: `3.0`

## Equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` - IDC sub-block estimate.
- **CPW impedance (conformal mapping):** `Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)` - CPW sub-block estimate.
- **Modified Wheeler spiral inductance:** `L = K1 * mu0 * n^2 * d_avg / (1 + K2 * rho)` - Spiral sub-block estimate.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- Sub-devices are far enough apart that mutual coupling is neglected (not verified).
- Single-metal process; alignment marks assume a second lithography level exists.

## Limitations

- This tile is a geometry-level comparison candidate; no sub-block on the tile has been simulated in place, and inter-device coupling is not modeled.
- All electrical numbers are per-sub-device analytical estimates, valid only in isolation.
- Alignment marks and the title label are lithographic aids with no electrical model.
- The tile is not fabrication-ready: process DRC, density rules, and dicing margins are not checked.
