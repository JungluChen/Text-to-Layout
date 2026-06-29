# Simulation Plan

- Solver: **FasterCap/FastCap**
- Status: **input_files_prepared**
- Readiness: **Level 2 - open-source simulation input prepared**
- Reason: FastCap-compatible IDC panel and list files were generated; solver was not run.

## Prepared artifacts

- `panel_file`: `examples\benchmarks\01_idc_0p6pf\simulation\idc.qui`
- `list_file`: `examples\benchmarks\01_idc_0p6pf\simulation\idc.lst`
- `manifest`: `examples\benchmarks\01_idc_0p6pf\simulation\simulation_manifest.json`

## Limitations

- Effective-medium capacitance is not a full air/silicon interface extraction.
- Mesh convergence and a finite-thickness or full-wave cross-check are required.
- Self-resonance and Q are outside this electrostatic model.

## Status contract

`input_files_prepared` is not a simulation result. Only `executed` with a non-empty solver-owned output is simulation evidence.
