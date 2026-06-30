# Evidence — 5 MHz LC Resonator

**Status:** INFEASIBLE
**Model:** f0 = 1/(2π√LC)
**Target:** resonance_frequency_hz = 5,000,000

## Analytical model and reference

- **Model:** lumped parallel/series LC resonance, `f0 = 1/(2π√LC)`.
- **Reference:** standard LCR resonance (e.g. Pozar, *Microwave Engineering*,
  4th ed., Ch. 6). See [`../../../REFERENCES.md`](../../../REFERENCES.md).
- **What it supports:** the *required* LC product for a target frequency.
- **What it does NOT prove:** that any specific on-chip geometry realizes the
  required L and C with usable Q. Only EM extraction or measurement can do that.

## Required LC product

```
LC = 1/(2πf0)² = 1/(2π × 5×10⁶)² ≈ 1.013×10⁻¹⁵ s²
```

### Required L for a given C (LC = 1.013×10⁻¹⁵ s²)

| C | Required L | On-chip feasibility |
|---|-----------|---------------------|
| 1 pF | 1.013 mH | ❌ Impossible |
| 10 pF | 101.3 μH | ❌ Impossible |
| 100 pF | 10.13 μH | ❌ Impractical |
| 1 nF | 1.013 μH | ❌ Impractical |
| 10 nF | 101.3 nH | ❌ C impractical on-chip |
| 100 nF | 10.13 nH | ❌ C impossible on-chip |

## On-chip limits and the resulting gap

- Practical spiral L: ~1-10 nH (usable Q), up to ~100 nH aggressive.
- Practical MIM C: ~0.1-10 pF, up to ~100 pF aggressive (~0.1 mm²).

Best *comfortable* on-chip values:

```
L = 10 nH, C = 100 pF
f0 = 1/(2π√(10×10⁻⁹ × 100×10⁻¹²)) = 1/(2π√(10⁻¹⁸)) = 159 MHz
```

This is **31× higher** than the 5 MHz target. The required LC product is
**~100-1000× larger** than any practical on-chip combination, so L = 10 nH with
C = 100 pF is **not** close to 5 MHz.

| On-chip combination | LC (s²) | f0 | LC gap vs target |
|---|---|---|---|
| L = 10 nH, C = 100 pF | 1×10⁻¹⁸ | 159 MHz | ~1000× |
| L = 100 nH, C = 100 pF | 1×10⁻¹⁷ | 50.3 MHz | ~100× |
| L = 1 µH, C = 100 pF | 1×10⁻¹⁶ | 15.9 MHz | ~10× |

To reach 5 MHz you would need L ≈ 10.13 µH (with 100 pF) or C ≈ 101 nF (with
10 nH); neither is realizable on-chip.

## Why 5 MHz is infeasible on-chip

1. Required LC exceeds practical on-chip limits by ~100-1000×.
2. Parasitics (wirebond ~1-10 nH, stray C ~0.1-1 pF) dominate and shift f0 >50%.
3. On-chip spiral Q at 5 MHz is ~2-10, broadening the peak.
4. Area penalty is mm²-scale.

## Recommendation

**Status: INFEASIBLE.** For 5 MHz use discrete components, a crystal/ceramic
resonator, or an active (gyrator) LC realization. The minimum comfortable on-chip
resonance with these passives is ≈ 159 MHz.

## What this proves

Text-to-Layout reasons from circuit requirements to physical feasibility,
identifies impossible targets, explains why, and proposes alternatives — rather
than drawing a layout that looks correct but is physically wrong.
