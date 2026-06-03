---
name: text-to-gds
description: Generate, compile, inspect, DRC-check, and simulate local GDSII layouts for superconducting and quantum IC work using Text-to-GDS, gdsfactory PCells, KLayout-compatible reports, MCP tools, semantic sidecars, and local artifact workflows. Use when Codex needs to create or modify parametric GDS layouts, route trusted superconducting PCells, run layout DRC, extract ports/metadata, or prepare local MCP-driven EDA iterations.
---

# Text-to-GDS

Provenance: maintained in
[JungluChen/Text-to-Layout](https://github.com/JungluChen/Text-to-Layout).
Use the installed local skill files as the runtime source of truth; the
repository link is for provenance and release review.

## Purpose

Use this skill for local-first superconducting IC layout workflows where Python
code generates `.gds` files, emits semantic sidecars, runs DRC, and optionally
feeds extracted parameters into simulation adapters.

## Use This Skill When

Use this skill when the user asks for GDS, GDSII, gdsfactory layout code,
superconducting PCells, Josephson Junction geometry, circuit sidecars, local
DRC, KLayout checks, extracted ports, layer metadata, or ideal JJ current and
inductance estimates.

Do not use this skill for mechanical CAD, 3D mesh generation, analog circuit
schematics without layout, foundry signoff claims, or electromagnetic
certification unless the user also asks for local GDS layout artifacts.

## Default Assumptions

- Units: microns for geometry and `uA`, `pH`, `fF` for JJ calculations.
- Output root: `workspace/artifacts/`.
- Primary artifact: `.gds`.
- Layout screenshot artifact: `.layout.png`.
- Sidecar artifact: `.sidecar.json`.
- DRC report: `.drc.json`.
- Simulation report: `.simulation.json`.
- Process layers are placeholders unless the user provides a real stack.
- Prefer registered PCells over raw polygons.
- Ask one focused clarification question only when missing process data or
  dimensions would make the layout impossible or unsafe to interpret.

## Available Tools

From a Text-to-GDS project or plugin root:

```bash
py -3 -m uv sync
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py toolchain --output-name manhattan_jj.gds
py -3 -m uv run text-to-gds
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

The MCP server exposes:

- `compile_layout` - writes `.gds`, `.layout.png`, and `.sidecar.json`.
- `run_drc` - reads GDS with KLayout Python and writes `.drc.json`.
- `run_simulation` - computes ideal JJ outputs and writes `.simulation.json`.

## Required Workflow

1. Identify the requested circuit, process stack assumptions, target output
   paths, and validation gates.
2. Prefer registered PCells from `text_to_gds.pcells` over raw polygons.
3. Compile layouts through the MCP tool `compile_layout` or the skill helper
   script so a `.gds`, `.layout.png`, and `.sidecar.json` are produced together.
4. Run `run_drc` before treating any layout as valid. The current built-in
   adapter is a KLayout-backed geometry scan and should be replaced by a full
   process deck for signoff.
5. Run `run_simulation` when the request includes junction critical current,
   Josephson inductance, capacitance, or other circuit-level targets.
6. Report only artifacts and checks that were actually produced.

## References

- Read `references/mcp-tools.md` before changing MCP tool signatures or return
  JSON shapes.
- Read `references/pcell-authoring.md` before creating or editing PCells.
- Read `references/workflow.md` for the compile -> DRC -> simulation loop.

## Non-Negotiables

- Keep generated artifacts under `workspace/artifacts/` unless the user gives a
  different path.
- Keep process layer tuples explicit in metadata and sidecars.
- Do not claim full foundry signoff DRC, JosephsonCircuits.jl, JoSIM, WRSPICE,
  or EM extraction unless those adapters actually ran.
- Treat the built-in DRC as a KLayout-backed geometry scan, not a full process
  rule deck.
- Keep plugin-bundled skill resources self-contained; do not rely on sibling
  skill imports.

## Final Response Expectations

Final responses should include generated file paths, DRC status, simulation
values when run, explicit assumptions, and any limits of the local adapter used.
