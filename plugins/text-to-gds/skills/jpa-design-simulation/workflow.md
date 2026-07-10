# JPA Design-to-Simulation Workflow

Execute stages in order. Persist stage status and provenance in the output packet. A downstream stage may run only when its prerequisites are valid.

## 1. Parse the user requirement

Extract target center frequency, bandwidth, gain target if any, topology constraints, substrate/process, minimum rules, ports, footprint, simulator preferences, and tolerances. Normalize units. Distinguish user values from documented defaults and unresolved inputs.

## 2. Build `intent.json`

Write a typed, versioned intent before creating geometry. Include source text, normalized requirements, assumptions, constraints, requested outputs, backend policy, and tolerance policy. Mark missing material inputs; do not silently guess foundry data.

## 3. Estimate target L/C using first principles

Use the equations in [equations.md](equations.md). Choose one independently constrained starting value, solve for the other, and record all substitutions in `design_equations.json`. Check practical bounds for on-chip IDC capacitance, total inductance, self-resonance, feature sizes, and footprint.

## 4. Estimate loaded Q from bandwidth

Compute `Q_loaded = f0 / BW`. State that this is a system target, not a layout-extracted or measured Q. Translate it into coupling requirements only through a declared circuit model.

## 5. Estimate SQUID tunability

Calculate `LJ0`, `LJ(phi)`, and `f(phi)` over the requested or safe flux range. Avoid the cosine singularity and record the allowed flux interval, junction symmetry assumption, critical-current basis, stray inductance, and model limitations.

## 6. Generate Layout DSL

Create typed, unit-explicit IDC, SQUID, CPW, routing, pad, layer, and technology objects under the `src/textlayout` contract. Include stable identifiers and deterministic parameters. Do not encode arbitrary polygons supplied by the AI.

## 7. Generate IDC/SQUID/CPW layout

Call registered deterministic generators. Use a fixed technology/layer map, database unit, component placement rules, routing policy, and stable top-cell name. Record generator versions and parameters in `layout.json`.

## 8. Run geometry verification

Check schema validity, parameter bounds, minimum width/gap, layer usage, connectivity, ports, SQUID topology, IDC finger count and spacing, CPW GSG structure, overlaps/shorts, bounding box, and GDS readback. Write `verification.json`. Stop on required-check failure.

## 9. Prepare capacitance extraction

Create geometry-derived FasterCap/FastCap or equivalent electrostatic/EM inputs under `extraction/capacitance_input/`. Record conductor mapping, dielectric stack, units, meshing controls, ports/nets, source GDS hash, command template, and expected outputs. Label only `EXTRACTION_INPUT_PREPARED`.

## 10. Run extraction if a solver exists

Discover the backend and capture its version. Execute a real process, retain command/log/output files, parse the capacitance matrix or supported scalar, validate units and conductor mapping, and write `capacitance_result.json`. If absent, use `SKIPPED_SOLVER_ABSENT`. If execution or parsing fails, use `FAILED`.

## 11. Update the circuit model

Prefer extracted capacitance when valid. Otherwise retain the analytical capacitance with an explicit analytical provenance tag. Update total inductance, stray terms, coupling, junction parameters, and losses only from declared sources. Never relabel analytical values as extracted.

## 12. Prepare JoSIM, PSCAN2, and WRspice decks

Create independent backend directories and decks. Include consistent circuit topology, initial conditions, flux bias, pump/signal sources when requested, sweep plan, transient duration, timestep, probes, and expected output schema. Assign only each backend's `*_INPUT_PREPARED` label.

## 13. Run available simulators

For each backend independently, run a real subprocess, capture version/command/return code/stdout/stderr, and retain non-empty native outputs. Do not treat installed or discovered binaries as execution. Use `SKIPPED_SOLVER_ABSENT` for unavailable optional backends and `FAILED` for attempted unsuccessful runs.

## 14. Parse transient outputs

Parse only actual retained output files. Validate columns, units, sample count, timestep, requested nodes/branches, and run identity. Preserve raw data. Assign the backend's `*_TRANSIENT_PARSED` label only after successful validation.

## 15. Extract valid metrics

Compute resonance from a declared response metric and method. Compute a gain proxy only when the method is explicitly bounded. Assign `GAIN_CHECKED` only with pump, signal, and idler data and a stated definition. Do not infer physical IDC capacitance from circuit transients.

## 16. Tune parameters

Compare extracted capacitance, resonance, bandwidth, tunability, and gain metrics with declared tolerances. Tune bounded parameters in a deterministic order. If geometry changes, regenerate layout, rerun verification and extraction, update the circuit, and rerun simulations. Record every iteration, parameter delta, objective, artifact hashes, evidence labels, and stop reason in `optimization.json`.

## 17. Generate the final report

Write `report.md` with target versus result tables, topology and assumptions, equations, layout and verification summary, backend versions and commands, artifact links, tolerance results, full evidence-label ledger, limitations, failures, and reproducibility instructions. Grant `PHYSICS_VERIFIED` only when geometry-level extraction and circuit simulation both meet their declared tolerances.
