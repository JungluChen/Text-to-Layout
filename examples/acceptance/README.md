# Physics-fit acceptance tests

A *benchmark* answers "does it draw?". An *acceptance test* answers the harder
question this project exists for:

> Does the generated layout meet the physical requirement, or does the system
> correctly refuse an infeasible requirement?

Each packet records an explicit **verdict** and an **evidence ladder** so a
geometry pass is never mistaken for a physics claim. Regenerate with:

```bash
python scripts/generate_acceptance.py
```

The pass rules are enforced in
[`tests/textlayout_suite/test_acceptance_physics.py`](../../tests/textlayout_suite/test_acceptance_physics.py).

| # | Prompt | Verdict | What it proves |
| - | ------ | ------- | -------------- |
| A | Fully on-chip passive LC resonator at 5 MHz | `INFEASIBLE` | The system refuses to fake a layout when first principles say the target is unreachable on-chip. Required `L·C = 1.013×10⁻¹⁵ s²`; the best aggressive on-chip pairing reaches only ~50 MHz. |
| B | 6 GHz quarter-wave CPW resonator on silicon | `GEOMETRY_PASS` | Length is derived from `v_p/(4f)` (≈4918 µm), geometry verifies with signal+ground ports, and the openEMS input is prepared — but it stays Level 2 because no solver was executed. |
| C | IDC targeting 0.6 pF, auto-choose finger pairs | `GEOMETRY_PASS` | Auto-sizing picks 19 finger pairs (analytical error ≈0.2%) instead of the prompt's 22 (≈16.4%), and refuses to claim EM-verified capacitance. |

## Verdict vocabulary

| Verdict | Meaning |
| ------- | ------- |
| `INFEASIBLE` | First principles show the target cannot be met on-chip; no geometry is produced. |
| `GEOMETRY_PASS` | Geometry + artifacts are valid and an analytical estimate exists. **Not** a physics claim. |
| `PHYSICS_VERIFIED` | A solver executed, a value was extracted, and it matched the target within tolerance. |

No acceptance result is ever `fabrication_ready`.

## Promotion rule for B (PHYSICS_VERIFIED)

Acceptance B is promoted from `GEOMETRY_PASS` to `PHYSICS_VERIFIED` only when
openEMS is installed and executed, its resonance is extracted, and the extracted
frequency matches the 6 GHz target within 5%:

```python
from textlayout.acceptance import evaluate_quarter_wave_resonator
result = evaluate_quarter_wave_resonator(6.0, execute_solver=True, work_dir="out/acc_b")
```
