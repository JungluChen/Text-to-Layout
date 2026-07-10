# Simulation Plan - IDC

- Status: **planned**
- Simulation readiness: **Level 1 - geometry/research workflow defined**
- No solver result is claimed by this file.

## Recommended extraction

- **capacitance:** Ansys Q3D Extractor — quasi-static C between the two combs (see simulation/q3d_workflow.md).
- **self_resonance_and_Q:** Ansys HFSS or Sonnet — full-wave S-parameters to find SRF and Q (simulation/hfss_workflow.md, sonnet_workflow.md).

## Comparison method

1. Execute the named solver and retain its input, version, log, and output artifact.
2. Extract the requested physical quantity from the solver-owned output.
3. Compare it with the Layout DSL target and state the error and tolerance.
4. Change Layout DSL parameters, regenerate, and rerun verification.

## Limitations

- The Bahl model is quasi-static; accuracy depends on stack and geometry and requires EM correlation.
- It ignores finite metal thickness, fringing at finger ends, and substrate loss tangent.
- Self-resonance and Q are NOT predicted here — an EM solve is required before fabrication.
