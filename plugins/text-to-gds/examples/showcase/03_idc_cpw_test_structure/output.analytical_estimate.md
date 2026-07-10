# Analytical Estimate - TestStructure

- Model: **Bahl/Alley IDC + conformal-mapping CPW feed (composite analytical model)**
- Status: **analytical** (not simulated or measured)

## Target

- `capacitance_pf`: `0.6`
- `impedance_ohm`: `50.0`

## Calculated values

- `substrate_eps_r`: `11.9`
- `estimated_capacitance_pf`: `0.6`
- `feed_estimated_z0_ohm`: `50.0001`
- `feed_effective_permittivity`: `6.45`
- `target_capacitance_pf`: `0.6`
- `estimate_vs_target_pct`: `0.0`

## Equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` - Device under test only; feed and launch metal are excluded.
- **CPW impedance (conformal mapping):** `Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)` - Feed sections; k = w/(w+2g).

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- The device under test is the embedded IDC; feeds are treated as ideal 50-ohm-class access lines.
- Launch pads are probe-compatible rectangles, not a calibrated GSG standard.

## Limitations

- The capacitance model covers the IDC region only; launch pads and feed traces add parasitic shunt capacitance that a real measurement must de-embed.
- The CPW feed impedance is an analytical estimate; no EM solver validates the launch-to-feed and feed-to-IDC transitions.
- No radiation, substrate loss, or self-resonance model is included.
