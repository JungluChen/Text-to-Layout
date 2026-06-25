---
name: text-to-gds-simulation
description: Run Text-to-GDS solver handoffs and simulations with strict evidence labels. Use for JosephsonCircuits.jl, JoSIM, scqubits, openEMS, Palace, Elmer, FastCap/FastHenry, Touchstone, gain, bandwidth, Ic, Lj, spectra, and solver status audits.
---

# Text-to-GDS Simulation

## When To Use This Skill

Use this skill after a `.sidecar.json` or `physics_graph.json` exists and the
user asks for solver inputs, real solver execution, RF/quantum/circuit results,
or validation of solver evidence.

## Inputs

- `.sidecar.json` for layout-derived device metadata.
- `physics_graph.json` for compiler IR and solver input generation.
- Optional process values such as `jc_ua_per_um2`, capacitance density, substrate
  permittivity, and target frequency.
- Optional measurement files for comparison only, not solver evidence.

## Outputs

- Solver input decks or projects.
- Solver result JSON files.
- Solver-owned output files such as `.s2p`, CSV, JSON, HDF5, or logs.
- `adapter_status` or `status` equal to `executed`, `skipped`, or `failed`.
- Plots only when backed by the source data file.

## Required Files

- `src/text_to_gds/server.py`
- `src/text_to_gds/solver_contract.py`
- `SOLVER_EVIDENCE_CONTRACT.md`
- `scripts/check_external_tools.py`

## Hard Stops

- Do not say `SOLVER EXECUTED` unless an output file exists.
- Do not use analytical CPW or ideal JJ values as simulated values.
- Do not hide skipped solvers.
- Do not count `input_files_prepared`, `installed`, or `binary_found` as
  execution evidence.

## Solver Requirements

- JosephsonCircuits.jl requires Julia plus the package installed.
- JoSIM requires a JoSIM executable.
- scqubits requires an importable Python package and produced eigenvalues.
- openEMS requires a real Touchstone or solver output file for RF evidence.
- Palace, Elmer, FastCap, and FastHenry require their native binaries.

## Example Prompts

- "Run JosephsonCircuits.jl for this JPA sidecar and show the output file."
- "Generate openEMS inputs from this physics graph, but mark execution skipped."
- "Check whether this solver result can count as signoff evidence."

## Example Commands

```bash
uv run python scripts/check_external_tools.py
uv run python examples/zero_to_one_demos.py 40
uv run text-to-gds
```

## Failure Cases

- Missing binary: return `skipped` with install steps.
- Solver returned no output file: return `failed`.
- Output file exists but parser cannot read it: return `failed`.
- User asks for signoff with one solver: cap at Level 4.
