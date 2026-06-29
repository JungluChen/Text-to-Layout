# Evidence — IDC

**Model:** Bahl/Alley quasi-static interdigital capacitor
**Target:** capacitance_pf = 0.6, frequency_ghz = 6.0

## Analytical estimate

- `substrate_eps_r` = 11.9
- `eps_re` = 6.45
- `estimated_capacitance_pf` = 0.6983
- `target_capacitance_pf` = 0.6
- `estimate_vs_target_pct` = 16.4
- `proposed_finger_pairs_for_target` = 20
- `proposed_estimate_pf` = 0.6319

## First-principles equations

- **Bahl IDC capacitance:** `C = (eps_re + 1) * l * [(N - 3)*A1 + A2]` — N = 2*finger_pairs; l = overlap length [cm]; A1=0.089, A2=0.10 pF/cm.
- **Effective permittivity:** `eps_re = (eps_r + 1) / 2` — Surface IDC on a thick substrate.
- **Self-resonance (qualitative):** `f_SRF ~ 1 / (2*pi*sqrt(L_par * C))` — Parasitic series inductance L_par of the fingers/bus sets an upper usable frequency.

## Proposed parameters (from target)

```json
{
  "finger_pairs": 20,
  "finger_width_um": 4.0,
  "gap_um": 2.0,
  "overlap_um": 250.0,
  "bus_width_um": 25.0,
  "metal_layer": "M1"
}
```

## Design rationale

- Finger width sets current-handling and series resistance; too narrow raises loss and ohmic Q-degradation, too wide wastes area without adding much capacitance.
- Gap is the dominant capacitance lever: capacitance per unit length rises sharply as the gap shrinks, but the gap is bounded below by the process minimum-spacing rule.
- Overlap length l scales the capacitance linearly (see equation) — the cheapest knob for hitting a target value once gap/width are fixed by rules.
- Finger count N scales capacitance roughly linearly (the (N-3) term); more fingers means larger footprint and more parasitic inductance, lowering self-resonance.
- Parasitic series inductance of the bus and fingers creates a self-resonant frequency; above it the device no longer behaves as a capacitor.

## Assumptions

- Substrate eps_r = 11.9 (from technology 'generic_2metal').
- Coplanar fingers on a thick, lossless substrate; metal thickness neglected.
- Uniform fingers; end effects approximated by the two-terminal-finger term A2.

## Limitations

- The Bahl model is quasi-static; accuracy depends on stack and geometry and requires EM correlation.
- It ignores finite metal thickness, fringing at finger ends, and substrate loss tangent.
- Self-resonance and Q are NOT predicted here — an EM solve is required before fabrication.

## Recommended simulation

- **capacitance:** Ansys Q3D Extractor — quasi-static C between the two combs (see simulation/q3d_workflow.md).
- **self_resonance_and_Q:** Ansys HFSS or Sonnet — full-wave S-parameters to find SRF and Q (simulation/hfss_workflow.md, sonnet_workflow.md).

## References

- I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2. — Closed-form interdigital capacitance used here.
- G. D. Alley, 'Interdigital Capacitors and Their Application to Lumped-Element Microwave Integrated Circuits', IEEE Trans. MTT-18 (1970) 1028. — Original per-finger capacitance coefficients.
- S. S. Gevorgian et al., 'CAD models for multilayered substrate interdigital capacitors', IEEE Trans. MTT-44 (1996) 896. — More accurate multilayer/finite-thickness models for EM cross-check.
