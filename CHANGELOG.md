# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/). Release entries are backed by merged
pull requests and verified benchmark evidence.

## [Unreleased]

## [0.3.0] - 2026-07-05

Bumped to match the version already claimed (but never actually released) by
`IMPLEMENTATION_REPORT.md` since 2026-06-26, plus the cQED design-loop
upgrade added in this cycle.

### Added
- `textlayout.epr`: energy-participation-ratio analysis and coherence
  estimation (`AnalyticalEPRBackend`, `PyEPRBackend` interface stub,
  `1/Q = sum(p*tan_delta)` / `T1 = Q/omega`), illustrative materials DB,
  CLI `textlayout epr` / `verify --include-epr`.
- `textlayout.yield_model`: JJ/SQUID critical-current variability, seeded
  Monte Carlo frequency-yield propagation, CLI `textlayout yield jj` /
  `yield qubit-array`.
- `textlayout.chip_lattice`: multi-qubit frequency-collision taxonomy,
  Monte Carlo collision-free chip yield, greedy retune optimizer, CLI
  `textlayout chip analyze` / `chip optimize`.
- `textlayout.pdk`: typed foundry PDK schema beyond `generic_2metal`
  (layer stack, substrate, JJ process parameters, density-rule
  placeholders), YAML loader, `pdk_to_technology()` bridge, two shipped
  illustrative PDKs, CLI `textlayout pdk list` / `pdk info`.
- `textlayout.measurement`: simulation-vs-measurement residual comparison
  and correction-factor calibration, CLI `textlayout measurement compare`
  / `measurement calibrate`.
- `examples/real_cqed_loop.py`: end-to-end demo composing all of the above.
- `scripts/generate_project_status.py` + `scripts/check_project_claims.py`:
  a single machine-readable status manifest (`out/evidence/project_status.json`
  / `PROJECT_STATUS.md`) and a consistency checker that fails CI on
  version/claim drift between README, status docs, and package metadata.

### Fixed
- `run_python_process_drc` (legacy `text_to_gds.drc`) now uses KLayout's
  exact `Region.width_check`/`space_check` instead of a bounding-box
  approximation that missed concave-polygon and overlapping-bbox violations.
- GDS export refuses to write an unknown layer as `(0,0)`; KLayout readback
  independently verifies drawn minimum width on the exported file.
- `pyproject.toml` version now matches reality (`IMPLEMENTATION_REPORT.md`
  had claimed 0.3.0 since 2026-06-26 without a corresponding release).

## [0.2.0] - 2026-06-22

First tracked release. Consolidates the work previously described informally as
the first through fifth "waves" into a versioned baseline.

### Added
- Open research platform (roadmap Phases 1-6): open-source-first solver routing
  (`open_solver_manager`), the Solver Agreement Engine (`solver_agreement`),
  `open_q3d` (Elmer/FastCap/FastHenry + IDC auto-tune), a MEEP FDTD adapter,
  device physics templates + a pre-layout feasibility gate, a rule-based AI
  review committee (physics/microwave/fabrication/measurement) with an
  auto-repair loop, layout understanding, functional open benchmarks, a gated
  research-readiness score, and the end-to-end `run_ai_scientist` orchestrator.
  Commercial EM (HFSS/Q3D/Sonnet) is demoted to optional validation-only.
- Reviewed superconducting PCell library (Manhattan JJ, dc-SQUID, CPW resonator,
  meander inductor, flux-bias line, via chain, ground plane, calibration array).
- Local MCP server exposing 80+ tools for layout, DRC, extraction, EM/circuit
  simulation handoff, planning, review, and reporting.
- Three callable improvement registries (340 numbered catalog entries mapping to
  285 distinct implementations), each with import/callable validation.
- Versioned superconducting PDK loader and bundled illustrative process files.
- Real, execute-when-installed adapters for gdsfactory, JosephsonCircuits.jl,
  scikit-rf, openEMS, Optuna, Qiskit Metal, scqubits, and QCoDeS.
- Open-source EM stack (openEMS, Palace, Elmer, FastHenry/FastCap, gmsh) and a
  licensed PyAEDT HFSS/Q3D path.
- Paper-benchmark reproductions (Planat 2020 STWPA, Gaydamachenko 2022 3WM-JTWPA).
- Fifth-wave foundations: scientific verification, quantum datasets, graph
  encoders, differentiable EDA, neural surrogates, and topology search.

### Changed
- Registry `list_*` results now report `unique_implementations` alongside the
  catalog `count`, making the distinction between numbered entries and distinct
  callables explicit.
- Reference material (PyAEDT/Q3D deep dive, open-source EM solver details, and
  the improvement-registry catalogs) moved from the README into `docs/`.

### Fixed
- CI now verifies that the bundled `plugins/text-to-gds/` copy is in sync with
  the source tree, preventing silent drift.

[Unreleased]: https://github.com/JungluChen/Text-to-Layout/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/JungluChen/Text-to-Layout/releases/tag/v0.2.0
