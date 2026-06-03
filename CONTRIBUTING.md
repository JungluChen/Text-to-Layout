# Contributing

Text-to-GDS is an open-source local EDA toolkit. Contributions should keep the
agent workflow local-first, reproducible, and explicit about process
assumptions.

## Development Setup

```powershell
py -3 -m pip install --user uv
py -3 -m uv sync
```

## Checks

Run these before opening a pull request:

```powershell
py -3 -m uv run python -m compileall src scripts examples
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

Validate installable skill and plugin outputs after changing `src/`, `skills/`,
`examples/`, `drc/`, or plugin metadata:

```powershell
py -3 scripts\bundle_plugin.py
py -3 C:\Users\justi\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\text-to-gds
py -3 C:\Users\justi\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\text-to-gds
py -3 C:\Users\justi\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\text-to-gds\skills\text-to-gds
```

## Contribution Guidelines

- Keep generated `.gds`, DRC reports, sidecars, and simulation JSON under
  `workspace/artifacts/`.
- Prefer registered PCells over raw polygons in agent-facing workflows.
- Put raw geometry generation inside reviewed PCell implementations.
- Keep layer tuples, material assumptions, critical current density, and DRC
  thresholds explicit.
- Do not claim a real foundry DRC or simulator run unless that adapter actually
  executed.
- Update tests when changing MCP tool return schemas, PCell parameters, or
  simulation formulas.

## Useful Contribution Areas

- Process-specific layer maps.
- Real KLayout `.drc` decks.
- Additional superconducting PCells.
- JosephsonCircuits.jl, JoSIM, WRSPICE, or EM extraction adapters.
- Visual review tools for generated GDS and semantic sidecars.
