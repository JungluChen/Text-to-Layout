# Simulation Plan - SpiralInductor

- Status: **planned**
- Simulation readiness: **Level 1 - geometry/research workflow defined**
- No solver result is claimed by this file.

## Recommended extraction

- **inductance_and_resistance:** FastHenry/FastHenry2 first; Q3D/HFSS is optional correlation.

## Comparison method

1. Execute the named solver and retain its input, version, log, and output artifact.
2. Extract the requested physical quantity from the solver-owned output.
3. Compare it with the Layout DSL target and state the error and tolerance.
4. Change Layout DSL parameters, regenerate, and rerun verification.

## Limitations

- The Mohan estimate does not establish Q or self-resonance.
- Skin effect, substrate loss, and parasitic capacitance require extraction.
