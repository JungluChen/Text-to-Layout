<div align="center">

# Text-to-GDS

**A skills library for superconducting quantum-device layout, simulation, and signoff agents**

[Docs](docs/open_platform_roadmap.md) · [Roadmap](docs/open_platform_roadmap.md) · [Benchmarks](#-benchmarks)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![gdsfactory](https://img.shields.io/badge/gdsfactory-GDSII-00A676?style=flat-square)](https://github.com/gdsfactory/gdsfactory)
[![KLayout](https://img.shields.io/badge/KLayout-DRC-4A5568?style=flat-square)](https://www.klayout.de/)
[![Open EM](https://img.shields.io/badge/EM-openEMS%20%7C%20Palace%20%7C%20Elmer%20%7C%20MEEP-6B46C1?style=flat-square)](docs/opensource_em_solvers.md)
[![MCP](https://img.shields.io/badge/MCP-Tools-6B46C1?style=flat-square)](src/text_to_gds/server.py)

</div>

Text-to-GDS turns a natural-language request into a fabrication-ready GDSII
layout through a closed loop of physics feasibility checking, **open-source** EM
simulation, and a rule-based AI review committee. It is inspired by
[earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad), but
targets multi-layer superconducting quantum ICs instead of mechanical CAD.

> The promise is not "here is a layout." It is **"here is a layout proven to
> work"** — feasibility-checked before generation, simulated on open solvers,
> cross-validated by solver agreement, and passed by every review agent.
> Commercial EDA (HFSS / Q3D / Sonnet) is optional, validation-only.

## ⚡ Example

```python
from text_to_gds.server import run_ai_scientist

result = run_ai_scientist(
    "Design a 6 GHz JPA",
    device="JPA",
    targets_json='{"frequency_ghz": 6.0, "gain_db": 10, "bandwidth_mhz": 100, "quality_factor": 10}',
)
print(result["verdict"])                     # "validated" or "rejected_infeasible"
print(result["artifacts"]["review_report"])  # Markdown review report
```

```text
prompt -> feasibility gate -> gdsfactory PCell -> open EM solve
       -> solver agreement -> AI review committee -> auto-repair
       -> research-readiness verdict -> validated GDS + review report
```

An infeasible request (e.g. *20 dB gain with 2 GHz bandwidth from a single JPA*)
is **rejected at the feasibility stage before any layout is generated**.

## 🧰 Skills

Install the library to give agents focused, local workflows for superconducting
layout generation, DRC, simulation, and signoff.

| Skill | Summary | Source |
| --- | --- | --- |
| **Text-to-GDS** | Generates and validates local GDS layouts with trusted gdsfactory PCells, semantic sidecars, KLayout DRC, and JJ simulation outputs. | [skills/text-to-gds](skills/text-to-gds/SKILL.md) |
| **Simulation** | Runs and interprets ideal JJ, JosephsonCircuits.jl, JoSIM, and ngspice simulation handoffs. | [skills/text-to-gds-simulation](skills/text-to-gds-simulation/SKILL.md) |
| **Circuit Design** | Plans LJPA / JJ / CPW circuit targets before layout. | [skills/text-to-gds-circuit-design](skills/text-to-gds-circuit-design/SKILL.md) |
| **Layout Design** | Compiles, routes, DRC-checks, extracts, and reviews GDS layouts. | [skills/text-to-gds-layout-design](skills/text-to-gds-layout-design/SKILL.md) |
| **Signoff** | Audits generated artifacts, DRC status, simulation, plots, and release validation. | [skills/text-to-gds-signoff](skills/text-to-gds-signoff/SKILL.md) |

## 💻 Installation

**Skills CLI** (preferred):

```bash
npx skills install JungluChen/Text-to-Layout
```

**Plugins** for Codex and Claude Code:

```bash
# Claude Code
claude plugin marketplace add JungluChen/Text-to-Layout
claude plugin install text-to-gds@text-to-gds

# Codex
codex plugin marketplace add JungluChen/Text-to-Layout
codex plugin add text-to-gds@text-to-gds
```

**Local development** (Python 3.11+; on Windows the launcher is usually `py -3`):

```powershell
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
py -3 -m uv sync                     # core
py -3 -m uv sync --extra research    # Optuna, scikit-rf, QCoDeS, scqubits, pyEPR, PyAEDT, gmsh

py -3 -m uv run pytest               # checks
py -3 -m uv run ruff check .
```

Optional local solver toolchains (Julia/JosephsonCircuits.jl, JoSIM, ngspice,
Magic, openEMS, Palace/Elmer) install under a git-ignored `.tools/` and are
discovered automatically — see [docs/simulation_tools.md](docs/simulation_tools.md).
Contributions are welcome on the `main` branch; see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📸 Screenshots

<table>
  <tr>
    <td align="center"><b>Layout (Manhattan JJ)</b><br><img src="assets/manhattan_jj_layout.png" alt="Manhattan JJ layout" width="240"></td>
    <td align="center"><b>3D process stack</b><br><img src="assets/hfss_stack_3d.png" alt="3D process stack" width="240"></td>
    <td align="center"><b>openEMS FDTD extraction</b><br><img src="assets/openems_extraction_example.png" alt="openEMS extraction" width="240"></td>
  </tr>
  <tr>
    <td align="center"><b>Scientific report</b><br><img src="assets/scientific_report_example.png" alt="Scientific report" width="240"></td>
    <td align="center"><b>JPA pump sweep</b><br><img src="assets/jpa_analysis_example.png" alt="JPA analysis" width="240"></td>
    <td align="center"><b>Qubit spectrum (scqubits)</b><br><img src="assets/scqubits_spectrum_example.png" alt="scqubits spectrum" width="240"></td>
  </tr>
</table>

## 🧪 Benchmarks

Benchmarks are lightweight text prompts plus expected artifact families (GDS,
sidecar, DRC, and simulation outputs). The previews are screenshots rendered
from the compiled GDS polygons — regenerate them with the named registered PCell.

| # | Target | Prompt | Preview |
| --- | --- | --- | --- |
| 1 | [Manhattan Josephson Junction](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ, run DRC, and estimate `Ic` and `Lj` for `Jc = 2.0 uA/um²`. | <img src="assets/benchmark_01_manhattan_jj_layout.png" alt="Manhattan JJ" width="200"> |
| 2 | [Compact CMOS Logic Cell](benchmarks/02-compact-cmos-logic-cell.md) | Fit active logic inside `5 µm × 5 µm`, M1/M2/M3 routing, sub-50 ps delay, <100 nW leakage. | <img src="assets/benchmark_02_compact_cmos_logic_layout.png" alt="CMOS logic" width="200"> |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | Route a superconducting splitter with branch `Ic`, output skew, and min-width targets. | <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" alt="SFQ splitter" width="200"> |
| 4 | [JJ Ic Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas and report expected critical current from sidecar metadata. | <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" alt="Calibration array" width="200"> |
| 5 | [CPW Resonator Test](benchmarks/05-cpw-resonator-test.md) | Layout a CPW resonator with frequency, coupling-Q, and gap targets. | <img src="assets/benchmark_05_cpw_resonator_test_layout.png" alt="CPW resonator" width="200"> |
| 6 | [Via-Chain Process Monitor](benchmarks/06-via-chain-monitor.md) | Build a 100-stage via-chain monitor with landing-pad, resistance, and topology targets. | <img src="assets/benchmark_06_via_chain_monitor_layout.png" alt="Via chain" width="200"> |

Functional benchmarks that assert **physical quantities** (not "a file exists")
run via `run_open_benchmarks`: CPW Z0 = 50 Ω / f0 = 6 GHz, IDC C = 0.6 pF (±1%),
and JPA gain — solver-backed rows skip cleanly when a binary is absent.

## ⚙️ How it works

**Open-source-first solvers.** Every analysis type has a first-class open
backend; commercial solvers are validation-only and never ranked primary.

| Analysis | Open backend (default) | Commercial analog (validation only) |
| --- | --- | --- |
| RF S-parameters / Z0 | **openEMS** (FDTD) | HFSS driven-modal |
| Eigenmode f0 / Q | **Palace** (3D FEM) | HFSS eigenmode |
| Capacitance / inductance | **Elmer / FastCap / FastHenry** | Q3D Extractor |
| Field / photonics | **MEEP** (FDTD) | — |
| Nonlinear JPA/JTWPA | **JosephsonCircuits.jl** | — |

The **Solver Agreement Engine** cross-checks a quantity across ≥2 sources plus
theory and returns a confidence score — a single solver is never trusted.

**Rule-based AI review committee.** Four deterministic reviewers (no LLM, no
network) gate every layout: **Physics** (topology, CPW ground-gap, impedance,
junction presence in the extracted GDS), **Microwave** (passivity, reciprocity),
**Fabrication** (DRC → tapeout readiness), and **Measurement** (probe/pump/flux
ports). The committee score is the minimum across reviewers, so any error stays
below the 90 acceptance threshold; an **auto-repair loop** iterates
generate → review → fix until it accepts or the budget is spent.

See [docs/open_platform_roadmap.md](docs/open_platform_roadmap.md) for the full
architecture and per-component status.

## 🧠 MCP tools

Start the local server (`py -3 -m uv run text-to-gds`). 80+ tools grouped by stage:

| Group | Representative tools |
| --- | --- |
| **Orchestration** | `run_ai_scientist`, `run_design_workflow` |
| **Feasibility & templates** | `check_design_feasibility`, `list_physics_templates`, `validate_device_template` |
| **Open solvers** | `route_open_solver`, `cross_validate_solvers`, `export_open_eigenmode`, `extract_open_q3d`, `tune_idc_capacitance` |
| **Review** | `review_layout`, `understand_layout`, `run_open_benchmarks` |
| **Layout & DRC** | `compile_layout`, `run_drc`, `extract_layout`, `run_lvs`, `generate_wafer_level_mask` |
| **Simulation & EM** | `run_simulation`, `export_openems_project`, `export_palace_project`, `export_jpa_analysis` |

List every public function with its signature: `py -3 -m uv run python examples\run_function_demo.py list`.

## 🔬 Validity boundaries

Adapters run the **real** upstream tool when installed and report `skipped`
otherwise — never a fabricated result. Open EM/circuit models are layout-derived
starters; the review committee encodes deterministic rules, not learned judgment;
and bundled PDK / process / cryostat values are demonstration data. Publication
or tapeout still needs calibrated process data, extracted parasitics, mesh
validation, and measured device data.

## 🛠️ Contributing

Issues, PRs, PCell contributions, process-deck adapters, and solver adapters are
welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). The
`plugins/text-to-gds/` copy is generated by `scripts/bundle_plugin.py` and
verified in CI — edit the source tree, not the bundle.

## License

MIT. See [LICENSE](LICENSE).
