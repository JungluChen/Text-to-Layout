# Text-to-GDS

Text-to-GDS is a local-first skills and MCP toolkit for agentic GDSII layout.
It is inspired by [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad),
but targets multi-layer IC and superconducting quantum layouts instead of
mechanical CAD.

The core loop is:

```text
agent prompt -> Python/gdsfactory PCell -> GDSII -> semantic sidecar -> DRC -> simulation
```

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![gdsfactory](https://img.shields.io/badge/gdsfactory-GDSII-00A676?style=for-the-badge)](https://github.com/gdsfactory/gdsfactory)
[![KLayout](https://img.shields.io/badge/KLayout-DRC-4A5568?style=for-the-badge)](https://www.klayout.de/)
[![MCP](https://img.shields.io/badge/MCP-Tools-6B46C1?style=for-the-badge)](src/text_to_gds/server.py)

## What It Provides

- A Python package: `text_to_gds`
- A local MCP server: `text-to-gds`
- A `$text-to-gds` skill for Codex and other skills-compatible agents
- Codex and Claude plugin metadata
- A reviewed starter superconducting PCell:
  `manhattan_josephson_junction`
- GDSII artifact generation through gdsfactory
- Semantic sidecar JSON with ports, bounding boxes, layers, and PCell metadata
- KLayout-backed local DRC shape scanning
- Correct ideal Josephson Junction calculations for `Ic` and `Lj`

For a direct feature mapping against `earthtojake/text-to-cad`, see
[docs/function_parity.md](docs/function_parity.md).

## Skills

Install the library to give agents focused workflows for local superconducting
layout generation, DRC, and simulation handoff.

| Skill | Summary | Source |
| --- | --- | --- |
| Text-to-GDS | Generates and validates local GDS layouts with trusted gdsfactory PCells, semantic sidecars, KLayout-shaped DRC reports, and JJ simulation outputs. | [skills/text-to-gds](skills/text-to-gds/SKILL.md) |

## Installation

For production use, install or clone from `main`; that branch contains the
generated skill and plugin outputs needed by provider installers.

### Skills

Install Text-to-GDS with the Skills CLI:

```bash
npx skills install JungluChen/Text-to-Layout
```

This is the preferred installation path. It installs the `text-to-gds` skill
directly for supported agents.

### Plugins

Provider-native plugin installs are also available for Codex and Claude Code:

```bash
# Codex
codex plugin marketplace add JungluChen/Text-to-Layout
codex plugin add text-to-gds@text-to-gds
```

```bash
# Claude Code
claude plugin marketplace add JungluChen/Text-to-Layout
claude plugin install text-to-gds@text-to-gds
```

Restart your agent if newly installed skills do not appear.

## Local Development

Use Python 3.11 or newer. On Windows, the Python launcher is usually available
as `py -3`.

Install `uv` if needed:

```powershell
py -3 -m pip install --user uv
```

Install dependencies:

```powershell
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
py -3 -m uv sync
```

Run the checks:

```powershell
py -3 -m uv run python -m compileall src scripts examples
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

## MCP Tools

Start the local MCP server over stdio:

```powershell
py -3 -m uv run text-to-gds
```

For local MCP development:

```powershell
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

| Tool | Purpose | Output |
| --- | --- | --- |
| `compile_layout` | Compile a registered PCell into GDS and a semantic sidecar. | `.gds`, `.sidecar.json` |
| `run_drc` | Read GDS with KLayout Python and report min-width style findings. | `.drc.json` |
| `run_simulation` | Compute ideal JJ current and inductance from sidecar metadata. | `.simulation.json` |

## Example Output

Run the complete local toolchain:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py toolchain --output-name manhattan_jj.gds --jc-ua-per-um2 2.0
```

Generated files:

```text
workspace/artifacts/manhattan_jj.gds
workspace/artifacts/manhattan_jj.sidecar.json
workspace/artifacts/manhattan_jj.drc.json
workspace/artifacts/manhattan_jj.sidecar.simulation.json
```

Representative output:

```json
{
  "compile": {
    "status": "compiled",
    "gds_path": "workspace/artifacts/manhattan_jj.gds",
    "sidecar_path": "workspace/artifacts/manhattan_jj.sidecar.json"
  },
  "drc": {
    "schema": "text-to-gds.drc.v0",
    "engine": "klayout_python_bbox",
    "ruleset": "builtin_min_bbox_width",
    "status": "passed",
    "checked_shapes": 3,
    "violations": []
  },
  "simulation": {
    "schema": "text-to-gds.simulation.v0",
    "engine": "mock_jj",
    "junction_area_um2": 0.0484,
    "jc_ua_per_um2": 2.0,
    "critical_current_ua": 0.0968,
    "josephson_inductance_ph": 3399.855149,
    "shunt_capacitance_ff": 0.0
  }
}
```

The full example output shape is documented in
[examples/example_output.md](examples/example_output.md).

Constraint-driven design request examples are documented in
[examples/design_requests.md](examples/design_requests.md).

## Benchmarks

Benchmarks are lightweight text prompts plus expected artifact families. They
mirror the role of `text-to-cad` benchmarks, but use GDS, sidecar, DRC, and
simulation outputs instead of STEP or mesh previews.

| # | Target | Prompt | Expected outputs |
| --- | --- | --- | --- |
| 1 | [Manhattan Josephson Junction](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ with default layers, run DRC, and estimate `Ic` and `Lj` for `Jc = 2.0 uA/um^2`. | GDS, sidecar JSON, DRC JSON, simulation JSON |
| 2 | [Compact CMOS Logic Cell](benchmarks/02-compact-cmos-logic-cell.md) | Fit active logic inside `$5 \mu m \times 5 \mu m$`, use M1/M2/M3 routing, and target sub-50 ps delay with under-100 nW leakage. | GDS, sidecar JSON, DRC JSON, adapter simulation JSON |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | Route a superconducting splitter with branch `Ic`, output skew, and min-width targets. | GDS, sidecar JSON, DRC JSON, JJ/adapter simulation JSON |
| 4 | [JJ IC Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas and report expected critical current from sidecar metadata. | GDS, sidecar JSON, DRC JSON, simulation JSON |
| 5 | [CPW Resonator Test Structure](benchmarks/05-cpw-resonator-test.md) | Layout a CPW resonator with frequency, coupling-Q, and gap targets. | GDS, sidecar JSON, DRC JSON, EM-adapter report JSON |
| 6 | [Via-Chain Process Monitor](benchmarks/06-via-chain-monitor.md) | Build a 100-stage via-chain monitor with landing-pad, resistance, and topology targets. | GDS, sidecar JSON, DRC JSON, extraction-adapter report JSON |

## Simulation Model

The current simulation is intentionally small and deterministic. It is a
correct ideal Josephson Junction calculation for zero-phase, small-signal
inductance. It is not a replacement for JosephsonCircuits.jl, JoSIM, WRSPICE,
or EM extraction.

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

The tests assert these values.

## Repository Structure

```text
Text-to-Layout/
|-- .codex-plugin/
|-- .claude-plugin/
|-- .github/
|-- benchmarks/
|-- docs/
|-- drc/
|-- examples/
|-- plugins/
|   `-- text-to-gds/
|-- scripts/
|-- skills/
|   `-- text-to-gds/
|-- src/
|   `-- text_to_gds/
|-- tests/
`-- workspace/
    `-- artifacts/
```

## Current Limits

- `run_drc` is a built-in KLayout Python geometry scan, not a full process DRC
  deck. Add a real KLayout `.drc` deck before foundry use.
- `run_simulation` computes ideal JJ quantities only. It does not model phase
  bias, shunt dynamics, parasitics, CPW impedance, or microwave response.
- The layer map is a placeholder superconducting stack and must be replaced by
  a real process file before tapeout or publication of process-specific claims.

## Contributing

Text-to-GDS is intended to be an open-source project. Issues, pull requests,
PCell contributions, process-deck adapters, and simulator adapters are welcome.

For local contribution workflow, plugin refresh, and validation guidance, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
