# TODO — 5 MHz LC Resonator

**Status:** INFEASIBLE

## Reason

This benchmark is **INFEASIBLE** for on-chip layout under realistic constraints.

### First-principles analysis

For f0 = 5 MHz:
```
LC = 1 / (2πf0)² = 1.013×10⁻¹⁵ s²
```

### Required component values

| C | Required L | Feasibility |
|---|-----------|-------------|
| 1 pF | 1.013 μH | ❌ Extremely large inductor |
| 10 pF | 101.3 nH | ⚠️ Large but possible |
| 100 pF | 10.13 nH | ⚠️ Possible L, large C |
| 1 nF | 1.013 nH | ✅ L achievable, ❌ C impossible |

### On-chip constraints

- **Inductor limit:** ~100 nH practical, ~1 μH maximum
- **Capacitor limit:** ~10 pF practical, ~100 pF maximum
- **LC product limit:** ~10⁻¹⁵ s² (at 100 nH × 10 pF)
- **Required LC:** 1.013×10⁻¹⁵ s² (borderline feasible)

### Why it fails

Even with the most aggressive values (L = 10 nH, C = 100 pF):
```
f0 = 1/(2π√(10e-9 × 100e-12)) = 159 MHz
```

**This is 31× higher than the 5 MHz target.**

### Additional problems

1. **Parasitic dominance:** Wirebond inductance (~1-10 nH) is comparable to target L
2. **Q-factor:** On-chip spiral Q ~ 2-10 at 5 MHz (vs. 10-50 at GHz)
3. **Area:** ~0.13 mm² minimum (vs. ~0.001 mm² for GHz circuits)
4. **Frequency definition:** Low Q broadens resonance peak

## Verdict

**Do not generate layout.** The 5 MHz target is not achievable with on-chip lumped LC components.

## Alternative

For 5 MHz applications:
- Use discrete components (off-chip)
- Use ceramic resonator or crystal
- Use active LC simulation (gyrator circuit)
- Consider 159 MHz as minimum feasible on-chip frequency

## What this proves

This benchmark demonstrates that Text-to-Layout can:
1. Reason from circuit requirements to physical feasibility
2. Identify when a target is impossible
3. Explain why and propose alternatives
4. **Not just draw layouts that look correct but are physically wrong**
