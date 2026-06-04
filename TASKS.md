# TASKS.md

## Phase 0: Scaffold

- [x] Create a Python package under `src/text_to_gds`.
- [x] Add `pyproject.toml` with `uv`-friendly dependency metadata.
- [x] Add repo guidance in `AGENTS.md`.
- [x] Add a placeholder KLayout DRC deck.
- [x] Add a smoke test for the first PCell.
- [x] Add root Codex and Claude marketplace metadata.
- [x] Add a bundled `plugins/text-to-gds` package with MCP and skill manifests.

## Phase 1: MCP Server

- [x] Expose `compile_layout` as a compile tool that writes `.gds`,
  `.layout.png`, and a semantic sidecar JSON file.
- [x] Expose `run_drc` as a KLayout Python geometry adapter with the same report
  shape expected from a future process-deck implementation.
- [x] Expose `run_simulation` as a deterministic ideal Josephson Junction
  calculation from the semantic sidecar.
- [x] Expose planning and inspection tools: `list_pcells`, `extract_layout`,
  `list_simulators`, `plan_ljpa`, and `export_3d_preview`.
- [x] Add an MCP client fixture or protocol-level integration test.
- [x] Add `.mcp.json` for local plugin-backed MCP server startup.

## Phase 2: PCell Library

- [x] Implement `manhattan_josephson_junction` with ports and device metadata.
- [x] Add CPW, meander inductor, flux-bias line, via, and ground-plane PCells.
- [x] Add a process/layer map module with typed layer constants.
- [x] Add PCell parameter validation against fab rule defaults.
- [x] Add `$text-to-gds` skill instructions, references, and helper script.

## Phase 3: KLayout DRC And Sidecars

- [x] Replace mock DRC with KLayout Python GDS geometry execution.
- [x] Add external headless KLayout process-deck execution adapter.
- [x] Add KLayout Python process-rule fallback when external deck execution is
  unavailable or host-runtime dependent.
- [x] Parse `.lyrdb` or JSON DRC output into `text-to-gds.drc.v0`.
- [x] Extract layer bounding boxes and process metadata from generated GDS.
- [x] Extract labels from generated GDS into the sidecar/extraction report.
- [x] Add sample superconducting DRC decks under `drc/`.

## Phase 4: Simulation Adapters

- [x] Add a netlist/extraction interface for layout-derived JJ and CPW elements.
- [x] Add JosephsonCircuits.jl availability and command-plan scaffold.
- [x] Add a JosephsonCircuits.jl command-line adapter.
- [x] Add JoSIM transient deck scaffold.
- [x] Add a JoSIM transient simulation adapter.
- [x] Add a reproducible local toolchain installer for KLayout, Julia,
  JosephsonCircuits.jl, and JoSIM.
- [x] Validate real local JoSIM transient execution and JosephsonCircuits.jl
  package-load execution.
- [x] Preserve mock simulation for local smoke tests without Julia or JoSIM.

## Phase 5: Prompt-To-Layout UX

- [x] Add `plan_ljpa` for prompts such as "Design a 5 GHz LJPA with wide
  bandwidth" and return clarification questions, assumptions, PCells, and
  simulator options.
- [x] Add local 2.5D stack preview export for quick UI/UX review.
- [x] Add a local browser workbench for prompt, plan, layout, DRC, 3D preview,
  and simulation result review.
- [x] Add a live interactive frontend that accepts prompt edits and runs the
  workflow from the browser.
- [x] Add closed-loop optimization that adjusts geometry after simulation
  misses target gain/bandwidth/noise metrics.

## Future Signoff Work

- Add CI/release-host jobs that run `scripts/install_toolchain.ps1` or cached
  equivalent installers.
- Replace the JosephsonCircuits.jl package-load plan with a full
  harmonic-balance circuit model generated from extracted JJ/CPW networks.
- Replace the local surrogate optimizer with external gain/bandwidth/noise
  metrics from JosephsonCircuits.jl, JoSIM, or EM extraction.
