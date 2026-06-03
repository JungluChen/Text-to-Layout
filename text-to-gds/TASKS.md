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

- [x] Expose `compile_layout` as a mock compile tool that writes `.gds` and a
  semantic sidecar JSON file.
- [x] Expose `run_drc` as a mock DRC adapter with the same report shape expected
  from a future KLayout implementation.
- [x] Expose `run_simulation` as a mock Josephson Junction calculation from the
  semantic sidecar.
- [ ] Add an MCP client fixture or protocol-level integration test.
- [x] Add `.mcp.json` for local plugin-backed MCP server startup.

## Phase 2: PCell Library

- [x] Implement `manhattan_josephson_junction` with ports and device metadata.
- [ ] Add CPW, meander inductor, flux-bias line, via, and ground-plane PCells.
- [ ] Add a process/layer map module with typed layer constants.
- [ ] Add PCell parameter validation against fab rule defaults.
- [x] Add `$text-to-gds` skill instructions, references, and helper script.

## Phase 3: KLayout DRC And Sidecars

- [ ] Replace mock DRC with headless KLayout execution.
- [ ] Parse `.lyrdb` or JSON DRC output into `text-to-gds.drc.v0`.
- [ ] Extract layer bounding boxes, labels, and ports from generated GDS.
- [ ] Add sample superconducting DRC decks under `drc/`.

## Phase 4: Simulation Adapters

- [ ] Add a netlist/extraction interface for layout-derived JJ and CPW elements.
- [ ] Add a JosephsonCircuits.jl command-line adapter.
- [ ] Add a JoSIM transient simulation adapter.
- [ ] Preserve mock simulation for local smoke tests without Julia or JoSIM.
