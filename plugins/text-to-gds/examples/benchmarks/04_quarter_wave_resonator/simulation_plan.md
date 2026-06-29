# Simulation Plan

- Solver: **openEMS**
- Status: **input_files_prepared**
- Readiness: **Level 2 - open-source simulation input prepared**
- Reason: Verified geometry, material assumptions, ports, and expected outputs were serialized.

## Prepared artifacts

- `model`: `examples\benchmarks\04_quarter_wave_resonator\simulation\openems_model.json`
- `manifest`: `examples\benchmarks\04_quarter_wave_resonator\simulation\simulation_manifest.json`

## Limitations

- The JSON is a solver-input manifest, not a mesh or solver result.
- Port calibration, boundary placement, mesh convergence, and Touchstone output remain required.

## Status contract

`input_files_prepared` is not a simulation result. Only `executed` with a non-empty solver-owned output is simulation evidence.
