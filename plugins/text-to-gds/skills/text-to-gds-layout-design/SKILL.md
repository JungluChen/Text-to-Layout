---
name: text-to-gds-layout-design
description: Generate and inspect Text-to-GDS layout artifacts with professional-backend preference, GDS, sidecar, screenshots, DRC, extraction, physics graph generation, and solver input handoff.
---

# Text-to-GDS Layout Design

## When To Use This Skill

Use this skill when the user asks to create, edit, inspect, or validate a GDS
layout for superconducting or quantum circuit work.

## Inputs

- `design_intent.json` or explicit PCell name and parameters.
- Process stack or PDK name.
- Target output name.
- Optional backend preference: KQCircuits, gdsfactory, Qiskit Metal, or local.

## Outputs

- `.gds`
- `.layout.png`
- `.sidecar.json`
- `.drc.json`
- `.extraction.json`
- `physics_graph.json`
- Solver input directory when requested.

## Required Files

- `src/text_to_gds/server.py`
- `src/text_to_gds/pcells/`
- `src/text_to_gds/layout/backends.py`
- `PHYSICS_GRAPH_SCHEMA.md`

## Hard Stops

- GDS alone is not enough; sidecar and extraction are required for physics.
- CPW layouts must have signal, gap, and ground evidence.
- JPA layouts must include a nonlinear JJ/SQUID model before JPA review can
  pass.
- Do not overwrite `*_layout.png` with benchmark/status panels.

## Solver Requirements

Layout generation does not prove simulation. Generate solver inputs from
`physics_graph.json`, then use the simulation skill to execute real solvers.

## Example Prompts

- "Create a CPW resonator layout and run DRC plus extraction."
- "Regenerate benchmark 05 as separate layout and benchmark panel assets."
- "Extract a physics graph from this sidecar."

## Example Commands

```bash
uv run python examples/zero_to_one_demos.py 20
uv run python scripts/generate_assets.py layouts
```

## Failure Cases

- Unknown PCell: list supported PCells and stop.
- DRC failed: return violations and do not claim valid layout.
- Missing sidecar: cannot pass extraction or signoff.
