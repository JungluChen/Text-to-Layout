# Analytical Estimate - SpiralInductor

- Model: **Modified-Wheeler / Mohan planar spiral inductor**
- Status: **analytical** (not simulated or measured)

## Target

- `inductance_nh`: `3.0`

## Calculated values

- `turns`: `4`
- `outer_dimension_um`: `129.168`
- `inner_dimension_um`: `85.168`
- `estimated_inductance_nh`: `3.2227`

## Equations

- **Modified Wheeler (square):** `L = K1*mu0*n^2*d_avg / (1 + K2*rho)` - K1=2.34, K2=2.75; d_avg=(d_out+d_in)/2.
- **Fill ratio:** `rho = (d_out - d_in) / (d_out + d_in)` - Density of the winding.

## Assumptions

- Square planar spiral; uniform width and spacing; thin-film metal.
- Substrate eps_r = 11.9 (technology 'generic_2metal').

## Limitations

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.
