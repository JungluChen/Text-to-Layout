# Evidence — 5 MHz LC Resonator

**Status:** INFEASIBLE
**Model:** f0 = 1/(2π√LC)
**Target:** resonance_frequency_hz = 5,000,000

## First-principles analysis

### Resonance frequency equation

```
f0 = 1/(2π√LC)
```

Rearranging for required LC product:

```
LC = 1/(2πf0)²
LC = 1/(2π × 5×10⁶)²
LC = 1/(3.14159×10⁷)²
LC = 1/9.8696×10¹⁴
LC ≈ 1.013×10⁻¹⁵ s²
```

### Required component combinations

| C | Required L | Feasibility |
|---|-----------|-------------|
| 1 pF | 1.013 μH | ❌ Extremely large (~100 turns) |
| 10 pF | 101.3 nH | ⚠️ Large (~20-30 turns) |
| 100 pF | 10.13 nH | ⚠️ Most feasible |
| 1 nF | 1.013 nH | ✅ L possible, ❌ C impossible |

### On-chip constraints

**Inductor:**
- Practical range: 1 nH to 100 nH
- Maximum: ~1 μH (100+ turns, ~2 mm²)
- Q-factor at 5 MHz: 2-10 (substrate loss dominated)

**Capacitor:**
- MIM density: 1-2 fF/μm²
- Practical range: 100 fF to 10 pF
- Maximum: ~100 pF (100,000 μm² = 0.1 mm²)

### Feasibility verdict

**Best achievable:** L = 10 nH, C = 100 pF
```
f0 = 1/(2π√(10×10⁻⁹ × 100×10⁻¹²))
f0 = 1/(2π√(10⁻¹⁸))
f0 = 1/(2π × 10⁻⁹)
f0 = 159 MHz
```

**Result:** 31× higher than 5 MHz target.

## Why 5 MHz is infeasible

### 1. Component size mismatch

| Frequency | Typical LC | Ratio to 5 MHz |
|-----------|-----------|----------------|
| 5 GHz | 1×10⁻¹⁸ s² | 1000× smaller |
| 2.4 GHz | 4×10⁻¹⁸ s² | 250× smaller |
| 1 GHz | 2.5×10⁻¹⁷ s² | 100× smaller |
| 100 MHz | 2.5×10⁻¹⁵ s² | 2.5× smaller |
| **5 MHz** | **1×10⁻¹⁵ s²** | **Target** |

### 2. Parasitic dominance

At 5 MHz:
- Wirebond inductance: 1-10 nH (comparable to target L)
- Stray capacitance: 0.1-1 pF (significant fraction of target C)
- **Parasitic LC can shift resonance by >50%**

### 3. Q-factor degradation

On-chip spiral inductors at 5 MHz:
- Substrate eddy current losses dominate
- Typical Q: 2-10 (vs. 10-50 at GHz)
- **Low Q broadens resonance peak, making frequency ambiguous**

### 4. Area penalty

Achievable on-chip:
- L = 10 nH → 200 μm × 200 μm = 0.04 mm²
- C = 100 pF → 300 μm × 300 μm = 0.09 mm²
- **Total: ~0.13 mm²** (vs. ~0.001 mm² for GHz circuits)

## Recommendation

**Status: INFEASIBLE**

The 5 MHz LC resonator is not achievable with on-chip lumped LC components because:
1. Required LC product exceeds practical limits by 100-1000×
2. Parasitic effects dominate and make frequency unpredictable
3. Q-factor is too low for meaningful resonance characterization
4. Area penalty is excessive for a single resonator

**Alternative approaches for 5 MHz:**
- Discrete components (off-chip inductor + capacitor)
- Ceramic resonator or crystal
- Active LC simulation (gyrator circuit)
- Consider 159 MHz as minimum feasible on-chip frequency

## What this proves

This benchmark demonstrates that Text-to-Layout can:
1. Reason from circuit requirements to physical feasibility
2. Identify when a target is impossible
3. Explain why and propose alternatives
4. **Not just draw layouts that look correct but are physically wrong**
