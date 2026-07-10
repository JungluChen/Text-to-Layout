# Evidence — TestStructure

**Model:** Bahl/Alley IDC + conformal-mapping CPW feed (composite analytical model)
**Target:** capacitance_pf = 0.6, impedance_ohm = 50.0

## Analytical estimate

- `substrate_eps_r` = 11.9
- `estimated_capacitance_pf` = 0.6
- `feed_estimated_z0_ohm` = 50.0001
- `feed_effective_permittivity` = 6.45
- `target_capacitance_pf` = 0.6
- `estimate_vs_target_pct` = 0.0

## First-principles equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` — Device under test only; feed and launch metal are excluded.
- **CPW impedance (conformal mapping):** `Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)` — Feed sections; k = w/(w+2g).

## Design rationale

- Only the IDC region is exported to FasterCap; the report must state that feeds and launches are not simulated.
- Keep the ground clearance constant along the structure so the feed impedance estimate stays meaningful.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- The device under test is the embedded IDC; feeds are treated as ideal 50-ohm-class access lines.
- Launch pads are probe-compatible rectangles, not a calibrated GSG standard.

## Limitations

- The capacitance model covers the IDC region only; launch pads and feed traces add parasitic shunt capacitance that a real measurement must de-embed.
- The CPW feed impedance is an analytical estimate; no EM solver validates the launch-to-feed and feed-to-IDC transitions.
- No radiation, substrate loss, or self-resonance model is included.

## Recommended simulation

- **capacitance:** FasterCap/FastCap on the embedded IDC region (documented extraction region).
- **transitions:** Full-wave EM (openEMS/HFSS/Sonnet) for launch and step transitions — not performed here.

## References

- I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2. — Closed-form interdigital capacitance for the device under test.
- R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001. — CPW characteristic impedance for the feed sections.
- D. F. Williams & R. B. Marks, 'Transmission line capacitance measurement', IEEE Microwave and Guided Wave Letters 1 (1991) 243. — Why launch/feed parasitics must be de-embedded from a capacitance measurement.

See the repository [REFERENCES.md](../../../REFERENCES.md).

## Evidence status

- A citation supports the analytical **method/model**, not this specific layout.
- This generated geometry has **not** been EM-simulated (no solver executed).
- This generated geometry has **not** been measured.
- This generated geometry is **not** fabrication-ready.
