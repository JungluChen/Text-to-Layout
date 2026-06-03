# AGENTS.md

This repository is a local-first EDA harness for generating superconducting
GDS layouts through registered PCells and exposing layout tools through MCP.

## Operating Model

- Keep all layout generation, DRC, and simulation execution local. Do not add a
  cloud backend or remote service dependency for core workflows.
- Treat generated `.gds`, sidecar JSON, DRC reports, and simulation outputs as
  artifacts. Write them under `workspace/artifacts/` unless a user explicitly
  requests another path.
- Prefer trusted registered PCells over raw polygons in agent-generated layout
  code. Raw polygons are acceptable inside reviewed PCell implementations.
- Keep fab/process data explicit: layer maps, material constants, critical
  current density, kinetic inductance, and DRC thresholds must be named inputs
  or documented defaults.
- Treat KLayout, JosephsonCircuits.jl, JoSIM, and future extraction engines as
  adapters around the core Python package. Mock adapters should preserve the
  final report shape.

## Project Layout

- `src/text_to_gds/server.py`: MCP server entry point and tool registration.
- `src/text_to_gds/pcells/`: reviewed superconducting PCell library.
- `skills/text-to-gds/`: source skill used by local agents.
- `plugins/text-to-gds/`: bundled Codex/Claude plugin copy.
- `drc/`: KLayout DRC decks and placeholders.
- `examples/`: runnable examples that exercise the package.
- `tests/`: package smoke and regression tests.
- `workspace/artifacts/`: local generated outputs.

## Development Rules

- Use `uv` for dependency management when available. If `uv` is missing on
  Windows, bootstrap it with `py -3 -m pip install uv`.
- Keep public tools typed and return JSON-serializable dictionaries.
- Add or update tests whenever MCP tool behavior or PCell parameters change.
- Keep `plugins/text-to-gds/skills/text-to-gds` and
  `plugins/text-to-gds/src/text_to_gds` refreshed from the root source before
  plugin validation or publishing.
- Do not commit `.venv/`, caches, local credentials, or large generated
  artifacts unless they are deliberate fixtures.

## Checks

Run the smallest check that covers the change:

```bash
py -3 -m uv run python -m compileall src
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

Validate plugin metadata after changing plugin files:

```bash
py -3 C:/Users/justi/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/text-to-gds
py -3 C:/Users/justi/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/text-to-gds
```
