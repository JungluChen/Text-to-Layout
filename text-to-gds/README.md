# Text-to-GDS

Text-to-GDS is a local-first tool ecosystem for agentic GDSII layout. It lets
an LLM generate Python layout code, instantiate reviewed superconducting
gdsfactory PCells, write `.gds` files, emit semantic JSON sidecars, run
DRC-shaped checks, and execute layout-derived simulation calculations through an
MCP server.

The project is inspired by `earthtojake/text-to-cad`, but it targets multi-layer
IC and superconducting quantum layouts instead of 3D mechanical CAD.

## What You Get

- A Python package: `text_to_gds`
- An MCP server: `text-to-gds`
- Three MCP tools:
  - `compile_layout`
  - `run_drc`
  - `run_simulation`
- A reviewed starter PCell:
  - `manhattan_josephson_junction`
- Codex and Claude plugin metadata
- A `$text-to-gds` skill with workflow instructions and helper scripts

## Repository Structure

```text
text-to-gds/
|-- .codex-plugin/
|   `-- marketplace.json
|-- .claude-plugin/
|   `-- marketplace.json
|-- .mcp.json
|-- drc/
|   `-- placeholder.drc
|-- examples/
|   `-- manhattan_jj_layout.py
|-- plugins/
|   `-- text-to-gds/
|       |-- .codex-plugin/plugin.json
|       |-- .claude-plugin/plugin.json
|       |-- .mcp.json
|       |-- skills/text-to-gds/
|       `-- src/text_to_gds/
|-- scripts/
|   `-- bundle_plugin.py
|-- skills/
|   `-- text-to-gds/
|-- src/
|   `-- text_to_gds/
|-- tests/
`-- workspace/
    `-- artifacts/
```

## Step 1: Install Python And uv

Use Python 3.11 or newer. On Windows, the Python launcher is usually available
as `py -3`.

Install `uv` if you do not have it:

```powershell
py -3 -m pip install --user uv
```

Confirm it works:

```powershell
py -3 -m uv --version
```

## Step 2: Install Project Dependencies

From the repository root:

```powershell
cd C:\path\to\text-to-gds
py -3 -m uv sync
```

This creates `.venv/` and installs gdsfactory, KLayout's Python package, MCP,
pytest, and ruff.

## Step 3: Run The Test Suite

```powershell
py -3 -m uv run python -m compileall src scripts examples
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

Expected result:

```text
pytest: all tests pass
ruff: All checks passed
```

## Step 4: Generate A GDS Layout

Run the bundled helper:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py toolchain --output-name manhattan_jj.gds --jc-ua-per-um2 2.0
```

The command writes artifacts under `workspace/artifacts/`:

```text
manhattan_jj.gds
manhattan_jj.sidecar.json
manhattan_jj.drc.json
manhattan_jj.sidecar.simulation.json
```

## Step 5: Run The MCP Server

Start the server over stdio:

```powershell
py -3 -m uv run text-to-gds
```

For local MCP development:

```powershell
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

The MCP server registers these tools:

| Tool | Purpose |
| --- | --- |
| `compile_layout` | Compile a registered PCell into GDS and a semantic sidecar |
| `run_drc` | Emit a DRC report with the future KLayout report shape |
| `run_simulation` | Compute ideal Josephson Junction values from sidecar metadata |

## Step 6: Install As A Codex Plugin

Codex discovers this repository through the root marketplace file:

```powershell
codex plugin marketplace add C:\path\to\text-to-gds\.codex-plugin
codex plugin add text-to-gds@text-to-gds
```

After installing, restart or reload Codex so it sees:

- plugin: `text-to-gds`
- skill: `$text-to-gds`
- MCP server: `text-to-gds`

## Step 7: Install As A Claude Plugin

Claude Code uses the parallel marketplace file:

```powershell
claude plugin marketplace add C:\path\to\text-to-gds\.claude-plugin
claude plugin install text-to-gds@text-to-gds
```

Restart or reload Claude Code after installation.

## Step 8: Refresh The Bundled Plugin

The root package and root skill are the editable source. The installable plugin
copy lives under `plugins/text-to-gds`.

After changing `src/`, `skills/`, `examples/`, or `drc/`, refresh the plugin:

```powershell
py -3 scripts\bundle_plugin.py
```

Then validate:

```powershell
py -3 C:\Users\justi\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\text-to-gds
py -3 C:\Users\justi\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\text-to-gds
py -3 C:\Users\justi\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\text-to-gds\skills\text-to-gds
```

## Simulation Model

The current simulation is intentionally small and deterministic. It is a correct
ideal Josephson Junction calculation for zero-phase, small-signal inductance,
not a replacement for JosephsonCircuits.jl, JoSIM, WRSPICE, or EM extraction.

Inputs:

- junction area: `A` in `um^2`
- critical current density: `Jc` in `uA/um^2`

Critical current:

```text
Ic_uA = A_um2 * Jc_uA_per_um2
```

Josephson inductance:

```text
Lj_H = Phi0 / (2 * pi * Ic_A)
Lj_pH = Lj_H * 1e12
Phi0 = 2.067833848e-15 Wb
```

For the default Manhattan JJ:

```text
A = 0.22 um * 0.22 um = 0.0484 um^2
Jc = 2.0 uA/um^2
Ic = 0.0968 uA
Lj = 3399.855149 pH
```

The tests assert these values. Future real simulation adapters should preserve
the JSON output schema while adding engine-specific details.

## Current Limitations

- `run_drc` is a mock adapter with a KLayout-compatible report shape. It does
  not yet execute a real process DRC deck.
- `run_simulation` computes ideal JJ quantities only. It does not model phase
  bias, shunt dynamics, parasitics, CPW impedance, or microwave response.
- The layer map is a placeholder superconducting stack and must be replaced by
  a real process file before foundry use.

