# TODO — 5 MHz LC Resonator

**Status:** INFEASIBLE (no layout to generate)

## Reason

5 MHz is infeasible for a practical fully on-chip passive LC resonator under
normal IC/RF layout constraints.

### First-principles analysis

```
LC = 1 / (2πf0)² = 1.013×10⁻¹⁵ s²
```

### Required L for a given C (LC = 1.013×10⁻¹⁵ s²)

| C | Required L | On-chip feasibility |
|---|-----------|---------------------|
| 1 pF | 1.013 mH | ❌ Impossible |
| 10 pF | 101.3 μH | ❌ Impossible |
| 100 pF | 10.13 μH | ❌ Impractical |
| 1 nF | 1.013 μH | ❌ Impractical |
| 10 nF | 101.3 nH | ❌ C impractical |
| 100 nF | 10.13 nH | ❌ C impossible |

### On-chip limits

- Spiral L: ~1-10 nH practical (≤ ~100 nH aggressive).
- MIM C: ~0.1-10 pF practical (≤ ~100 pF aggressive).
- Best comfortable on-chip LC ≈ 1×10⁻¹⁸ s² → 159 MHz.
- Required LC = 1.013×10⁻¹⁵ s² → ~100-1000× larger than achievable.

### Why it fails

With the most aggressive comfortable on-chip values (L = 10 nH, C = 100 pF):

```
f0 = 1/(2π√(10e-9 × 100e-12)) = 159 MHz   # 31× higher than 5 MHz
```

L = 10 nH, C = 100 pF is **not** close to 5 MHz. Reaching 5 MHz needs
L ≈ 10.13 µH (with 100 pF) or C ≈ 101 nF (with 10 nH) — neither realizable
on-chip. Parasitics, low Q (~2-10), and mm²-scale area make it worse.

## Verdict

Do not generate a layout. For 5 MHz use discrete components, a crystal/ceramic
resonator, or an active (gyrator) LC realization. Minimum comfortable on-chip
resonance ≈ 159 MHz.

## What this proves

Text-to-Layout reasons about physical feasibility and refuses impossible targets
instead of drawing physically wrong layouts.
