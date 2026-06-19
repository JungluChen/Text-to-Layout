---
name: text-to-gds-circuit-design
description: "Plan superconducting and IC circuit intent before layout in Text-to-GDS. Use when the user asks for LJPA/JPA targets, Josephson junction sizing, CPW/resonator choices, gain/bandwidth/noise tradeoffs, process assumptions, or prompt-to-circuit planning before generating GDS."
---

# Text-to-GDS Circuit Design

Use this skill before layout when the request is about circuit topology,
performance targets, or process assumptions.

## Workflow

1. Run or mirror `plan_ljpa` for amplifier-style prompts.
2. Identify target frequency, bandwidth, gain, impedance, Jc, materials, layer
   stack, pump topology, and simulator authority.
3. Map the circuit intent to registered PCells and explicit parameters.
4. State which requirements are layout constraints, simulation constraints, and
   future signoff constraints.

## Guardrails

- Prefer parameterized cells and sidecar metadata over raw polygons.
- Do not optimize from intuition alone when a simulator-backed metric is
  available.
- Keep assumptions visible in returned JSON, docs, and final summaries.
