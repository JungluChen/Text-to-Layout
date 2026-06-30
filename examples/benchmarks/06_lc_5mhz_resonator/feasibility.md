# Feasibility Analysis — 5 MHz LC Resonator

**Target:** f0 = 5 MHz
**Status:** INFEASIBLE for a practical fully on-chip passive LC resonator

## First-principles analysis

### Resonance frequency equation

```
f0 = 1 / (2π√(LC))
```

Rearranging for the required LC product:

```
LC = 1 / (2πf0)²
LC = 1 / (2π × 5×10⁶)²
LC = 1 / (3.14159×10⁷)²
LC = 1 / 9.8696×10¹⁴
LC ≈ 1.013×10⁻¹⁵ s²
```

### Required L for a given C (LC = 1.013×10⁻¹⁵ s²)

| C | Required L | On-chip feasibility |
|---|-----------|---------------------|
| 1 pF | 1.013 mH | ❌ Impossible (mH inductor) |
| 10 pF | 101.3 μH | ❌ Impossible (~100+ turn spiral, huge area) |
| 100 pF | 10.13 μH | ❌ Impractical (µH spiral not realizable on-chip) |
| 1 nF | 1.013 μH | ❌ Impractical L and very large C |
| 10 nF | 101.3 nH | ❌ C impractical on-chip (~10 nF) |
| 100 nF | 10.13 nH | ❌ C impossible on-chip (~100 nF) |

Every row requires either an inductor far larger than any practical on-chip
spiral (≤ ~100 nH with usable Q) **or** a capacitor far larger than a practical
on-chip MIM (≤ ~100 pF at ~1-2 fF/µm²). There is no feasible on-chip pairing.

## On-chip component limits

**Spiral inductor (practical):**
- Usable range with acceptable Q: ~1 nH to ~10 nH.
- Aggressive (large area, degraded Q): up to ~100 nH.
- µH-scale on-chip spirals are not realizable at usable Q or area.

**MIM / interdigital capacitor (practical):**
- Density ~1-2 fF/µm².
- Usable range: ~100 fF to ~10 pF; aggressive up to ~100 pF (~0.05-0.1 mm²).
- nF-scale on-chip capacitors are not practical.

### Best achievable on-chip LC product

| Combination | LC product | f0 | Gap vs target |
|---|---|---|---|
| L = 10 nH, C = 100 pF (comfortable) | 1×10⁻¹⁸ s² | **159 MHz** | ~1000× too small in LC |
| L = 100 nH, C = 100 pF (aggressive) | 1×10⁻¹⁷ s² | 50.3 MHz | ~100× too small in LC |
| L = 1 µH, C = 100 pF (impractical) | 1×10⁻¹⁶ s² | 15.9 MHz | ~10× too small in LC |

The required LC product (1.013×10⁻¹⁵ s²) is **~100-1000× larger** than what a
practical on-chip spiral + MIM can provide. The most aggressive *comfortable*
on-chip values (L = 10 nH, C = 100 pF) resonate at **159 MHz — about 31× higher
than the 5 MHz target.** L = 10 nH and C = 100 pF is therefore **not** close to
5 MHz.

To actually reach 5 MHz you would need, for example:
- C = 100 pF → L ≈ 10.13 µH (not realizable as an on-chip spiral), or
- L = 10 nH → C ≈ 101 nF (not realizable as an on-chip capacitor).

## Why 5 MHz is problematic on-chip

1. **Component values.** Required LC is ~100-1000× larger than typical RF
   on-chip designs (2.4 GHz: LC ≈ 4×10⁻¹⁸ s²; 6 GHz: ≈ 7×10⁻¹⁹ s²).
2. **Parasitic dominance.** Wirebond/package inductance (~1-10 nH) is comparable
   to any feasible on-chip L; stray capacitance shifts resonance by >50%.
3. **Q-factor.** On-chip spiral Q at 5 MHz is ~2-10 (substrate loss dominated),
   broadening the peak and making f0 ill-defined.
4. **Area.** A 5 MHz attempt would demand mm²-scale passives.

## Conclusion

**Status: INFEASIBLE**

5 MHz is infeasible for a practical fully on-chip passive LC resonator under
normal IC/RF layout constraints, unless extremely large area, very high
capacitance density, very large inductance, or off-chip components are allowed.

The minimum *comfortable* on-chip resonance with L = 10 nH, C = 100 pF is
≈ 159 MHz. For 5 MHz, use discrete components, a crystal/ceramic resonator, or
an active (gyrator) LC realization.

This benchmark tests whether Text-to-Layout can reason from circuit requirements
to physical feasibility, not just draw a layout.
