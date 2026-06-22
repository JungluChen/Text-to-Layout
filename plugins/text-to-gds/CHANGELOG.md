# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/). Release entries are backed by merged
pull requests and verified benchmark evidence.

## [Unreleased]

## [0.2.0] - 2026-06-22

First tracked release. Consolidates the work previously described informally as
the first through fifth "waves" into a versioned baseline.

### Added
- Reviewed superconducting PCell library (Manhattan JJ, dc-SQUID, CPW resonator,
  meander inductor, flux-bias line, via chain, ground plane, calibration array).
- Local MCP server exposing 72 tools for layout, DRC, extraction, EM/circuit
  simulation handoff, planning, and reporting.
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
