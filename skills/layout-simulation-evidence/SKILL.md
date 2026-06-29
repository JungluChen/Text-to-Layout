---
name: layout-simulation-evidence
description: Create evidence-backed EM simulation and extraction plans for IC, RF, microwave, and superconducting layouts. Use when a generated GDS must be evaluated against capacitance, inductance, Q, S-parameters, resonance, coupling, or nonlinear-device targets.
---

# Layout simulation evidence

## Required evidence packet

1. Record the analytical estimate, derivation, assumptions, references, and confidence.
2. Select a solver appropriate to the extracted quantity: Q3D for quasi-static C/L/R, Sonnet or ADS Momentum for planar EM, HFSS for 3-D full-wave behavior, and ADS for circuit/EM co-simulation.
3. Document GDS/DXF import, layer mapping, substrate and metal stack, boundaries, mesh/convergence criteria, ports, sweep range, and expected outputs.
4. Extract only solver-produced C, L, Q, S-parameters, resonance, or coupling values.
5. Compare the extracted value with the DSL target and state tolerance and error.
6. Propose a DSL parameter update, regenerate, verify, and repeat.
7. Preserve solver input, version, log, and non-empty output artifact as provenance.

Read the repository guides under `simulation/` for HFSS, Q3D, ADS, and Sonnet setup.

## Status vocabulary

Use `analytical`, `planned`, `input_files_prepared`, `executed`, `failed`, or `skipped`. Only `executed` with a solver-owned output is simulation evidence. Never infer solver success from a GDS or plot.
