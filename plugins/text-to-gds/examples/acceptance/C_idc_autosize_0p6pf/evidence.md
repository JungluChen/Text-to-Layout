# Acceptance — C_idc_autosize_0p6pf

**Prompt:** Design an IDC targeting 0.6 pF using 4 um width, 2 um gap, and 250 um overlap. Choose the finger pair count automatically.

**Verdict:** `GEOMETRY_PASS`

## Evidence ladder

- [x] geometry generated
- [x] artifact generated
- [x] analytical estimate
- [x] solver input prepared
- [ ] solver executed
- [ ] extracted and compared
- [ ] physics verified
- [ ] fabrication ready

## Analytical estimate

- `target_capacitance_pf` = 0.6
- `reference_finger_pairs` = 22
- `reference_estimate_pf` = 0.6983
- `reference_error_pct` = 16.38
- `chosen_finger_pairs` = 19
- `chosen_estimate_pf` = 0.5988
- `chosen_error_pct` = -0.2
- `smallest_count_reaching_target` = 20
- `smallest_reaching_estimate_pf` = 0.6319
- `smallest_reaching_error_pct` = 5.32
- `error_improvement_pct_points` = 16.17
- `model` = Bahl/Alley quasi-static IDC

## Target comparison

- `target_pf` = 0.6
- `analytical_pf` = 0.5988
- `error_pct` = -0.2
- `method` = analytical
- `solver_executed` = False

## Notes

- Auto-sized to 19 finger pairs (|error| 0.20%) vs reference 22 (|error| 16.38%).
- Analytical (Bahl/Alley) only — no EM solver executed, so no EM-verified capacitance is claimed.

## References

- I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2.
- G. D. Alley, IEEE Trans. MTT-18 (1970) 1028 — interdigital capacitor model.

## Status contract

- `GEOMETRY_PASS` means geometry and artifacts are valid and an analytical
  estimate exists — it is **not** a physics claim.
- `PHYSICS_VERIFIED` requires a real solver run, a parsed result, and a
  target comparison within tolerance.
- No acceptance result is ever `fabrication_ready`.
