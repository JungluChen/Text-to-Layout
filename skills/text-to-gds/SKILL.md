---
name: text-to-gds
description: Generate, compile, inspect, DRC-check, preview, plan, and simulate local GDSII layouts for superconducting and quantum IC work using Text-to-GDS, gdsfactory PCells, KLayout-compatible reports, MCP tools, semantic sidecars, 2.5D stack previews, LJPA planning, and local artifact workflows. Use when Codex needs to create or modify parametric GDS layouts, route trusted superconducting PCells, run layout DRC, extract ports/material/layer metadata, plan a Josephson parametric amplifier, or prepare local MCP-driven EDA iterations.
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
DRC, KLayout checks, extracted ports, layer/material/thickness metadata, 2.5D
stack previews, LJPA planning, or ideal JJ current and inductance estimates.

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
- Extraction report: `.extraction.json`.
- Stack preview: `.stack3d.html` and `.stack3d.json`.
- Browser workbench: `.workbench.html`.
- Process layers are placeholders unless the user provides a real stack.
- Prefer registered PCells over raw polygons.
- For open-ended amplifier requests, run or mirror `plan_ljpa` first and ask
  the returned material/process/performance clarifications before designing.

## Available Tools

From a Text-to-GDS project or plugin root:

```bash
py -3 -m uv sync
./scripts/install_toolchain.ps1
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py toolchain --output-name manhattan_jj.gds
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py plan-ljpa "Design a 5 GHz LJPA with wide bandwidth"
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py design-workflow "Design a 5 GHz LJPA with wide bandwidth" --output-name ljpa_seed.gds --simulator josim
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py optimize-design "Design a 5 GHz LJPA with wide bandwidth" --output-name ljpa_optimized.gds
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py ui --host 127.0.0.1 --port 8765
py -3 -m uv run text-to-gds
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

The MCP server exposes:

- `compile_layout` - writes `.gds`, `.layout.png`, and `.sidecar.json`.
- `run_drc` - reads GDS with KLayout Python and writes `.drc.json`.
- `run_process_drc` - attempts external `klayout -b` deck execution, parses
  `.lyrdb`/JSON reports when produced, and falls back to KLayout Python
  process rules when external deck execution is unavailable.
- `extract_layout` - writes `.extraction.json` with dimensions, layers, and
  GDS shape boxes.
- `list_simulators` - reports local JosephsonCircuits.jl and JoSIM availability.
- `plan_ljpa` - returns clarifying questions, assumptions, PCells, and
  simulator choices for LJPA prompts.
- `export_3d_preview` - writes `.stack3d.html` and `.stack3d.json`.
- `run_design_workflow` - runs prompt planning, LJPA seed layout compile, DRC,
  extraction, preview, simulation, and writes `.workbench.html`.
- `run_optimized_design_workflow` - adjusts geometry with a deterministic local
  surrogate before running the design workflow.
- `run_simulation` - computes ideal JJ outputs, can execute a real JoSIM
  transient starter deck, and can execute a JosephsonCircuits.jl package-load
  and command-plan script when the executable is installed or passed through
  `adapter_executable`.

## Required Workflow

1. Identify the requested circuit, process stack assumptions, target output
   paths, and validation gates. For LJPA/JPA requests, start with `plan_ljpa`.
2. Prefer registered PCells from `text_to_gds.pcells` over raw polygons.
3. Compile layouts through the MCP tool `compile_layout` or the skill helper
   script so a `.gds`, `.layout.png`, and `.sidecar.json` are produced together.
4. Run `run_drc` before treating any layout as valid. Use `run_process_drc`
   when process-stack defaults should be checked. Treat both as local iteration
   gates until a foundry-qualified deck is provided.
5. Run `extract_layout` before simulation handoff so material/layer/geometry
   parameters are explicit.
6. Run `run_simulation` when the request includes junction critical current,
   Josephson inductance, capacitance, or other circuit-level targets.
7. Run `export_3d_preview` when the user asks to view the stack, UI, or 3D
   design.
8. Use `run_design_workflow` for prompt-to-artifact LJPA seed runs and return
   the generated workbench path.
9. Use `run_optimized_design_workflow` when the user asks to iterate or optimize
   geometry before external signoff.
10. Report only artifacts and checks that were actually produced.

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
- Treat built-in DRC and process-rule fallback reports as local iteration aids,
  not foundry signoff.
- Keep plugin-bundled skill resources self-contained; do not rely on sibling
  skill imports.

## Final Response Expectations

Final responses should include generated file paths, DRC status, simulation
values when run, explicit assumptions, and any limits of the local adapter used.
