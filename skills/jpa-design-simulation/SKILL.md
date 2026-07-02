---
name: jpa-design-simulation
description: Convert natural-language Josephson parametric amplifier (JPA) requirements into first-principles sizing, typed Layout DSL, deterministic IDC/SQUID/CPW geometry, verification, electrostatic extraction handoffs, superconducting circuit-simulator decks, tuning records, and evidence-backed reports. Use for JPA design-to-layout tasks, JPA simulation planning or execution, IDC capacitance qualification, SQUID-equivalent inductance sizing, JoSIM/PSCAN2/WRspice workflows, and audits of JPA physics-evidence claims in Text-to-Layout.
---

# JPA Design and Simulation

## Scope

Guide JPA work from a natural-language requirement to a reproducible design packet. Treat `src/textlayout` as the main product path. Treat `src/text_to_gds` as legacy compatibility code and do not expand it.

Read these files before acting:

- [workflow.md](workflow.md) for the required stage order and tuning loop.
- [equations.md](equations.md) before sizing the resonator or SQUID.
- [evidence_labels.md](evidence_labels.md) before assigning any status.
- [simulator_backends.md](simulator_backends.md) before selecting or invoking a solver.
- [output_contract.md](output_contract.md) before writing artifacts.

## Allowed Actions

- Parse requirements into typed, unit-explicit design intent.
- Compute analytical starting values and record equations, inputs, assumptions, and uncertainty.
- Select a supported topology from physical and fabrication constraints.
- Emit typed Layout DSL objects.
- Call deterministic, parameterized generators for IDC, SQUID, CPW, pads, and routing.
- Run geometry, connectivity, layer, port, and design-rule verification.
- Prepare and, when installed, execute electrostatic/EM extraction tools.
- Prepare and, when installed, execute JoSIM, PSCAN2, and WRspice circuit simulations.
- Parse real solver-owned output files, compare results with declared tolerances, and tune bounded parameters.
- Produce an honest report with artifact paths, commands, versions, evidence labels, limitations, and failures.

## Hard Stops

- Do not draw arbitrary GDS polygons from natural language. Natural language must terminate at structured intent or typed Layout DSL; deterministic generators own geometry.
- Do not introduce nondeterministic or unparameterized layout generation.
- Do not expand `src/text_to_gds`; add new product behavior only under `src/textlayout`.
- Do not present analytical estimates as solver evidence.
- Prepared solver input is not solver execution; do not present it as execution evidence.
- Do not mark execution without a real subprocess or simulator call and retained output artifacts.
- Do not mark parsed results without a real, non-empty output file.
- Do not use JoSIM, PSCAN2, or WRspice as proof of physical IDC capacitance.
- Do not infer gain from a passive resonance sweep. Require pump, signal, and idler data.
- Do not use `PHYSICS_VERIFIED` unless geometry-level extraction and circuit simulation both pass declared tolerances.
- Do not invent values, output files, simulator versions, or successful status when a backend is absent or fails.

## Required Reasoning Flow

1. Parse the request and normalize all quantities to explicit units.
2. Reject or flag missing requirements that materially determine topology or physics.
3. Write `intent.json` before geometry.
4. Size target inductance, capacitance, loaded Q, and SQUID tunability analytically.
5. Select topology and document why it satisfies the target and available process constraints.
6. Emit typed Layout DSL; never emit freehand geometry.
7. Generate deterministic IDC/SQUID/CPW geometry and stable artifacts.
8. Verify generated and exported geometry before solver preparation.
9. Prepare geometry-level capacitance extraction; execute it only if an appropriate solver is available.
10. Update the circuit model only from traceable analytical or extracted values, preserving provenance.
11. Prepare JoSIM, PSCAN2, and WRspice decks independently.
12. Execute available circuit simulators, retain logs and outputs, and parse only supported metrics.
13. Tune bounded design parameters, regenerating and re-verifying geometry whenever geometry changes.
14. Write the final evidence-backed report without promoting skipped, prepared, analytical, or failed stages.

Follow the detailed 17-stage procedure in [workflow.md](workflow.md).

## Required Output Files

Write the canonical packet under `out/jpa_demo/` as specified in [output_contract.md](output_contract.md). Required top-level files are:

- `intent.json`
- `design_equations.json`
- `layout.json`
- `output.gds`
- `output.svg`
- `verification.json`
- `extraction/capacitance_result.json`
- `simulation/simulation.json`
- `optimization.json`
- `report.md`

If an upstream gate prevents layout or simulation, still write the applicable intent, equation, failure, and report artifacts. Do not create fake downstream outputs merely to complete the tree.

## Required Evidence Labels

Use only the exact labels in [evidence_labels.md](evidence_labels.md). Record each label with status, timestamp, producing command or function, input paths, output paths, backend and version where applicable, tolerances, and reason. Evidence is monotonic only when its prerequisites remain valid; geometry changes invalidate downstream extraction and circuit evidence.

## Simulator Boundaries

- Use FasterCap/FastCap or another declared electrostatic/EM solver for geometry-level capacitance extraction.
- JoSIM, PSCAN2, and WRspice are circuit-level superconducting simulators; use them for circuit-level transient analysis.
- Never substitute a circuit simulator's lumped capacitor value for extracted physical IDC capacitance.
- Keep each backend optional. Absence produces `SKIPPED_SOLVER_ABSENT`, not failure and not execution.
- Require real subprocess execution, version capture, return code, logs, and non-empty output artifacts for an executed label.

See [simulator_backends.md](simulator_backends.md) for backend-specific roles and proof boundaries.

## Acceptance Criteria

- Requirement values and units are captured in `intent.json`; unresolved material assumptions are explicit.
- Analytical L/C/Q/tunability calculations are reproducible from `design_equations.json`.
- Layout is generated only from typed DSL and deterministic generators.
- Geometry verification passes declared checks before extraction or simulation evidence is accepted.
- Solver states distinguish prepared, executed, parsed, checked, skipped, and failed.
- Every executed or parsed claim references retained real artifacts.
- IDC capacitance claims use geometry-level extraction, not JoSIM, PSCAN2, or WRspice.
- Resonance and gain claims identify the data and method used; gain includes pump, signal, and idler data.
- `PHYSICS_VERIFIED` is issued only after both extraction and circuit tolerances pass.
- `report.md` states what is proven, what is analytical, what was skipped, and what failed.

## Failure Handling

- Missing required intent: stop the dependent stage, write `FAILED`, and list the missing fields.
- Physically infeasible analytical sizing: stop geometry generation unless the user explicitly requests an exploratory candidate; report the violated bound.
- Geometry or DRC failure: do not prepare or run downstream solvers from the invalid layout.
- Solver absent: retain prepared inputs when valid and use `SKIPPED_SOLVER_ABSENT`.
- Solver nonzero exit, timeout, empty output, or parse error: use `FAILED`; retain command, logs, return code, and diagnostics.
- Tolerance miss: keep executed and parsed labels, withhold the checked or verified label, then tune within declared bounds or report convergence failure.
- Any geometry change: invalidate prior extraction, circuit-model update, simulations, and `PHYSICS_VERIFIED`; rerun the dependent stages.
- Conflicting simulator results: preserve both results, withhold verification, and report the discrepancy rather than averaging it away.

## Example Requests

- [2.3 GHz JPA](examples/2p3ghz_jpa_prompt.md)
- [6 GHz JPA](examples/6ghz_jpa_prompt.md)
- [IDC-only benchmark](examples/idc_only_prompt.md)
