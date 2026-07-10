# Simulation Plan

- Solver: **openEMS**
- Status: **input_files_prepared**
- Readiness: **Level 2 - open-source simulation input prepared**
- Reason: A runnable openEMS/CSXCAD Octave model and manifest were generated.

## Prepared artifacts

- `model`: `examples\benchmarks\02_cpw_50ohm\simulation\openems_model.json`
- `driver`: `examples\benchmarks\02_cpw_50ohm\simulation\openems_model.m`
- `manifest`: `examples\benchmarks\02_cpw_50ohm\simulation\simulation_manifest.json`

## Limitations

- The Octave driver is runnable only with the external openEMS/CSXCAD stack installed.
- Boundary placement and mesh convergence must be reviewed before signoff.

## Status contract

`input_files_prepared` is not a simulation result. Only `executed` with a non-empty solver-owned output is simulation evidence.
