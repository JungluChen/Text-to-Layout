---
name: text-to-gds-layout-design
description: "Generate and iterate Text-to-GDS layout artifacts with gdsfactory PCells, GDS screenshots, semantic sidecars, DRC, extraction, Magic VLSI handoff, CAD-style SVG/DXF/STL/GLB exports, 3D stack previews, and workbench review. Use when the user asks to create, route, inspect, beautify, export, or validate superconducting or IC GDS layouts."
---

# Text-to-GDS Layout Design

Use this skill when the deliverable is GDS layout or visual layout review.

## Workflow

1. Choose a registered PCell from `list_pcells`; add new PCells only when the
   existing library cannot express the circuit.
2. Compile through `compile_layout` so `.gds`, `.layout.png`, and
   `.sidecar.json` are generated together.
3. Run `run_drc`, then `run_process_drc` when process rules should be attempted.
4. Run `extract_layout`, `run_magic_extract`, `export_cad_artifacts`,
   `export_3d_preview`, and optionally `run_simulation`.
5. Return generated paths, DRC status, Magic status, key sidecar ports, 3D
   preview path, CAD export paths, `physical_performance`, and limits of any
   fallback checks.

## Guardrails

- Keep artifacts under `workspace/artifacts/` unless the user gives a path.
- Keep layer tuples and process metadata explicit.
- For monitor structures such as `via_chain_monitor`, report real stage count,
  input/output ports, checked shape count, resistance estimate, and topology
  status instead of using illustrative screenshots.
- Do not claim foundry signoff without a real process deck, Magic tech file when
  extraction matters, and successful run.
