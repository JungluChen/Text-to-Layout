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
- Reviewed starter superconducting PCells:
  `manhattan_josephson_junction`, `cpw_straight`, `meander_inductor`,
  `flux_bias_line`, `via_stack`, and `ground_plane`
- GDSII artifact generation through gdsfactory
- Layout screenshot PNG generation for quick visual inspection
- Semantic sidecar JSON with ports, bounding boxes, layers, process stack, and
  PCell metadata
- KLayout-backed local DRC shape scanning
- Correct ideal Josephson Junction calculations for `Ic` and `Lj`
- External simulator adapters for JoSIM transient runs and
  JosephsonCircuits.jl package-load/command-plan runs
- Prompt planning for LJPA requests, including clarification questions and
  simulator selection
- A local browser workbench that shows prompt, plan, layout screenshot, 2.5D
  stack preview, DRC status, extraction parameters, and simulation output
- A live local UI server for browser-driven prompt edits and workflow runs
- A deterministic surrogate optimizer for first-pass LJPA geometry iteration

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

Install the optional local simulator toolchain:

```powershell
# Installs portable Julia 1.12.6, JosephsonCircuits.jl, and JoSIM v2.7 under .tools/
.\scripts\install_toolchain.ps1

# Or install one adapter at a time
.\scripts\install_toolchain.ps1 -InstallJulia
.\scripts\install_toolchain.ps1 -InstallJoSIM
```

The `.tools/` directory is intentionally ignored by git. The adapters discover
those local tools automatically, so no global PATH change is required. Check
what the project can see:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulators
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
| `list_pcells` | List registered PCells and process-stack defaults. | JSON |
| `compile_layout` | Compile a registered PCell into GDS, screenshot, and semantic sidecar. | `.gds`, `.layout.png`, `.sidecar.json` |
| `run_drc` | Read GDS with KLayout Python and report min-width style findings. | `.drc.json` |
| `run_process_drc` | Attempt external `klayout -b` deck execution, then fall back to KLayout Python process rules when needed. | `.process.drc.json`, optional `.lyrdb` |
| `extract_layout` | Summarize sidecar parameters and layer bounding boxes for simulation handoff. | `.extraction.json` |
| `list_simulators` | Report local JosephsonCircuits.jl and JoSIM adapter availability. | JSON |
| `plan_ljpa` | Convert prompts like "Design a 5 GHz LJPA with wide bandwidth" into questions, assumptions, PCells, and workflow. | JSON |
| `export_3d_preview` | Export a local 2.5D process-stack preview from GDS layer boxes. | `.stack3d.html`, `.stack3d.json` |
| `run_design_workflow` | Run the prompt-to-artifacts LJPA seed flow and write a local workbench. | `.gds`, `.layout.png`, `.sidecar.json`, `.drc.json`, `.extraction.json`, `.simulation.json`, `.stack3d.html`, `.workbench.html` |
| `run_optimized_design_workflow` | Run local surrogate geometry optimization before the LJPA seed workflow. | optimized GDS/workbench artifact set plus optimization history |
| `run_simulation` | Compute ideal JJ current/inductance and optionally execute JoSIM or JosephsonCircuits.jl adapters. | `.simulation.json`, optional `.josim.cir`, `.josim.csv`, `.josephsoncircuits.jl` |

## Example Output

Run the complete local toolchain:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py toolchain --output-name manhattan_jj.gds --jc-ua-per-um2 2.0
```

Generated files:

```text
workspace/artifacts/manhattan_jj.gds
workspace/artifacts/manhattan_jj.layout.png
workspace/artifacts/manhattan_jj.sidecar.json
workspace/artifacts/manhattan_jj.drc.json
workspace/artifacts/manhattan_jj.sidecar.extraction.json
workspace/artifacts/manhattan_jj.sidecar.simulation.json
workspace/artifacts/manhattan_jj.stack3d.html
```

Example layout screenshot:

![Manhattan Josephson Junction layout screenshot](assets/manhattan_jj_layout.png)

Representative output:

```json
{
  "compile": {
    "status": "compiled",
    "gds_path": "workspace/artifacts/manhattan_jj.gds",
    "screenshot_path": "workspace/artifacts/manhattan_jj.layout.png",
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

Simulator selection and LJPA paper references are documented in
[docs/simulation_tools.md](docs/simulation_tools.md).

Run a real JoSIM transient after compiling a layout:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\manhattan_jj.sidecar.json --simulator josim --jc-ua-per-um2 2.0
```

That writes a `.josim.cir` starter deck, a `.josim.csv` transient output file,
and records parsed voltage/phase rows in `.josim.json`.

The built-in and external KLayout DRC paths are documented in
[docs/klayout_drc.md](docs/klayout_drc.md).

The intended local workbench UX is documented in
[docs/ui_ux_workflow.md](docs/ui_ux_workflow.md).

Run the first-pass LJPA workflow from the prompt in this README:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py design-workflow "Design a 5 Ghz LJPA with wilde bandwidth" --output-name ljpa_seed.gds --jc-ua-per-um2 2.0
```

That command writes `workspace/artifacts/ljpa_seed.workbench.html`, which can
be opened locally in a browser.

Run the same prompt-to-layout workflow with the real JoSIM adapter:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py design-workflow "Design a 5 Ghz LJPA with wilde bandwidth" --output-name ljpa_josim.gds --jc-ua-per-um2 2.0 --simulator josim
```

When JoSIM is installed, the workflow status is
`completed_with_external_simulation` and the simulation result includes parsed
transient rows from `.josim.csv`.

Run the live local browser UI:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py ui --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765`. The page accepts prompt edits, simulator
selection, and can run the normal or optimized local workflow.

## Benchmarks

Benchmarks are lightweight text prompts plus expected artifact families. They
mirror the role of `text-to-cad` benchmarks, but use GDS, sidecar, DRC, and
simulation outputs instead of STEP or mesh previews. The `Expected layout`
column renders the expected output layout screenshot PNG.

| # | Target | Prompt | Expected layout |
| --- | --- | --- | --- |
| 1 | [Manhattan Josephson Junction](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ with default layers, run DRC, and estimate `Ic` and `Lj` for `Jc = 2.0 uA/um^2`. | <img src="assets/benchmark_01_manhattan_jj_layout.png" alt="Manhattan Josephson Junction output layout screenshot" width="220"> |
| 2 | [Compact CMOS Logic Cell](benchmarks/02-compact-cmos-logic-cell.md) | Fit active logic inside `$5 \mu m \times 5 \mu m$`, use M1/M2/M3 routing, and target sub-50 ps delay with under-100 nW leakage. | <img src="assets/benchmark_02_compact_cmos_logic_layout.png" alt="Compact CMOS logic output layout screenshot" width="220"> |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | Route a superconducting splitter with branch `Ic`, output skew, and min-width targets. | <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" alt="SFQ pulse splitter output layout screenshot" width="220"> |
| 4 | [JJ IC Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas and report expected critical current from sidecar metadata. | <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" alt="JJ critical-current calibration array output layout screenshot" width="220"> |
| 5 | [CPW Resonator Test Structure](benchmarks/05-cpw-resonator-test.md) | Layout a CPW resonator with frequency, coupling-Q, and gap targets. | <img src="assets/benchmark_05_cpw_resonator_test_layout.png" alt="CPW resonator test output layout screenshot" width="220"> |
| 6 | [Via-Chain Process Monitor](benchmarks/06-via-chain-monitor.md) | Build a 100-stage via-chain monitor with landing-pad, resistance, and topology targets. | <img src="assets/benchmark_06_via_chain_monitor_layout.png" alt="Via-chain process monitor output layout screenshot" width="220"> |

## Simulation Model

The default simulation is intentionally small and deterministic. It is a
correct ideal Josephson Junction calculation for zero-phase, small-signal
inductance. JoSIM and JosephsonCircuits.jl are local external adapters:
Text-to-GDS reports whether their executables are available, writes and runs a
JoSIM transient starter deck when requested, and emits/runs a
JosephsonCircuits.jl package-load plus command-plan script. It does not claim
those tools ran unless they are actually executed locally.

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
|-- assets/
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
- `run_process_drc` attempts external `klayout -b` first. If that executable is
  missing or cannot execute the deck, it falls back to headless KLayout Python
  process rules and records the external command/warnings in the JSON report.
- `run_simulation` computes ideal JJ quantities by default. It can execute a
  real JoSIM transient deck and a JosephsonCircuits.jl package-load/plan script
  when the local tools are installed. Full phase bias, parasitics, CPW
  impedance, and microwave gain/noise response still require a richer extracted
  circuit model and measured process data.
- The layer map is a placeholder superconducting stack and must be replaced by
  a real process file before tapeout or publication of process-specific claims.
- The 2.5D preview is a local UX/review aid based on layer bounding boxes, not a
  field solver or electromagnetic model.
- The optimizer is a deterministic local surrogate for first-pass geometry. It
  is not a replacement for simulator-backed gain/noise/bandwidth optimization.

## Contributing

Text-to-GDS is intended to be an open-source project. Issues, pull requests,
PCell contributions, process-deck adapters, and simulator adapters are welcome.

For local contribution workflow, plugin refresh, and validation guidance, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
