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

- [x] Expose `compile_layout` as a compile tool that writes `.gds`,
  `.layout.png`, and a semantic sidecar JSON file.
- [x] Expose `run_drc` as a KLayout Python geometry adapter with the same report
  shape expected from a future process-deck implementation.
- [x] Expose `run_simulation` as a deterministic ideal Josephson Junction
  calculation from the semantic sidecar.
- [x] Expose planning and inspection tools: `list_pcells`, `extract_layout`,
  `list_simulators`, `plan_ljpa`, and `export_3d_preview`.
- [x] Add an MCP client fixture or protocol-level integration test.
- [x] Add `.mcp.json` for local plugin-backed MCP server startup.

## Phase 2: PCell Library

- [x] Implement `manhattan_josephson_junction` with ports and device metadata.
- [x] Add CPW, meander inductor, flux-bias line, via, and ground-plane PCells.
- [x] Add a real `via_chain_monitor` PCell with 100-stage topology, I/O ports,
  DRC coverage, resistance metadata, and corrected benchmark screenshot output.
- [x] Add a process/layer map module with typed layer constants.
- [x] Add PCell parameter validation against fab rule defaults.
- [x] Add `$text-to-gds` skill instructions, references, and helper script.

## Phase 3: KLayout DRC And Sidecars

- [x] Replace mock DRC with KLayout Python GDS geometry execution.
- [x] Add external headless KLayout process-deck execution adapter.
- [x] Add KLayout Python process-rule fallback when external deck execution is
  unavailable or host-runtime dependent.
- [x] Parse `.lyrdb` or JSON DRC output into `text-to-gds.drc.v0`.
- [x] Extract layer bounding boxes and process metadata from generated GDS.
- [x] Extract labels from generated GDS into the sidecar/extraction report.
- [x] Add sample superconducting DRC decks under `drc/`.

## Phase 4: Simulation Adapters

- [x] Add a netlist/extraction interface for layout-derived JJ and CPW elements.
- [x] Add JosephsonCircuits.jl availability and harmonic-balance starter scaffold.
- [x] Add a JosephsonCircuits.jl command-line adapter.
- [x] Add JoSIM transient deck scaffold.
- [x] Add a JoSIM transient simulation adapter.
- [x] Add a reproducible local toolchain installer for KLayout, Julia,
  JosephsonCircuits.jl, and JoSIM.
- [x] Validate real local JoSIM transient execution and JosephsonCircuits.jl
  harmonic-balance starter execution.
- [x] Preserve mock simulation for local smoke tests without Julia or JoSIM.
- [x] Add automatic JosephsonCircuits.jl `auto` analysis mode with two-port
  LJPA S-parameter output for `lumped_element_jpa_seed` and single-port
  reflection fallback for standalone JJ sidecars.

## Phase 5: Prompt-To-Layout UX

- [x] Add `plan_ljpa` for prompts such as "Design a 5 GHz LJPA with wide
  bandwidth" and return clarification questions, assumptions, PCells, and
  simulator options.
- [x] Add local 2.5D stack preview export for quick UI/UX review.
- [x] Add a local browser workbench for prompt, plan, layout, DRC, 3D preview,
  and simulation result review.
- [x] Add a live interactive frontend that accepts prompt edits and runs the
  workflow from the browser.
- [x] Redesign the live frontend with Apple-style controls, artifact serving,
  3D stack review, simulation plot review, and simulator analysis controls.
- [x] Add closed-loop optimization that adjusts geometry after simulation
  misses target gain/bandwidth/noise metrics.
- [x] Split focused skills for simulation, circuit design, circuit layout
  design, and signoff review.
- [x] Add Python-rendered simulation plot PNG artifacts.
- [x] Add ngspice, PySpice, and Magic VLSI discovery metadata.
- [x] Add ngspice starter-deck generation, execution, parsing, and plot handoff.
- [x] Add Magic VLSI GDS import/extraction/SPICE-export handoff.
- [x] Validate MSYS2 ngspice execution on Windows and parse generated data rows.
- [x] Add a local WSL/Ubuntu Magic VLSI wrapper under `.tools` and report
  process-tech warnings when the generic tech cannot map superconducting layers.
- [x] Add `physical_performance` simulation output for LJPA gain, bandwidth,
  loaded Q, saturation/P1dB, noise temperature, pump current, and I/O ports.
- [x] Add explicit `dc_squid_pair` PCell and Aharonov-Bohm flux-periodic SQUID
  modulation for LJPA `Ic(Phi)`, `Lj(Phi)`, and `f0(Phi)`.
- [x] Add scientific simulation and sweep plot exports with PNG, SVG, CSV, and
  JSON metadata.
- [x] Add CAD-style GDS inspection exports: layout SVG, DXF, stack STL,
  optional GLB, and `.cad.json`.
- [x] Add local parameter sweep tool for layout-derived circuit metrics.
- [x] Add academic/industrial validation roadmap checklist JSON output.

## Phase 6: Research-Grade Open-Source Integrations

- [x] Add upstream integration registry for gdsfactory, JosephsonCircuits.jl,
  scikit-rf, openEMS, Optuna, Quantum Metal/Qiskit Metal, scqubits, and QCoDeS.
- [x] Add RF/Touchstone export from simulation results with `.s2p`, `.rf.png`,
  `.rf.csv`, and `.rf.json` outputs.
- [x] Add openEMS CPW/resonator EM handoff script/report generation.
- [x] Add QCoDeS-style VNA, pump, flux-bias, and fridge measurement-plan export.
- [x] Add scqubits Hamiltonian starter export from layout-derived `EJ`/`EC`.
- [x] Add Quantum Metal/Qiskit Metal component-renderer bridge metadata export.
- [x] Add Optuna-backed research optimization with deterministic grid fallback.
- [x] Add CLI/helper commands, tests, and docs for the research handoff layer.
- [x] Add a reusable vectorized JTWPA transfer-matrix engine and reproduce the
  arXiv:2209.11052v2 stop-band, coherence-length, and 3-9 GHz gain results.

## Phase 7: Closed-Loop Fabrication And Measurement

- [x] Add measured-process JSON records, process-aware JJ area correction, and
  expected critical-current yield.
- [x] Add analytical Kerr-JPA, 3WM, 4WM, and quantum-noise verification models.
- [x] Add deterministic process/lithography/capacitance Monte Carlo yield reports.
- [x] Add pyEPR-compatible HFSS field-energy, participation, loss, and T1 artifacts.
- [x] Add HFSS/PyAEDT and SonnetLab GDS handoff scripts.
- [x] Add process-mapped PyAEDT HFSS driven/eigenmode, Q3D matrix, field export,
  solver benchmark, and geometry-feedback workflows.
- [x] Add six executable QCoDeS-oriented JPA measurement recipe templates.
- [x] Add cryogenic attenuation/noise/dynamic-range analysis.
- [x] Add SQLite experiment feedback and next-design correction factors.
- [x] Add provenance-aware paper benchmark registry with pass/fail/skip status.

## Future Signoff Work

- Add CI/release-host jobs that run `scripts/install_toolchain.ps1` or cached
  equivalent installers.
- Extend the JosephsonCircuits.jl two-port LJPA starter with extracted CPW
  parasitics, calibrated pump, finite-loop-inductance SQUID, and noise models for signoff-grade
  harmonic-balance analysis.
- Replace the local surrogate optimizer with external gain/bandwidth/noise
  metrics from JosephsonCircuits.jl, JoSIM, or EM extraction.
- Implement PySpice orchestration on top of ngspice shared-library workflows.
- Promote ngspice starter decks to extracted-device decks when Magic/KLayout
  extraction can provide calibrated parasitics.
- Add calibrated Magic VLSI tech-file support and process-specific extraction
  validation for supported process stacks.
- Wire `run_research_optimization` to executed JosephsonCircuits.jl/openEMS
  objectives instead of the local surrogate when those tools are installed.
- Replace magnitude-only RF exports with complex S-parameters when adapters
  return phase or complex network data.
- Execute openEMS project scripts in CI once an installable openEMS package is
  available for the target runner.
- Add STEP export only if a real packaging/mechanical co-design workflow needs
  a STEP source model; keep GDS as the IC-layout source of truth.
