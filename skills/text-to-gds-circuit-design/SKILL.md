---
name: text-to-gds-circuit-design
description: Plan superconducting circuit intent before layout. Use for JPA, TWPA, SQUID, transmon, CPW, resonator, SFQ, process assumptions, performance targets, feasibility gates, and solver authority selection.
---

# Text-to-GDS Circuit Design

## When To Use This Skill

Use this skill before generating layout when the user asks for circuit targets,
device feasibility, topology, process assumptions, or solver authority.

## Inputs

- Natural-language circuit prompt.
- Target frequency, gain, bandwidth, impedance, Q, noise, or flux range.
- Process assumptions such as `Jc`, substrate, metal stack, and capacitance
  density.
- Required backend preference if the user specifies one.

## Outputs

- `design_intent.json`.
- Feasibility gate verdict.
- PCell/backend recommendation.
- Required solver list and signoff level target.
- Explicit assumptions and blockers.

## Required Files

- `src/text_to_gds/design_intent.py`
- `src/text_to_gds/feasibility_gate.py`
- `src/text_to_gds/process_database.py`
- `PHYSICS_GRAPH_SCHEMA.md`

## Hard Stops

- Do not generate GDS for physically incoherent targets.
- Do not use local toy PCells when KQCircuits, gdsfactory, or Qiskit Metal can
  handle the requested device.
- Do not mark LLM-provided numbers as physical values.

## Solver Requirements

- JPA/JTWPA gain needs JosephsonCircuits.jl or another real nonlinear circuit
  solver.
- Qubit spectra need scqubits or an equivalent Hamiltonian solver.
- CPW signoff needs openEMS, Palace, Elmer, FastCap, or measured data.

## Example Prompts

- "Plan a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth."
- "Check if this transmon target is feasible before layout."
- "Choose the solver authority for a CPW resonator signoff."

## Example Commands

```bash
uv run python examples/zero_to_one_demos.py 0
uv run text-to-gds
```

## Failure Cases

- Missing required target: return clarification or explicit assumption.
- Infeasible target: stop before layout.
- Solver authority unavailable: mark as required install, not executed.
