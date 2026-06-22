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

- [x] Add CI/release-host jobs that run `scripts/install_toolchain.ps1` or cached
  equivalent installers.
- [x] Extend the JosephsonCircuits.jl two-port LJPA starter with extracted CPW
  parasitics, calibrated pump, finite-loop-inductance SQUID, and noise models for signoff-grade
  harmonic-balance analysis.
- [x] Replace the local surrogate optimizer with external gain/bandwidth/noise
  metrics from JosephsonCircuits.jl, JoSIM, or EM extraction.
- [x] Implement PySpice orchestration on top of ngspice shared-library workflows.
- [x] Promote ngspice starter decks to extracted-device decks when Magic/KLayout
  extraction can provide calibrated parasitics.
- [x] Add calibrated Magic VLSI tech-file support and process-specific extraction
  validation for supported process stacks.
- [x] Wire `run_research_optimization` to executed JosephsonCircuits.jl/openEMS
  objectives instead of the local surrogate when those tools are installed.
- [x] Replace magnitude-only RF exports with complex S-parameters when adapters
  return phase or complex network data.
- [x] Execute openEMS project scripts in CI once an installable openEMS package is
  available for the target runner.
- [x] Add STEP export only if a real packaging/mechanical co-design workflow needs
  a STEP source model; keep GDS as the IC-layout source of truth.

---

## Phase 8: Fifth-Wave — Open Quantum Hardware Research Infrastructure

Goal: Move from AI Superconducting EDA Platform to Open Quantum Hardware Research Infrastructure.

### 8.1 Repository / Engineering Quality

- [x] Add GitHub Actions CI pipeline.
- [x] Add nightly regression benchmark.
- [x] Add automatic solver compatibility test.
- [x] Add performance benchmark dashboard.
- [x] Add documentation website using MkDocs.
- [x] Add API documentation generation.
- [x] Add executable tutorials.
- [x] Add Google Colab examples.
- [x] Add Docker images: minimal, research, full solver.
- [x] Add VS Code devcontainer.
- [x] Add release automation.
- [x] Add semantic versioning.
- [x] Add changelog generator.
- [x] Add package publishing to PyPI.
- [x] Add Zenodo DOI archive.
- [x] Add citation metadata.
- [x] Add contribution workflow.
- [x] Add issue templates.
- [x] Add benchmark submission template.
- [x] Add reproducibility checklist.

### 8.2 Scientific Verification Layer

- [x] Add physics unit-test framework.
- [x] Add equation verification tests.
- [x] Add dimensional analysis checker.
- [x] Add conservation law checker.
- [x] Add microwave causality checker.
- [x] Add passivity verification.
- [x] Add reciprocity verification.
- [x] Add S-parameter sanity checker.
- [x] Add Kramers-Kronig validation.
- [x] Add quantum limit validation.
- [x] Add uncertainty propagation engine.
- [x] Add confidence interval calculation.
- [x] Add automatic error bar generation.
- [x] Add measurement repeatability score.
- [x] Add simulation credibility score.

### 8.3 Literature Reproduction System

- [x] Add paper-to-benchmark pipeline.
- [x] Add DOI importer.
- [x] Add arXiv importer.
- [x] Add automatic parameter extraction.
- [x] Add figure digitization.
- [x] Add plot-to-data extraction.
- [x] Add equation extraction.
- [x] Add device reconstruction.
- [x] Add paper reproduction report.
- [x] Add reproduction leaderboard.

### 8.4 Quantum Device Dataset

- [x] Add open device dataset format.
- [x] Add device metadata standard.
- [x] Add GDS hash tracking.
- [x] Add process hash tracking.
- [x] Add measurement hash tracking.
- [x] Add dataset version control.
- [x] Add HuggingFace dataset export.
- [x] Add device similarity search.
- [x] Add failed-device database.
- [x] Add negative training examples.

### 8.5 Layout Foundation Model

- [x] Add GDS tokenizer.
- [x] Add polygon encoder.
- [x] Add layer embedding.
- [x] Add port embedding.
- [x] Add netlist graph encoder.
- [x] Add circuit graph neural network.
- [x] Add layout transformer.
- [x] Add masked layout pretraining.
- [x] Add geometry embedding search.
- [x] Add layout generation model.

### 8.6 AI Physics Model

- [x] Add physics foundation model.
- [x] Add microwave surrogate model.
- [x] Add neural S-parameter predictor.
- [x] Add neural capacitance extractor.
- [x] Add neural inductance extractor.
- [x] Add neural gain predictor.
- [x] Add neural noise predictor.
- [x] Add neural yield predictor.
- [x] Add uncertainty-aware prediction.
- [x] Add active learning loop.

### 8.7 Differentiable EDA

- [x] Add differentiable geometry engine.
- [x] Add PyTorch GDS parameters.
- [x] Add differentiable PCell.
- [x] Add differentiable circuit solver.
- [x] Add differentiable microwave model.
- [x] Add differentiable JPA gain model.
- [x] Add automatic gradient optimization.
- [x] Add adjoint EM workflow.
- [x] Add topology optimization.
- [x] Add gradient-based inverse design.

### 8.8 Advanced Device Discovery

- [x] Add topology search.
- [x] Add circuit evolution.
- [x] Add genetic superconducting circuit design.
- [x] Add symbolic circuit discovery.
- [x] Add automatic Hamiltonian discovery.
- [x] Add automatic Lagrangian derivation.
- [x] Add new amplifier topology generator.
- [x] Add new qubit topology generator.
- [x] Add novelty score.
- [x] Add patent similarity search.

### 8.9 Fabrication Digital Twin 2.0

- [x] Add cleanroom workflow tracking.
- [x] Add fabrication recipe optimizer.
- [x] Add process anomaly detector.
- [x] Add wafer map AI.
- [x] Add SEM foundation model.
- [x] Add TEM image analysis.
- [x] Add AFM roughness extraction.
- [x] Add film thickness prediction.
- [x] Add oxidation model.
- [x] Add yield learning system.

### 8.10 Measurement Intelligence 2.0

- [x] Add autonomous experiment planner.
- [x] Add experiment scheduler.
- [x] Add adaptive measurement.
- [x] Add Bayesian measurement selection.
- [x] Add automatic calibration selection.
- [x] Add VNA trace classifier.
- [x] Add failed measurement diagnosis.
- [x] Add anomaly detector.
- [x] Add cooldown memory.
- [x] Add lab notebook AI.

### 8.11 Cryogenic System Intelligence

- [x] Add fridge digital twin.
- [x] Add cooldown prediction.
- [x] Add thermal simulation.
- [x] Add heat-load optimizer.
- [x] Add cable configuration optimizer.
- [x] Add microwave-chain generator.
- [x] Add noise budget optimizer.
- [x] Add magnetic shielding optimizer.
- [x] Add vibration model.
- [x] Add reliability model.

### 8.12 Collaboration Platform

- [x] Add web-based layout editor.
- [x] Add multiplayer design.
- [x] Add cloud simulation queue.
- [x] Add design review workflow.
- [x] Add permission management.
- [x] Add lab/project workspace.
- [x] Add experiment sharing.
- [x] Add public benchmark portal.
- [x] Add device model marketplace.
- [x] Add community PDK repository.

### 8.13 Industrial Signoff

- [x] Add superconducting tapeout checklist.
- [x] Add manufacturing readiness level.
- [x] Add reliability qualification.
- [x] Add lifetime prediction.
- [x] Add automated design review.
- [x] Add compliance report.
- [x] Add process compatibility check.
- [x] Add foundry handoff package.
- [x] Add mask order generation.
- [x] Add production tracking.

### 8.14 AI Research Scientist Layer

- [x] Add research hypothesis generator.
- [x] Add automatic experiment proposal.
- [x] Add grant proposal generator.
- [x] Add research roadmap planner.
- [x] Add reviewer simulation.
- [x] Add weakness finder.
- [x] Add missing experiment detector.
- [x] Add automatic paper drafting.
- [x] Add result interpretation.
- [x] Add next-device recommendation.
