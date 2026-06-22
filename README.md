# Text-to-GDS

**An open-source-first, agentic platform for superconducting quantum-device
layout — that proves a layout works before handing it to you.**

Text-to-GDS turns a natural-language request into a fabrication-ready GDSII
layout through a closed loop of physics feasibility checking, open-source EM
simulation, and a rule-based AI review committee. It is local-first and offline:
every solver, check, and reviewer runs on your machine, and commercial EDA
(HFSS / Q3D / Sonnet) is optional — used only for industrial cross-validation,
never on the critical path.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![gdsfactory](https://img.shields.io/badge/gdsfactory-GDSII-00A676?style=for-the-badge)](https://github.com/gdsfactory/gdsfactory)
[![Open EM](https://img.shields.io/badge/EM-openEMS%20%7C%20Palace%20%7C%20Elmer%20%7C%20MEEP-4A5568?style=for-the-badge)](docs/opensource_em_solvers.md)
[![MCP](https://img.shields.io/badge/MCP-Tools-6B46C1?style=for-the-badge)](src/text_to_gds/server.py)

> The promise is not "here is a layout." It is **"here is a layout proven to
> work"** — feasibility-checked before generation, simulated on open solvers,
> cross-validated by solver agreement, and passed by every review agent.

---

## The pipeline

```text
            natural-language prompt ("Design a 6 GHz JPA")
                              |
                              v
              Feasibility gate — "can this exist?"
        Bode-Fano · Manley-Rowe · Kerr · quantum limit
                              |  (reject impossible specs here)
                              v
              gdsfactory PCell  ->  GDSII + semantic sidecar
                              |
                              v
         Open Solver Manager (open-source first, validation-only commercial)
   openEMS · Palace · Elmer · FastHenry/FastCap · MEEP · JosephsonCircuits.jl
                              |
                              v
               Solver Agreement Engine  (>=2 sources + theory -> confidence %)
                              |
                              v
              Rule-based AI Review Committee
       Physics · Microwave · Fabrication · Measurement
                              |
                       score < 90 ? --> Auto-Repair loop --+
                              |  (regenerate -> review -> fix)
                              v
        Research-readiness score  ->  validated GDS + review report
```

Run the whole thing with one call:

```python
from text_to_gds.server import run_ai_scientist

result = run_ai_scientist(
    "Design a 6 GHz JPA",
    device="JPA",
    targets_json='{"frequency_ghz": 6.0, "gain_db": 10, "bandwidth_mhz": 100, "quality_factor": 10}',
)
print(result["verdict"])                       # "validated" or "rejected_infeasible"
print(result["assessment"]["readiness"]["aggregate"])
print(result["artifacts"]["review_report"])    # Markdown review report
```

An infeasible request (for example *20 dB gain with 2 GHz bandwidth from a single
JPA*) is **rejected at the feasibility stage before any layout is generated**.

---

## Open-source-first architecture

Every analysis type has a first-class open-source backend. Commercial solvers
are demoted to optional validation. `recommend_em_solver` always ranks open
backends above commercial ones and tags the latter `role: validation_only`.

| Analysis | Open backend (default) | Commercial analog (validation only) |
| --- | --- | --- |
| RF S-parameters / Z0 / eps_eff | **openEMS** (FDTD) | HFSS driven-modal |
| Eigenmode f0 / Q / participation | **Palace** (3D FEM) | HFSS eigenmode |
| Capacitance matrix | **Elmer** / **FastCap** | Q3D Extractor |
| Inductance | **FastHenry** | Q3D |
| Field / photonics | **MEEP** (FDTD) | — |
| Nonlinear JPA/JTWPA gain & noise | **JosephsonCircuits.jl** | — |
| Qubit spectra | **scqubits** | — |

- **`open_solver_manager.py`** routes a device to its open backends and runs the
  ones whose binaries are installed (`SolverManager.solve(device, target_accuracy)`).
  `publication` accuracy requires ≥2 open backends to agree; `iteration` requires 1.
- **`solver_agreement.py`** cross-checks a quantity across ≥2 sources plus theory
  and returns a confidence score. **A single solver is never trusted.**
- **`open_q3d.py`** unifies Elmer + FastCap + FastHenry into a Q3D-style C/L
  matrix extractor, with an IDC auto-tune loop that hits a target capacitance
  within tolerance.

See [docs/opensource_em_solvers.md](docs/opensource_em_solvers.md) and, for the
licensed cross-check path, [docs/pyaedt_hfss_q3d.md](docs/pyaedt_hfss_q3d.md).

---

## AI review committee (rule-based, deterministic)

Before a layout is accepted, four reviewers inspect its evidence (sidecar,
simulation, DRC, extracted circuit). They are deterministic Python rules — no
LLM, no API, no network — so every verdict is reproducible and offline.

| Reviewer | Checks |
| --- | --- |
| **Physics** | topology/ports, CPW ground-gap (is Z0 even definable?), impedance realism, frequency match, junction presence in the extracted GDS |
| **Microwave** | S-parameter passivity `|S11|^2+|S21|^2<=1` (skipped for active amplifiers), reciprocity, port count |
| **Fabrication** | DRC violations → a tapeout-readiness score |
| **Measurement** | probe / pump / flux / readout interfaces present and probe-able |

The committee score is the **minimum** across reviewers, so a single error keeps
it below the 90 acceptance threshold — the committee can never approve a layout
that has an error. The **auto-repair loop** (`auto_repair.py`) iterates
generate → review → fix until the committee accepts, the iteration budget is
spent, or a repair stalls (it always terminates and never accepts with an error).

---

## Feasibility gate and device templates

The platform refuses to waste compute on impossible designs. Before generation,
`feasibility_gate.check_design_feasibility(device, targets)` combines a device
physics template (validity ranges + applicable limits) with the physics
constraint engine and returns an ACCEPT/REJECT verdict with reasons.

Device templates live in
[`device_templates/`](src/text_to_gds/device_templates) (CPW, Resonator, JPA,
JTWPA, SFQ, Transmon) and declare each device's must-have features, governing
equations, validity ranges, and which physical limits apply.

---

## What it provides

- A Python package `text_to_gds` and a local **MCP server** with 80+ tools.
- A `text-to-gds` skill (plus simulation / circuit-design / layout-design /
  signoff skills) for Codex, Claude Code, and other skills-compatible agents.
- Reviewed superconducting **PCells**: Manhattan JJ, dc-SQUID, CPW resonator,
  meander inductor, flux-bias line, via chain, ground plane, JJ calibration
  array, lumped-element JPA seed, photonic-crystal STWPA.
- Versioned superconducting **PDKs** (materials, layers, GDS maps, DRC rules) —
  illustrative templates, not signoff data.
- GDS + semantic sidecar, KLayout DRC, equivalent-circuit extraction, LVS, and
  wafer-mask generation.
- Open EM/circuit simulation handoffs that **execute the real upstream library
  when installed** and report `skipped` otherwise — never a fabricated result.
- CAD exports (SVG/DXF/STL/GLB), RF Touchstone export, 3D stack preview, and
  publication-style scientific plots and reports.
- Three callable improvement registries — 340 catalogued capabilities mapping to
  285 distinct implementations (see [docs/improvement_registries.md](docs/improvement_registries.md)).

---

## Installation

### As a skill or plugin

```bash
# Skills CLI (preferred)
npx skills install JungluChen/Text-to-Layout

# Claude Code plugin
claude plugin marketplace add JungluChen/Text-to-Layout
claude plugin install text-to-gds@text-to-gds

# Codex plugin
codex plugin marketplace add JungluChen/Text-to-Layout
codex plugin add text-to-gds@text-to-gds
```

### For local development

Use Python 3.11+. On Windows the launcher is usually `py -3`.

```powershell
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
py -3 -m uv sync                     # core
py -3 -m uv sync --extra research    # optional: Optuna, scikit-rf, QCoDeS, scqubits, pyEPR, PyAEDT, gmsh
```

Optional local solver toolchains (Julia/JosephsonCircuits.jl, JoSIM, ngspice,
Magic, openEMS, Palace/Elmer) install under a git-ignored `.tools/` and are
discovered automatically. See [docs/simulation_tools.md](docs/simulation_tools.md).

Run the checks:

```powershell
py -3 -m uv run python -m compileall src scripts examples
py -3 -m uv run pytest
py -3 -m uv run ruff check .
```

---

## MCP tools

Start the server over stdio:

```powershell
py -3 -m uv run text-to-gds
```

The tools group into the platform stages:

| Group | Representative tools |
| --- | --- |
| **Orchestration** | `run_ai_scientist`, `run_design_workflow`, `run_optimized_design_workflow` |
| **Feasibility & templates** | `check_design_feasibility`, `list_physics_templates`, `validate_device_template` |
| **Open solvers** | `route_open_solver`, `cross_validate_solvers`, `export_open_eigenmode`, `extract_open_q3d`, `tune_idc_capacitance`, `list_em_solvers`, `recommend_em_solver` |
| **Review** | `review_layout`, `understand_layout`, `run_open_benchmarks` |
| **Layout & DRC** | `compile_layout`, `run_drc`, `run_process_drc`, `extract_layout`, `run_lvs`, `generate_wafer_level_mask` |
| **Simulation & EM** | `run_simulation`, `export_openems_project`, `export_palace_project`, `export_elmer_project`, `export_jpa_analysis`, `export_hamiltonian_model` |
| **Exports & reports** | `export_cad_artifacts`, `export_rf_network`, `export_3d_preview`, `export_scientific_report`, `run_validation_checklist` |

The function table is the contract. List every public function with its
signature and one-line description:

```powershell
py -3 -m uv run python examples\run_function_demo.py list
```

---

## PCells, PDKs, and a quick example

```powershell
# Compile a Manhattan Josephson junction, render it, run DRC, estimate Ic/Lj.
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py toolchain --output-name manhattan_jj.gds --jc-ua-per-um2 2.0
```

![Manhattan Josephson Junction layout](assets/manhattan_jj_layout.png)

Load and inspect a PDK:

```python
from text_to_gds.pdk import PDKDatabase

pdk = PDKDatabase("process").get("ncu_alox_2026")
print(pdk.validate_geometry("JJ", width_um=0.08, spacing_um=0.15))
print(pdk.materials["Al"].surface_impedance(6e9))
```

PDK values are illustrative templates — replace them with released foundry or
measured lab data before tapeout.

---

## Functional benchmarks

`run_open_benchmarks` asserts **physical quantities**, never "a file exists":

| Benchmark | Target | Backend |
| --- | --- | --- |
| `01_CPW` | Z0 = 50 ohm, f0 = 6 GHz | analytical + openEMS/Palace agreement |
| `02_IDC` | C = 0.6 pF (+/-1%) | IDC auto-tune -> Elmer/FastCap |
| `03_JPA` | gain 20 dB, BW 500 MHz | JosephsonCircuits.jl (skips without Julia) |

Solver-backed rows **skip cleanly** when a binary is absent — the suite never
turns missing evidence into a pass.

---

## Roadmap and design

The full open-platform plan, with per-item status and acceptance criteria, is in
[docs/open_platform_roadmap.md](docs/open_platform_roadmap.md). Phases 1–6
(open-solver-first stack, feasibility gate, review committee, layout
understanding, functional benchmarks, and the AI-scientist orchestrator) are
implemented; learning device rules from a real reference-layout corpus is
deliberately left data-gated.

Architecture and validity boundaries are documented in
[docs/closed_loop_research.md](docs/closed_loop_research.md) and
[docs/closed_loop_extensions.md](docs/closed_loop_extensions.md).

---

## Validity boundaries (honesty)

- Adapters run the **real** upstream tool when installed and report `skipped`
  otherwise — they never claim a result a tool did not produce.
- Open EM/circuit models are layout-derived **starters**: publication or tapeout
  still needs calibrated process data, extracted parasitics, mesh validation, and
  measured device data.
- The review committee encodes deterministic **rules**, not learned judgment — it
  is a falsifiable gate, not an oracle.
- Bundled PDK / process / cryostat values are demonstration data.

---

## Contributing

Issues, PRs, PCell contributions, process-deck adapters, and solver adapters are
welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for the
local workflow (note: the `plugins/text-to-gds/` copy is generated by
`scripts/bundle_plugin.py` and verified in CI — edit the source tree, not the
bundle).

## License

MIT. See [LICENSE](LICENSE).
