---
name: text-to-gds
description: Generate, compile, inspect, DRC-check, preview, plan, simulate, optimize, and export local GDSII layouts for superconducting and quantum IC work using Text-to-GDS, gdsfactory PCells, KLayout-compatible reports, MCP tools, semantic sidecars, 2.5D stack previews, LJPA planning, RF/Touchstone exports, scientific plots, and research handoffs to JosephsonCircuits.jl, scikit-rf, openEMS, Optuna, scqubits, Quantum Metal/Qiskit Metal, and QCoDeS. Use when Codex needs to create or modify parametric GDS layouts, route trusted superconducting PCells, run layout DRC, extract ports/material/layer metadata, plan a Josephson parametric amplifier, or prepare local MCP-driven EDA iterations.
---

# Text-to-GDS

Provenance: maintained in
[JungluChen/Text-to-Layout](https://github.com/JungluChen/Text-to-Layout).
Use the installed local skill files as the runtime source of truth; the
repository link is for provenance and release review.

## Purpose

Use this skill for local-first superconducting IC layout workflows where Python
code generates `.gds` files, emits semantic sidecars, runs DRC, and optionally
feeds extracted parameters into simulation adapters.

## Use This Skill When

Use this skill when the user asks for GDS, GDSII, gdsfactory layout code,
superconducting PCells, Josephson Junction geometry, circuit sidecars, local
DRC, KLayout checks, extracted ports, layer/material/thickness metadata, 2.5D
stack previews, LJPA planning, RF S-parameter exports, openEMS/scqubits/QCoDeS
handoffs, Optuna-style optimization, or ideal JJ current and inductance
estimates.

Do not use this skill for mechanical CAD, 3D mesh generation, analog circuit
schematics without layout, foundry signoff claims, or electromagnetic
certification unless the user also asks for local GDS layout artifacts.

## Default Assumptions

- Units: microns for geometry and `uA`, `pH`, `fF` for JJ calculations.
- Output root: `workspace/artifacts/`.
- Primary artifact: `.gds`.
- Layout screenshot artifact: `.layout.png`.
- Sidecar artifact: `.sidecar.json`.
- DRC report: `.drc.json`.
- Simulation report: `.simulation.json`.
- Simulation plot: `.simulation.png`.
- Scientific plot/data: `.scientific.png`, `.scientific.svg`,
  `.scientific.csv`, `.scientific.json`.
- Extraction report: `.extraction.json`.
- Stack preview: `.stack3d.html` and `.stack3d.json`.
- CAD inspection exports: `.layout.svg`, `.layout.dxf`, `.stack.stl`,
  `.stack.glb`, and `.cad.json`.
- RF network exports: `.s2p`, `.rf.png`, `.rf.csv`, and `.rf.json`.
- Research handoffs: `.openems.py`, `.openems.json`, `.measurement.json`,
  `.qcodes.py`, `.hamiltonian.json`, `.scqubits.py`, `.qmetal.json`,
  `.qmetal.py`, `.optuna.json`, `.optuna.csv`, and `.optuna.png`.
- Browser workbench: `.workbench.html`.
- Validation roadmap: `.validation.json`.
- Process layers are placeholders unless the user provides a real stack.
- Prefer registered PCells over raw polygons.
- For open-ended amplifier requests, run or mirror `plan_ljpa` first and ask
  the returned material/process/performance clarifications before designing.

## Available Tools

From a Text-to-GDS project or plugin root:

```bash
py -3 -m uv sync
./scripts/install_toolchain.ps1
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py toolchain --output-name manhattan_jj.gds
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py plan-ljpa "Design a 5 GHz LJPA with wide bandwidth"
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py design-workflow "Design a 5 GHz LJPA with wide bandwidth" --output-name ljpa_seed.gds --simulator josim
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py optimize-design "Design a 5 GHz LJPA with wide bandwidth" --output-name ljpa_optimized.gds
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py cad-export workspace/artifacts/ljpa_seed.gds
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py scientific-plot workspace/artifacts/ljpa_seed.sidecar.simulation.json
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py rf-export workspace/artifacts/ljpa_seed.sidecar.simulation.json --output-name ljpa_seed
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py openems-project workspace/artifacts/ljpa_seed.sidecar.json --output-name ljpa_seed
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py measurement-plan workspace/artifacts/ljpa_seed.sidecar.json --simulation-path workspace/artifacts/ljpa_seed.sidecar.simulation.json --output-name ljpa_seed
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py hamiltonian-model workspace/artifacts/ljpa_seed.sidecar.json --jc-ua-per-um2 2.0 --flux-bias-phi0 0.25 --output-name ljpa_seed
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py research-optimize workspace/artifacts/ljpa_seed.sidecar.json --n-trials 16 --target-gain-db 20 --target-bandwidth-mhz 500 --min-p1db-dbm -100 --output-name ljpa_seed
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py sweep workspace/artifacts/ljpa_seed.sidecar.json --sweep-parameter jc_ua_per_um2 --start 1 --stop 4 --points 7
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py sweep workspace/artifacts/ljpa_seed.sidecar.json --sweep-parameter flux_bias_phi0 --start -0.5 --stop 0.5 --points 101 --target-frequency-ghz 5 --squid-asymmetry 0.05
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py validate-roadmap --sidecar-path workspace/artifacts/ljpa_seed.sidecar.json
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py ui --host 127.0.0.1 --port 8765
py -3 -m uv run text-to-gds
py -3 -m uv run mcp dev src/text_to_gds/server.py
```

The MCP server exposes:

- `compile_layout` - writes `.gds`, `.layout.png`, and `.sidecar.json`.
- `run_drc` - reads GDS with KLayout Python and writes `.drc.json`.
- `run_process_drc` - attempts external `klayout -b` deck execution, parses
  `.lyrdb`/JSON reports when produced, and falls back to KLayout Python
  process rules when external deck execution is unavailable.
- `extract_layout` - writes `.extraction.json` with dimensions, layers, and
  GDS shape boxes.
- `list_simulators` - reports local JosephsonCircuits.jl and JoSIM availability.
- `list_research_integrations` - reports gdsfactory, JosephsonCircuits.jl,
  scikit-rf, openEMS, Optuna, Quantum Metal/Qiskit Metal, scqubits, and QCoDeS
  availability and adapter roles.
- `plan_ljpa` - returns clarifying questions, assumptions, PCells, and
  simulator choices for LJPA prompts.
- `export_3d_preview` - writes `.stack3d.html` and `.stack3d.json`.
- `export_cad_artifacts` - writes `.layout.svg`, `.layout.dxf`,
  `.stack.stl`, optional `.stack.glb`, and `.cad.json` from GDS layer boxes.
- `export_scientific_plot` - writes a publication-style PNG/SVG/CSV/JSON
  package from a `.simulation.json`.
- `export_rf_network` - writes Touchstone `.s2p`, `.rf.png`, `.rf.csv`, and
  `.rf.json` from simulation results.
- `export_openems_project` - writes `.openems.py` and `.openems.json` EM
  handoff scaffolds.
- `export_measurement_plan` - writes `.measurement.json` and `.qcodes.py`
  measurement-plan scaffolds.
- `export_hamiltonian_model` - writes `.hamiltonian.json` and `.scqubits.py`
  from layout-derived `EJ`/`EC`.
- `export_quantum_metal_bridge` - writes `.qmetal.json` and `.qmetal.py`
  mapping Text-to-GDS concepts to Quantum Metal/Qiskit Metal concepts.
- `run_research_optimization` - writes `.optuna.json`, `.optuna.csv`, and
  `.optuna.png` using Optuna when installed or a deterministic fallback.
- `run_traveling_wave_paper_benchmark` - writes JSON/CSV/PNG evidence for the
  Planat STWPA and Erickson-Pappas KIT references. Treat linear band results as
  independent calculations and gain magnitude as paper-calibrated reduced-order output.
- `run_gaydamachenko_jtwpa_benchmark` - reproduces the typed 1500-cell
  dispersion-loaded 3WM-JTWPA reference using vectorized transfer matrices,
  then writes gain, reflection, phase-mismatch, and coherence-length evidence.
- `list_fabrication_processes` / `plan_process_aware_jpa` - resolve measured
  process records, correct JJ area, and report expected Ic yield.
- `run_uncertainty_analysis` - writes Monte Carlo JSON/CSV and
  `.yield_report.png` from process, lithography, and capacitance variation.
- `export_hfss_project`, `export_pyaedt_project`, `export_q3d_extract`,
  `export_sonnet_project`, and `export_epr_analysis` - generate process-mapped
  industrial EM and pyEPR handoffs. PyAEDT execution is only claimed when its
  generated result manifest reports successful AEDT execution.
- `recommend_pyaedt_design_correction` / `run_pyaedt_design_iteration` /
  `run_pyaedt_benchmarks` - feed real EM error back into geometry and keep
  missing licensed solver evidence as skips.
- `export_measurement_recipe` / `analyze_cryostat_input_chain` - produce
  publication-style measurement maps and cryogenic noise/power budgets.
- `run_analytical_verification`, `run_paper_benchmarks`, and
  `record_experiment_feedback` - connect theory, regression evidence, measured
  results, and next-design correction.
- `run_parameter_sweep` - sweeps local layout-derived circuit parameters and
  writes JSON plus scientific PNG/SVG/CSV outputs.
- `run_validation_checklist` - writes `.validation.json` following the
  academic/industrial validation roadmap.
- `run_design_workflow` - runs prompt planning, LJPA seed layout compile, DRC,
  extraction, preview, CAD exports, simulation, scientific plots, and writes
  `.workbench.html`.
- `run_optimized_design_workflow` - adjusts geometry with a deterministic local
  surrogate before running the design workflow.
- `run_simulation` - computes ideal JJ outputs, can execute a real JoSIM
  transient starter deck, and can execute JosephsonCircuits.jl harmonic-balance
  starter models when the executable is installed or passed through
  `adapter_executable`. Use `analysis_mode="auto"` for JosephsonCircuits:
  LJPA sidecars select a two-port S-parameter model, while standalone JJ
  sidecars select the single-port reflection model.
  Every run writes a Python-rendered `.simulation.png` and a scientific
  PNG/SVG/CSV package.
  For LJPA/SQUID sidecars, use `flux_bias_phi0`, `squid_asymmetry`, and coil
  period/mutual-inductance options to report Aharonov-Bohm flux tuning.

Focused companion skills:

- `$text-to-gds-simulation` for `Ic`, `Lj`, S-parameters, transient output,
  and simulation plots.
- `$text-to-gds-circuit-design` for topology, performance targets, and process
  assumptions before layout.
- `$text-to-gds-layout-design` for PCell/GDS/DRC/extraction/3D review.
- `$text-to-gds-signoff` for artifact and validation audits.

## Required Workflow

1. Identify the requested circuit, process stack assumptions, target output
   paths, and validation gates. For LJPA/JPA requests, start with `plan_ljpa`.
2. Prefer registered PCells from `text_to_gds.pcells` over raw polygons.
3. Compile layouts through the MCP tool `compile_layout` or the skill helper
   script so a `.gds`, `.layout.png`, and `.sidecar.json` are produced together.
4. Run `run_drc` before treating any layout as valid. Use `run_process_drc`
   when process-stack defaults should be checked. Treat both as local iteration
   gates until a foundry-qualified deck is provided.
5. Run `extract_layout` before simulation handoff so material/layer/geometry
   parameters are explicit.
6. Run `run_simulation` when the request includes junction critical current,
   Josephson inductance, capacitance, S-parameters, or other circuit-level
   targets.
7. Run `export_cad_artifacts` when the user needs CAD-style review,
   interchange files, or a 3D stack solid derived from GDS.
8. Run `export_scientific_plot` or `run_parameter_sweep` when the user asks for
   plots, gain/bandwidth trends, saturation, `Ic`, `Lj`, or physical
   performance comparisons. Use `sweep_parameter="flux_bias_phi0"` for SQUID
   flux tuning curves.
9. Run `export_rf_network` when the user asks for S-parameters, Touchstone,
   scikit-rf, VNA-style review, or RF network data.
10. Run `export_openems_project`, `export_measurement_plan`,
   `export_hamiltonian_model`, or `export_quantum_metal_bridge` only when the
   user asks for EM, lab, Hamiltonian, or Quantum Metal handoff artifacts.
11. Run `run_traveling_wave_paper_benchmark` for photonic-crystal STWPA or
   periodically loaded KIT/TWPA paper-parity requests; report its `parity_scope`.
12. Run `run_gaydamachenko_jtwpa_benchmark` when the request needs a scalable
   3WM-JTWPA paper reproduction or periodic-loading design evidence.
13. For fabrication prompts, resolve a process record before layout and include
   uncertainty/yield evidence. Never present demonstration process data as measured.
14. Use HFSS/Sonnet/pyEPR exports only as prepared handoffs unless the external
   solver actually executed and returned field or participation data.
15. Run `run_research_optimization` for Optuna-style constrained optimization;
   state whether it used Optuna or the fallback grid.
16. Run `export_3d_preview` when the user asks to view the stack, UI, or 3D
   design. Use the live UI for interactive 3D stack and simulation plot review.
17. Run `run_validation_checklist` when the user asks about roadmap,
   academic/industrial validation, or publication-readiness evidence.
18. Use `run_design_workflow` for prompt-to-artifact LJPA seed runs and return
   the generated workbench path.
19. Use `run_optimized_design_workflow` when the user asks to iterate or optimize
   geometry before external signoff.
20. Report only artifacts and checks that were actually produced.

## References

- Read `references/mcp-tools.md` before changing MCP tool signatures or return
  JSON shapes.
- Read `references/pcell-authoring.md` before creating or editing PCells.
- Read `references/workflow.md` for the compile -> DRC -> simulation loop.

## Non-Negotiables

- Keep generated artifacts under `workspace/artifacts/` unless the user gives a
  different path.
- Keep process layer tuples explicit in metadata and sidecars.
- Do not claim full foundry signoff DRC, JosephsonCircuits.jl, JoSIM, WRSPICE,
  or EM extraction unless those adapters actually ran.
- Do not claim RF phase, measured S-parameters, EM fields, instrument data, or
  Hamiltonian signoff from generated handoff files alone.
- Treat built-in DRC and process-rule fallback reports as local iteration aids,
  not foundry signoff.
- Keep plugin-bundled skill resources self-contained; do not rely on sibling
  skill imports.

## Final Response Expectations

Final responses should include generated file paths, DRC status, simulation
values when run, explicit assumptions, and any limits of the local adapter used.
