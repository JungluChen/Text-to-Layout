---
name: layout-simulation-evidence
description: Create evidence-backed EM simulation and extraction plans for IC, RF, microwave, and superconducting layouts. Use when a generated GDS must be evaluated against capacitance, inductance, Q, S-parameters, resonance, coupling, or nonlinear-device targets.
---

# Layout simulation evidence

## Required evidence packet

1. Record the analytical estimate, derivation, assumptions, references, and confidence.
2. Prefer an open-source solver appropriate to the quantity: FasterCap/FastCap for IDC capacitance, FastHenry for inductance/resistance, openEMS or Meep for FDTD, Elmer for FEM/electrostatics, and scikit-rf for Touchstone post-processing.
3. Use commercial Q3D, Sonnet, HFSS, or ADS only as optional higher-fidelity or independent correlation.
4. Document GDS/DXF import, layer mapping, substrate and metal stack, boundaries, mesh/convergence criteria, ports, sweep range, and expected outputs.
5. Extract only solver-produced C, L, Q, S-parameters, resonance, or coupling values.
6. Compare the extracted value with the DSL target and state tolerance and error.
7. Propose a DSL parameter update, regenerate, verify, and repeat.
8. Preserve solver input, version, log, and non-empty output artifact as provenance.

Read the repository guides under `simulation/` for HFSS, Q3D, ADS, and Sonnet setup.

## Status vocabulary

| Status | Meaning |
| - | - |
| `analytical` | Equations computed; no solver executed |
| `planned` | Simulation planned; input files not prepared |
| `input_files_prepared` | Solver input exists; solver not executed |
| `executed` | Solver ran and produced non-empty output file |
| `failed` | Solver attempted; no valid output |
| `skipped` | Solver unavailable or not configured |

**Only `executed` with a solver-owned output is simulation evidence.** Never infer solver success from a GDS or plot.

## Evidence requirements

- `input_files_prepared` is not a simulation result.
- `executed` requires a solver-owned non-empty result file.
- `physics_verified` requires extracted values compared against the target.
- `fabrication_ready` requires process-specific DRC and expert/foundry/lab review.

## Component routing

- IDC: Bahl/Alley estimate -> FasterCap/FastCap -> C matrix and mutual capacitance; Q3D/HFSS/Sonnet optional correlation.
- CPW: Simons conformal mapping -> openEMS -> scikit-rf -> Z0, S11, S21, effective permittivity.
- Spiral: Wheeler/Mohan -> FastHenry -> L, R, Q; add capacitance before claiming self-resonance.
- Quarter-wave resonator: `L=vp/(4f)` -> openEMS/Meep -> scikit-rf -> f0, Q, S21.
- SQUID: flux quantization/loop area only until a foundry-specific JJ stack and overlap evidence exist.

## Simulation readiness levels

| Level | Meaning |
| - | - |
| 0 | Analytical estimate only |
| 1 | Geometry generated and verified |
| 2 | Solver input prepared |
| 3 | Solver executed and result artifact exists |
| 4 | Result compared against target |
| 5 | Optimization loop implemented |

**No benchmark should claim Level 3+ without a solver-owned output file.**
