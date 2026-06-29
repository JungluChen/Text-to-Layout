# Simulation Plan

- Solver: **FastHenry + Josephson circuit solver**
- Status: **planned**
- Readiness: **Level 1 - geometry generated and verified**
- Reason: Geometry exists, but process-specific junction and conductor parameters are absent.

## Prepared artifacts

- `manifest`: `examples\benchmarks\05_squid_loop\simulation\simulation_manifest.json`

## Limitations

- The two JJ polygons are generic process placeholders.
- No loop-inductance or Josephson simulation is valid until a foundry stack, Ic, and thickness are supplied.

## Status contract

`input_files_prepared` is not a simulation result. Only `executed` with a non-empty solver-owned output is simulation evidence.
