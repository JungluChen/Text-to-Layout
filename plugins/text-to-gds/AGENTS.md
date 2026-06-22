# AGENTS.md

Local-first EDA harness for superconducting GDS layout via registered PCells
and MCP tools. Python 3.11+, gdsfactory, KLayout, optional JosephsonCircuits.jl
and openEMS adapters.

## Checks

```bash
py -3 -m uv run python -m compileall src scripts examples
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

Ruff config: line-length 100, target-version py311.

Full test suite (`tests/`, 19 files) requires optional extras:
`py -3 -m uv run pytest` runs the pure-Python core without extras. Some tests
(e.g. `test_paper_benchmarks.py`) need `--extra research` for upstream adapters.

After changing plugin or skill files, validate:
```bash
py -3 C:/Users/justi/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/text-to-gds
py -3 C:/Users/justi/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/text-to-gds
```

## Project Layout

- `src/text_to_gds/server.py` — MCP server entry point (~2,370 lines, all tool registration).
- `src/text_to_gds/rendering.py` — pure layout-screenshot/geometry-scan helpers used by the server.
- `src/text_to_gds/pcells/` — reviewed superconducting PCell library.
- `src/text_to_gds/improvements.py` / `next_improvements.py` / `third_wave.py` — three registries cataloguing 340 numbered improvement entries that map to 285 distinct callables.
- `skills/text-to-gds/` — primary agent skill (source of truth).
- `skills/text-to-gds-simulation/`, `skills/text-to-gds-circuit-design/`, `skills/text-to-gds-layout-design/`, `skills/text-to-gds-signoff/` — task-specific skills.
- `plugins/text-to-gds/` — bundled Codex/Claude plugin copy (keep synced from root).
- `process/` — versioned PDK YAML files (`ncu_alox_2026`, `mit_ll_sfq`, `ibm_nb`, `custom_process`).
- `drc/` — KLayout DRC decks.
- `examples/` — runnable examples.
- `tests/` — smoke and regression tests.
- `workspace/artifacts/` — generated outputs (gitignored).

## Operating Model

- All layout, DRC, and simulation execution stays local. No cloud backends.
- Generated `.gds`, sidecar JSON, DRC reports, and simulation outputs are
  artifacts — write under `workspace/artifacts/` unless user says otherwise.
- Prefer trusted registered PCells over raw polygons in agent-generated code.
  Raw polygons are acceptable inside reviewed PCell implementations.
- Fab/process data (layer maps, material constants, Jc, kinetic inductance,
  DRC thresholds) must be named inputs or documented defaults.

## Development Rules

- Use `uv` for dependency management: `py -3 -m uv sync` (core) or
  `py -3 -m uv sync --extra research` (all optional adapters).
- Keep public tools typed; return JSON-serializable dictionaries.
- `.tools/` is gitignored and contains portable Julia, JoSIM, ngspice, and
  Magic WSL wrappers discovered automatically by adapters.
- Do not commit `.venv/`, caches, or large generated artifacts.
