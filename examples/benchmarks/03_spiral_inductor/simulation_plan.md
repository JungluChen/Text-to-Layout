# Simulation Plan

- Solver: **FastHenry**
- Status: **input_files_prepared**
- Readiness: **Level 2 - open-source simulation input prepared**
- Reason: A continuous centerline and conductor cross-section were written as FastHenry input.

## Prepared artifacts

- `input`: `examples/benchmarks/03_spiral_inductor/simulation/spiral.inp`
- `manifest`: `examples/benchmarks/03_spiral_inductor/simulation/simulation_manifest.json`

## Limitations

- A prepared deck alone is not evidence; retained Zc.mat and logs are required.
- Normal-metal conductivity=58000000 S/m and thickness=0.2 um; replace these assumptions with process data. Kinetic inductance is not modeled.

## Status contract

`input_files_prepared` is not a simulation result. Only `executed` with a non-empty solver-owned output is simulation evidence.
