# Simulation Plan - QuarterWaveResonator

- Status: **planned**
- Simulation readiness: **Level 1 - geometry/research workflow defined**
- No solver result is claimed by this file.

## Recommended extraction

- **resonance_and_Q:** openEMS plus scikit-rf; retain Touchstone and mesh-convergence evidence.

## Comparison method

1. Execute the named solver and retain its input, version, log, and output artifact.
2. Extract the requested physical quantity from the solver-owned output.
3. Compare it with the Layout DSL target and state the error and tolerance.
4. Change Layout DSL parameters, regenerate, and rerun verification.

## Limitations

- Quasi-static, infinitely thick substrate, zero metal thickness, lossless.
- No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.
