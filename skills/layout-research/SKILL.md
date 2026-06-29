---
name: layout-research
description: Research an IC, RF, microwave, or superconducting layout before geometry generation. Use when a request includes a physical target such as capacitance, inductance, impedance, resonance frequency, coupling, or footprint and must be converted into an evidence-backed Layout DSL.
---

# Layout research

Treat research as a mandatory pre-layout gate. Do not invent geometry or quote an electrical result without a named model and its limits.

## Required workflow

1. Identify the component and measurable physical target.
2. Record explicit units, substrate/process inputs, frequency range, and missing assumptions.
3. Select a published first-principles or analytical model. Record equations, variable definitions, applicability, and references.
4. Calculate an initial geometry. Label every result `analytical`; never call it simulated or fabrication-ready.
5. Explain the role of each geometry parameter and expected parasitics or self-resonance limits.
6. Produce a Pydantic-compatible Layout DSL with `component`, `target`, `parameters`, `rules`, `outputs`, and provenance metadata.
7. Prefer an open-source extraction path: FasterCap/FastCap for IDC capacitance, openEMS for CPW/resonators, FastHenry for inductors, and scikit-rf for real Touchstone post-processing.
8. Prepare or run the simulation honestly. Label inputs `input_files_prepared`; label results `executed` only with a solver-owned output.
9. Produce `analytical_estimate.md`, `simulation_plan.md`, verification, evidence, and limitations beside the Layout DSL.
10. Stop if the evidence is insufficient. Do not pass arbitrary dimensions to a generator.

## IDC minimum evidence

Explain how finger count and overlap increase capacitance, how width affects loss/current handling, how gap controls electric-field concentration and is limited by process spacing, and how finger/bus inductance limits self-resonance. Require capacitance extraction and a full-wave sweep before fabrication.

## Repository commands

Use `POST /layout/research` for structured evidence or run the benchmark generator for a durable evidence file. Keep the result beside the Layout DSL as `evidence.md`.

## Hard stops

- No cited model or equation.
- Units or substrate/process assumptions are missing.
- A requested target is presented as achieved from geometry alone.
- A solver is described as executed without a non-empty solver-owned artifact.
- A benchmark is marked PASS without analytical and simulation-plan files.
