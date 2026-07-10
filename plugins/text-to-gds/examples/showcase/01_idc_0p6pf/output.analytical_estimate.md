# Analytical Estimate - IDC

- Model: **Bahl/Alley quasi-static interdigital capacitor**
- Status: **analytical** (not simulated or measured)

## Target

- `capacitance_pf`: `0.6`
- `frequency_ghz`: `6.0`

## Calculated values

- `substrate_eps_r`: `11.9`
- `eps_re`: `6.45`
- `estimated_capacitance_pf`: `0.5583`
- `target_capacitance_pf`: `0.6`
- `estimate_vs_target_pct`: `-7.0`
- `proposed_finger_pairs_for_target`: `22`
- `proposed_estimate_pf`: `0.6168`

## Equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` - N = 2*finger_pairs; l = overlap length [cm]; A1=0.089, A2=0.10 pF/cm.
- **Effective permittivity:** `eps_re = (eps_r + 1) / 2` - Surface IDC on a thick substrate.
- **Self-resonance (qualitative):** `f_SRF ~ 1 / (2*pi*sqrt(L_par * C))` - Parasitic series inductance L_par of the fingers/bus sets an upper usable frequency.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- Coplanar fingers on a thick, lossless substrate; metal thickness neglected.
- Uniform fingers; end effects approximated by the two-terminal-finger term A2.

## Limitations

- The Bahl model is quasi-static; accuracy depends on stack and geometry and requires EM correlation.
- It ignores finite metal thickness, fringing at finger ends, and substrate loss tangent.
- Self-resonance and Q are NOT predicted here — an EM solve is required before fabrication.
