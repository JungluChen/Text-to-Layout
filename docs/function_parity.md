# Function Parity With text-to-cad

Text-to-GDS follows the same open-source shape as `earthtojake/text-to-cad`,
but replaces mechanical CAD operations with local EDA layout operations.

| text-to-cad pattern | Text-to-GDS implementation |
| --- | --- |
| Installable skill library | `skills/text-to-gds` plus focused simulation, circuit-design, layout-design, and signoff skills. Install with `npx skills install JungluChen/Text-to-Layout` |
| Provider plugin bundle | `plugins/text-to-gds` with Codex and Claude metadata |
| Local deterministic toolchain | `py -3 -m uv run ...` commands and MCP server |
| Source-controlled generators | gdsfactory PCells under `src/text_to_gds/pcells` |
| Primary generated artifact | `.gds` instead of `.step` |
| Visual review artifact | `.layout.png` screenshot generated from the GDS |
| CAD/interchange exports | `export_cad_artifacts` writes `.layout.svg`, `.layout.dxf`, `.stack.stl`, optional `.stack.glb`, and `.cad.json` from GDS layer boxes |
| Inspection sidecar | `.sidecar.json` with ports, bbox, layers, and PCell metadata |
| 3D/stack review aid | `.stack3d.html` and `.stack3d.json` interactive local 3D process-stack preview |
| Validation loop | KLayout Python min-width scan and `.drc.json` reports |
| Process DRC handoff | external `klayout -b` adapter with `.lyrdb`/JSON parser plus KLayout Python process-rule fallback |
| Simulation handoff | ideal JJ `.simulation.json`, `.simulation.png` plots, scientific PNG/SVG/CSV exports, RF `.s2p`/`.rf.png` exports, parameter sweeps, extraction summaries, real JoSIM transient execution, ngspice starter-deck execution, Magic extraction handoff, JosephsonCircuits.jl single-port JJ reflection, and two-port LJPA S-parameter starter execution |
| Research adapter execution | `list_research_integrations` plus real, execute-when-installed adapters: openEMS FDTD EM extraction (S11/S21, effective permittivity, Z0, E-field VTK), QCoDeS mock-VNA sweep into a real SQLite dataset, scqubits Hamiltonian diagonalization (levels, anharmonicity, flux/charge spectrum), Qiskit Metal `QDesign`+GDS render, Optuna TPE optimization, and a JosephsonCircuits.jl pump sweep yielding gain/P1dB/noise-temperature/squeezing/stability |
| Traveling-wave paper benchmark | `photonic_crystal_stwpa` and `periodically_loaded_kit_unit_cell` PCells plus `run_traveling_wave_paper_benchmark`; the linear Planat/Erickson band calculations are independent, while gain magnitude is explicitly a paper-calibrated reduced coupled-mode result |
| Closed-loop research | Process-run records, analytical JPA/TWPA theory, uncertainty/yield reports, executable PyAEDT HFSS/Q3D and openEMS/Sonnet/pyEPR handoffs, cryogenic-chain budgets, measurement recipes, experiment SQLite storage, and EM/measurement-driven corrections |
| Scientific report generator | `export_scientific_report` assembles the ten-figure composite (Layout, S11/S21, Gain, Bandwidth, Flux tuning, Pump sweep, P1dB, Noise temperature, Squeezing, Stability) with each panel labelled `josephsoncircuits_real` or `layout_surrogate` |
| Research validation checklist | `.validation.json` follows the academic/industrial roadmap across layout, DRC, extraction, simulation, CAD, and publication-readiness evidence |
| Prompt planning | `plan_ljpa` turns short LJPA prompts into clarification questions, assumptions, registered PCells, and simulator choices |
| Prompt-to-artifact run | `run_design_workflow` compiles an LJPA seed GDS and writes a local browser workbench |
| Live workbench | Apple-style standard-library HTTP server at `text_to_gds.ui` accepts prompt edits, simulator controls, 3D stack review, simulation plot review, and local workflow execution |
| Iteration loop | `run_optimized_design_workflow` adjusts geometry with a deterministic surrogate and records optimization history |
| Example outputs | `examples/example_output.md` |
| Benchmark prompts | six prompt/layout screenshot benchmark rows under `benchmarks/` and `assets/` |
| CI and local checks | `.github/workflows/test.yml`, pytest, ruff, compileall, MCP stdio protocol smoke test |

## Intentional Differences

- Text-to-GDS does not use STEP as the primary source of truth. GDS remains the
  primary artifact; SVG/DXF/STL/GLB are derived inspection/interchange exports.
- Text-to-GDS does not implement 3MF, G-code, URDF, SRDF, or SDF workflows
  because those are mechanical manufacturing and robotics outputs.
- Text-to-GDS does not claim foundry signoff until a real process DRC deck is
  provided.
- Text-to-GDS uses GDS, sidecars, DRC reports, and superconducting simulation
  reports as the domain-specific equivalents of text-to-cad artifacts.
- Text-to-GDS now has the same high-level agent loop shape as text-to-cad:
  prompt, generated source artifact, visual review artifact, sidecar/metadata,
  validation report, examples, benchmarks, skill, plugin bundle, and local
  tests. Its remaining gaps are domain-specific signoff depth: foundry-qualified
  DRC decks, calibrated Magic tech/process extraction, EM extraction, richer
  extracted CPW/parasitic/noise-aware JosephsonCircuits netlist generation, and
  signoff-grade optimization backed by measured external simulator metrics.

The traveling-wave benchmark does not yet claim full nonlinear parity with the
papers. Missing pieces are Planat's self-consistent nonlinear pump/reflection/noise
calculation and Erickson-Pappas's `Nc=251`, `Nb=6` multi-band nonlinear Runge-Kutta
system. The benchmark JSON lists these exclusions under `parity_scope`.
