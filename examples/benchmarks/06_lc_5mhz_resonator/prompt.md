# Prompt — LC Resonator

Design a lumped LC resonator layout that targets 5 MHz resonance frequency.

## Requirements

- Target resonance frequency: 5 MHz
- Components: spiral inductor + IDC/MIM capacitor
- Topology: lumped LC tank (parallel or series)
- Process: generic_2metal

## Expected output

A Layout DSL that specifies:
- Spiral inductor with target inductance
- Capacitor with target capacitance
- Calculated resonance frequency within 5% of 5 MHz

## Success criteria

The benchmark passes ONLY if:
1. Solver-executed L and C values exist
2. f_extracted = 1/(2π√(L_extracted × C_extracted))
3. |f_extracted - 5 MHz| / 5 MHz ≤ 5%
4. physics_verified = true
