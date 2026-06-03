---
name: text-to-gds
description: Generate, compile, inspect, DRC-check, and simulate local GDSII layouts for superconducting and quantum IC work using Text-to-GDS, gdsfactory PCells, KLayout-compatible reports, MCP tools, semantic sidecars, and local artifact workflows. Use when Codex needs to create or modify parametric GDS layouts, route trusted superconducting PCells, run layout DRC, extract ports/metadata, or prepare local MCP-driven EDA iterations.
---

# Text-to-GDS

Use this skill for local-first superconducting IC layout workflows where Python
code generates `.gds` files, emits semantic sidecars, runs DRC, and optionally
feeds extracted parameters into simulation adapters.

## Required Workflow

1. Identify the requested circuit, process stack assumptions, target output
   paths, and validation gates.
2. Prefer registered PCells from `text_to_gds.pcells` over raw polygons.
3. Compile layouts through the MCP tool `compile_layout` or the skill helper
   script so a `.gds` and `.sidecar.json` are produced together.
4. Run `run_drc` before treating any layout as valid. The current adapter is
   mock-shaped and should be replaced by KLayout once a process deck exists.
5. Run `run_simulation` when the request includes junction critical current,
   Josephson inductance, capacitance, or other circuit-level targets.
6. Report only artifacts and checks that were actually produced.

## Local Commands

From a Text-to-GDS project or plugin root:

```bash
py -3 -m uv sync
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py toolchain --output-name manhattan_jj.gds
```

Use the MCP server directly with:

```bash
py -3 -m uv run text-to-gds
```

or, for MCP development:

```bash
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

## References

- Read `references/mcp-tools.md` before changing MCP tool signatures or return
  JSON shapes.
- Read `references/pcell-authoring.md` before creating or editing PCells.
- Read `references/workflow.md` for the compile -> DRC -> simulation loop.

## Non-Negotiables

- Keep generated artifacts under `workspace/artifacts/` unless the user gives a
  different path.
- Keep process layer tuples explicit in metadata and sidecars.
- Do not claim KLayout DRC or JosephsonCircuits.jl execution unless those
  adapters actually ran.
- Keep plugin-bundled skill resources self-contained; do not rely on sibling
  skill imports.

