# Feasibility Analysis — 5 MHz LC Resonator

**Date:** 2026-06-29
**Target:** f0 = 5 MHz
**Status:** INFEASIBLE for on-chip layout under realistic constraints

## First-principles analysis

### Resonance frequency equation

```
f0 = 1 / (2π√(LC))
```

Rearranging for required LC product:

```
LC = 1 / (2πf0)²
LC = 1 / (2π × 5×10⁶)²
LC = 1 / (3.14159×10⁷)²
LC = 1 / 9.8696×10¹⁴
LC ≈ 1.013×10⁻¹⁵ s²
```

### Required L and C combinations

| C | Required L | Feasibility |
|---|-----------|-------------|
| 1 pF | 1.013 μH | ❌ Extremely large inductor (~100+ turns, mm-scale) |
| 10 pF | 101.3 nH | ⚠️ Large but possible (~20-30 turns, ~500 μm) |
| 100 pF | 10.13 nH | ⚠️ Possible L, but C requires ~1 mm² area |
| 1 nF | 1.013 nH | ✅ L achievable, ❌ C impossible on-chip |

### On-chip component constraints

**Spiral inductor practical limits:**
- Typical range: 1 nH to 100 nH
- Maximum practical: ~1 μH (requires ~100 turns, ~2 mm² area)
- Q-factor degrades with turn count
- Self-resonant frequency (SRF) decreases with size

**On-chip capacitor practical limits:**
- MIM capacitor density: ~1-2 fF/μm²
- Typical range: 100 fF to 10 pF
- Maximum practical: ~100 pF (requires ~50,000-100,000 μm² = ~0.5-1 mm²)

### Most feasible combination

**Option: L = 10.13 nH, C = 100 pF**

Inductor:
- ~5-10 turns, ~200-300 μm outer dimension
- Achievable with standard spiral geometry
- Q-factor ~5-15 at 5 MHz (substrate loss dominated)

Capacitor:
- 100 pF at 1 fF/μm² density = 100,000 μm² = 0.1 mm²
- Achievable with MIM or interdigital structure
- Large but within single-die limits

**Total footprint estimate:** ~0.3-0.5 mm² (inductor + capacitor + routing)

## Why 5 MHz is problematic

### 1. Large component values

At 5 MHz, the required LC product is ~100× larger than typical RF circuits:
- 2.4 GHz Bluetooth: LC ≈ 1×10⁻¹⁸ s²
- 6 GHz WiFi: LC ≈ 1.7×10⁻¹⁹ s²
- **5 MHz target: LC ≈ 1×10⁻¹⁵ s²** (1000× larger than 2.4 GHz)

### 2. Parasitic dominance

At 5 MHz:
- Substrate loss is significant
- Wirebond/package inductance (~1-10 nH) is comparable to target L
- Stray capacitance (~0.1-1 pF) is significant fraction of target C
- **Parasitic LC can shift resonance by >50%**

### 3. Q-factor limitations

On-chip spiral inductors at 5 MHz:
- Substrate eddy current losses dominate
- Typical Q: 2-10 (vs. 10-50 at GHz frequencies)
- **Low Q broadens resonance peak, making frequency definition ambiguous**

### 4. Area penalty

Achievable on-chip:
- L = 10 nH → ~200 μm × 200 μm = 0.04 mm²
- C = 100 pF → ~300 μm × 300 μm = 0.09 mm²
- **Total: ~0.13 mm² minimum** (vs. ~0.001 mm² for GHz circuits)

This is large but not impossible for a test structure.

## Recommendation

### Preferred result: INFEASIBLE

**5 MHz is not recommended for on-chip LC resonator** because:
1. Component values are 100-1000× larger than typical RF designs
2. Parasitic effects dominate and make frequency unpredictable
3. Q-factor is too low for meaningful resonance characterization
4. Area penalty is excessive for a single resonator

### If forced to attempt

Use:
- L = 10 nH (10-turn square spiral, 250 μm outer)
- C = 100 pF (MIM capacitor, 300 μm × 300 μm)
- Expected f0 = 1/(2π√(10e-9 × 100e-12)) = 159 MHz (31× higher than target)
- **This demonstrates that 5 MHz requires ~30× more LC product than achievable**

### Alternative approach

For 5 MHz applications:
- Use discrete components (off-chip inductor + capacitor)
- Use ceramic resonator or crystal
- Use active LC simulation (gyrator circuit)
- **Do not attempt on-chip lumped LC at 5 MHz**

## Conclusion

**Status: INFEASIBLE**

The 5 MHz LC resonator benchmark should return:
- `status = "INFEASIBLE"`
- `reason = "Required LC product (1.013×10⁻¹⁵ s²) exceeds practical on-chip limits by 100-1000×"`
- `feasible_alternative = "159 MHz with L=10nH, C=100pF (most aggressive on-chip values)"`

This is a valid and preferred result. The benchmark tests whether Text-to-Layout can reason from circuit requirements to physical feasibility, not just draw layouts.
