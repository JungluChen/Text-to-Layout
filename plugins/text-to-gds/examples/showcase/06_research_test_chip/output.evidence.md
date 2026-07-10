# Evidence — TestChip

**Model:** Composite per-sub-device analytical models (Bahl IDC, conformal CPW, Wheeler spiral)
**Target:** capacitance_pf = 0.6, impedance_ohm = 50.0

## Analytical estimate

- `substrate_eps_r` = 11.9
- `idc_estimated_capacitance_pf` = 0.6319
- `cpw_estimated_z0_ohm` = 50.0001
- `cpw_effective_permittivity` = 6.45
- `spiral_estimated_inductance_nh` = 3.0

## First-principles equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` — IDC sub-block estimate.
- **CPW impedance (conformal mapping):** `Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)` — CPW sub-block estimate.
- **Modified Wheeler spiral inductance:** `L = K1 * mu0 * n^2 * d_avg / (1 + K2 * rho)` — Spiral sub-block estimate.

## Design rationale

- Every electrical claim on the tile must name the sub-device it belongs to and be labeled analytical unless a solver ran on that sub-device geometry.
- The tile outline lives on the TEXT layer so the bounding box equals the tile size without adding functional metal.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- Sub-devices are far enough apart that mutual coupling is neglected (not verified).
- Single-metal process; alignment marks assume a second lithography level exists.

## Limitations

- This tile is a geometry-level comparison candidate; no sub-block on the tile has been simulated in place, and inter-device coupling is not modeled.
- All electrical numbers are per-sub-device analytical estimates, valid only in isolation.
- Alignment marks and the title label are lithographic aids with no electrical model.
- The tile is not fabrication-ready: process DRC, density rules, and dicing margins are not checked.

## Recommended simulation

- **IDC_sub_block:** FasterCap/FastCap on the standalone IDC geometry (identical parameters).
- **full_tile:** Full-wave EM of the assembled tile — future work, not performed here.

## References

- I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003. — IDC and spiral-inductor lumped-element models used for the sub-block estimates.
- R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001. — CPW impedance estimate for the transmission-line sub-block.
- S. M. Sze & K. K. Ng, 'Physics of Semiconductor Devices', Wiley, 3rd ed., 2007, lithography/alignment discussion. — Role of alignment marks in multi-layer registration.

See the repository [REFERENCES.md](../../../REFERENCES.md).

## Evidence status

- A citation supports the analytical **method/model**, not this specific layout.
- This generated geometry has **not** been EM-simulated (no solver executed).
- This generated geometry has **not** been measured.
- This generated geometry is **not** fabrication-ready.
