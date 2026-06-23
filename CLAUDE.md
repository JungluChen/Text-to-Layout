# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

```powershell
# Install (Python 3.11+, Windows launcher)
py -3 -m uv sync                        # core
py -3 -m uv sync --extra research       # all optional backends

# Tests
uv run pytest                                          # full suite (~fast)
uv run pytest tests/test_smoke.py                      # single file
uv run pytest tests/test_smoke.py::test_mock_tool_chain_writes_sidecars  # single test
TEXT_TO_GDS_RUN_EXTERNAL=1 uv run pytest tests/test_research_execution.py  # slow external solvers

# Lint
uv run ruff check .

# MCP server (stdio, for Claude Desktop)
uv run text-to-gds

# Regenerate all documentation assets
uv run --no-sync python scripts/generate_assets.py all
# Subsets: layouts | sims | benchmarks
```

`TEXT_TO_GDS_WORKSPACE` overrides the artifact root (default: `./workspace`). Tests use `monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)` to redirect artifacts.

---

## Architecture

### Entry point: `server.py`

`src/text_to_gds/server.py` is both the MCP server and the public API. All 80+ `@mcp.tool()` functions here are also importable directly — tests call `from text_to_gds.server import compile_layout, run_simulation, ...` without spinning up the server. `ARTIFACT_ROOT` (under `workspace/artifacts/`) is where all output files land.

### The physics-compiler pipeline

Every design request flows through these stages in order. Skipping a stage is a hard failure, not a warning.

```
synthesize_design_intent()    → feasibility gate; raises if targets are incoherent
LayoutBackend.generate()      → GDSII + sidecar.json (semantic manifest)
run_drc()                     → KLayout bbox/process DRC
extract_layout()              → extraction.json with lineage on every value
run_simulation() / Backend.simulate()  → real solver or status="skipped"
cross_validate()              → agreement engine across ≥2 sources
review_committee()            → 5-agent verdict, score = min across agents
run_auto_repair()             → bounded generate→review→repair loop (max 6 iterations)
```

### Backend system (`src/text_to_gds/backends/`)

`backends/__init__.py` registers nine backend classes. Every backend inherits from `backends/base.py::Backend` and must implement `available() → BackendAvailability`, plus operation methods (`generate`, `simulate`, `extract`, etc.). When unavailable, operations return `_status("SKIPPED", ...)` — never fake data. Valid `BackendStatus` literals: `EXECUTED | PREPARED | SKIPPED | FAILED | UNSUPPORTED`.

#### Layout backends — priority order

| Priority | Backend | Reach for it when… |
|---|---|---|
| 1 | **KQCircuits** (`kqcircuits_backend.py`) | CPW feedlines, quarter-wave resonators, airbridges, junction-compatible superconducting layouts, KLayout process stack support. Primary for anything IQM-process-compatible. |
| 2 | **Qiskit Metal** (`qiskit_metal_backend.py`) | Transmon qubits, CPW routing between components, coupler geometry, launch pads / readout resonators. Better component model than KQCircuits for qubit-centric designs. |
| 3 | **gdsfactory** (`gdsfactory_backend.py`) | GDS boolean operations, layer remapping, polygon export/import, routing glue between KQCircuits and Qiskit Metal outputs. Use only as glue — not for device geometry. |
| 4 | **local_pcells** | Tests and demos only. Visualization placeholder. Never for production or EM solver input. |

#### Simulation / EM backends — pick by physics question

| Backend | Module | Reach for it when… |
|---|---|---|
| **JosephsonCircuits.jl** | `josephsoncircuits_backend.py` | JPA / JTWPA gain, pump power sweep, harmonic balance, nonlinear circuit simulation. The only correct source for JPA gain curves. |
| **scqubits** | `scqubits_backend.py` | Transmon / fluxonium / tunable qubit energy spectrum, anharmonicity, Hamiltonian plots. Required for any qubit spectrum claim. |
| **openEMS** | `openems_backend.py` | RF S-parameters, CPW characteristic impedance Z0, Touchstone `.s2p` output from FDTD. First-choice EM solver for driven-modal problems. |
| **Palace** | `palace_backend.py` | Eigenmode resonator frequency f0, Q factor, cavity modes via 3D FEM. Prefer over openEMS when the question is "what is the resonant frequency and loss?" |
| **Elmer FEM** | `elmer_backend.py` | Electrostatic capacitance extraction, charge distribution. Use for IDC / coupling capacitor values when FastCap is unavailable. |
| **pyEPR** | `pyepr_backend.py` | Energy participation ratios from EM fields, Hamiltonian reduction from HFSS/Palace results. Post-processing step after an eigenmode solve. |

### Local PCells (`src/text_to_gds/pcells/`)

These are **visualization-only fallbacks**. Every cell sets `c.info["visualization_only"] = True`. They are registered in `PCELL_REGISTRY` in `server.py` and are the lowest-priority option — never use them for production tapeout or as EM solver inputs without manual review. Production flow must try KQCircuits → Qiskit Metal → gdsfactory first.

### Layout backend abstraction (`src/text_to_gds/layout/`)

- `layout/backends.py` — `LayoutBackend` ABC; `can_handle(components)` selects by device list. The four concrete implementations match the priority table above.
- `layout/technology.py` — `SuperconductingTechnology` dataclass + `TechnologyFactory`; `KQCircuitsSelector` and `GDSFactorySelector` implement the `PCellSelector` protocol for naming and instantiating cells.
- `layout/kqcircuits_wrapper.py` — thin wrapper that guards `import kqcircuits` and returns `SKIPPED` if unavailable.

### Provenance and lineage (`src/text_to_gds/extraction.py`)

The `quantity()` function is the only correct way to record a derived value. It requires:

- `method_label`: `"estimated"` | `"extracted"` | `"simulated"` | `"measured"`
- `source`: name of the tool/formula — `source = "LLM"` is invalid and causes review failure
- `formula`, `confidence`, `unit`

`backends/base.py::value_record()` and `validate_value_records()` enforce the same contract for backend outputs.

`physics/extraction_provenance.py` provides `ExtractedQuantity` (dataclass with `value`, `unit`, `source`, `method`, `confidence`, `validity_range`, `dependencies`) and `ProvenanceChain` for walking dependency graphs. `ProvenanceChain.resolve()` raises if `"estimated"` is mixed with other sources.

### Solver Agreement Engine (`src/text_to_gds/solver_agreement.py`)

`cross_validate(sources, tolerance_pct=5.0)` requires ≥2 independent sources. A single solver result has `confidence = 0`. The confidence model is monotone: 100% at perfect agreement, 50% at the tolerance boundary, 0% at 2× the tolerance.

### Review Committee (`src/text_to_gds/review/committee.py`)

Five deterministic reviewers (no LLM): `physics`, `microwave`, `fabrication`, `measurement`, `literature`. Each lives in its own module under `review/`. `review_committee(evidence)` returns `score = min(reviewer scores)`. Pass threshold is ≥ 90. One error in any reviewer prevents pass — averaging is explicitly not done.

`review/base.py` provides shared helpers: `finding()`, `score_from_findings()`, `review_result()`. Severity penalties: `error = -40`, `warning = -10`, `info = 0`.

### Auto-repair loop (`src/text_to_gds/auto_repair.py`)

`run_auto_repair(initial_state, generate_fn, repair_fn, *, threshold=90, max_iterations=6)` is solver-agnostic. It stops when `committee["approved"]` and `score >= threshold`, when the iteration budget is exhausted, or when `repair_fn` returns an unchanged state. Acceptance requires both `approved` and score; the committee can never report ≥ 90 while any reviewer has an error. Returns schema `text-to-gds.auto-repair.v1`.

### SolverAdapter base (`src/text_to_gds/simulation/solver_adapter.py`)

`SolverAdapter` is the ABC for circuit/EM adapters (JoSIM, ngspice, JosephsonCircuits.jl, openEMS). `SolverResult` is a frozen dataclass with `status ∈ {EXECUTED, SKIPPED, FAILED}`. The `.to_dict()` method normalises `"SUCCESS"` → `"EXECUTED"` and rejects anything not in the valid set.

Concrete adapters: `simulation/openems_adapter.py`, `simulation/josephsoncircuits_adapter.py`. These differ from the `backends/` classes — adapters handle the raw subprocess/input-generation/parsing cycle; backends add availability checking and sidecar integration.

### AI copilot (`src/text_to_gds/ai/`)

- `ai/design_intent.py` — `DesignIntent` dataclass + `DesignIntentParser`. Parses a free-text prompt into `device`, `parameters`, `technology`, `process` without calling an LLM.
- `ai/copilot.py` — `AICopilot` orchestrator. Registers `SolverAdapter` instances via `register_solver()` and runs `execute(prompt)` → `CopilotResult`. Technology backends are selected via `TechnologyFactory`.

The standalone `design_intent.py` in the package root (`src/text_to_gds/design_intent.py`) contains `synthesize_design_intent()` — the full pre-layout solver that calls `synthesize_cpw()` and derives `Lj`, `Ic`, `f0`. This is distinct from the parser in `ai/`.

### Physics modules

| Module | Key API |
|---|---|
| `cpw_physics.py` | `synthesize_cpw(center_width_um, gap_um, ...)` — conformal-mapping Z0, epsilon_eff, lambda/4 length. Validates geometry; raises on non-physical inputs. |
| `junction_physics.py` | `bcs_gap_j()`, `ambegaokar_baratoff()`, `temperature_dependent_ic()`, `junction_aging()`. Constants: `FLUX_QUANTUM`, `BOLTZMANN`. |
| `squid_physics.py` | SQUID loop inductance, flux sensitivity, flux-tunable Lj. |
| `process_database.py` | `FabricationProcess` (frozen dataclass); loads process records from JSON. Validates required fields; raises on non-physical Jc. |
| `physics/cpw_model.py` | Analytical CPW S-parameter model (conformal mapping). Label `method="analytical"`, `confidence=0.65`. Cross-check only — not a simulation result. |
| `physics/extraction_provenance.py` | `ExtractedQuantity`, `ProvenanceChain` — dependency-graph provenance. |

### Theory subpackage (`src/text_to_gds/theory/`)

Analytical JPA/TWPA verification models (no solver required):

- `theory/kerr_jpa.py` — `kerr_jpa_gain()`, `gain_bandwidth_product()`
- `theory/three_wave_mixing.py` — `three_wave_mixing_gain()`
- `theory/four_wave_mixing.py` — `four_wave_mixing_gain()`
- `theory/quantum_noise.py` — `quantum_limited_noise_temperature()`

These are cross-checks against JosephsonCircuits.jl results. They must never replace a solver run.

### Sidecar JSON schema

`compile_layout()` writes `<stem>.sidecar.json` alongside every GDS. Downstream tools (`extract_layout`, `run_simulation`, `export_hamiltonian_model`, etc.) all take `sidecar_path` as their primary input — not the GDS path. Sidecar schema version is `"text-to-gds.sidecar.v0"`.

### External tool discovery (`src/text_to_gds/tool_discovery.py`)

`ToolPaths` dataclass + `discover()` function. Checks `.tools/` (git-ignored) for `julia-*/`, `josim-*/`, `openEMS-*/`, then falls back to `shutil.which`. Call `tool_paths()` from any adapter instead of hard-coding a binary name. Tests inject fake executables via `adapter_executable=str(fake_script)`.

---

## Key invariants — never break these

- `source = "LLM"` in any provenance record → immediate review failure
- `status = "skipped"` when a solver is unavailable — never `"passed"` or `"success"`
- Review committee score = **minimum** (not average) across all reviewers
- Local PCells must not claim `visualization_only = False` for production devices
- `synthesize_design_intent()` must gate every layout generation — never call `compile_layout()` without it in the production path
- Module names in `src/text_to_gds/` must not shadow PyPI distribution names (e.g. do not create `packaging.py`, `importlib.py`) — the MCP stdio subprocess imports the project package and will shadow the stdlib/PyPI module

---

## External solver gating

Slow tests that require real external binaries are skipped by default. Set `TEXT_TO_GDS_RUN_EXTERNAL=1` to enable them. Individual tests use `pytest.mark.skipif(find_spec("scqubits") is None, ...)` patterns for optional Python packages. The `test_research_execution.py` file documents which libraries are always-on vs gated.

## Asset regeneration

`scripts/generate_assets.py` drives the full physics-compiler pipeline to produce every PNG in `assets/`. Run it with `--no-sync` when the venv is locked by the running MCP server process: `uv run --no-sync python scripts/generate_assets.py all`. The script distinguishes `executed` vs `skipped` solvers explicitly — it never invents solver output.

---

## Solver execution status (as of 2026-06-23)

See [`PHYSICS_VALIDATION_REPORT.md`](PHYSICS_VALIDATION_REPORT.md) for the full benchmark table.

### What executes today

| Solver | Status | Artifact |
|---|---|---|
| JosephsonCircuits.jl | **EXECUTED** | gain array, pump sweep (Julia 1.12.6, JC.jl 0.5.2) |
| scqubits | **EXECUTED** | energy levels, f01, anharmonicity (scqubits 4.3.1) |
| CPW analytical model | **EXECUTED** | Touchstone .s2p (method=analytical, confidence=0.65) |
| Via chain resistance | **EXECUTED** | resistance_ohm from sidecar geometry |
| JJ array characterization | **EXECUTED** | Ic/Lj table per junction + JC.jl sweep |

### What is SKIPPED (honest, not a failure)

| Solver | Root cause | Fix |
|---|---|---|
| openEMS FDTD | Binary at `.tools/openEMS-v0.0.36/`; S-parameters require octave post-processor. Python wheels in `python/` are cp311, project uses Python 3.12. | Install Octave or switch to Python 3.11 venv |
| Elmer FEM | ElmerSolver not on PATH | https://www.elmerfem.org/blog/binaries/ |
| Palace | Executable not found | Build from source: https://github.com/awslabs/palace |
| JoSIM | Binary found but SFQ netlist generation not wired to benchmark | Connect josim adapter to SFQ PCell sidecar |
| Qiskit Metal | PySide2/Qt5 incompatible with Windows Python 3.12 | conda + Python 3.10 |

### openEMS critical path

`openems_runner.py::_find_octave()` checks PATH and common Windows install paths. If no octave → `status="skipped"` with explicit reason including install URL. The octave post-processing script is `matlab/calcPort.m` (bundled in openEMS package). The bundled Python wheels (`openEMS-0.0.36-cp311-cp311-win_amd64.whl`) are an alternative — install into a Python 3.11 venv.

### CPW analytical model (not a simulation substitute)

`src/text_to_gds/physics/cpw_model.py` implements conformal-mapping Z0 and a coupled quarter-wave resonator S-parameter model. It writes a valid Touchstone `.s2p` but MUST be labelled `method="analytical"`, `confidence=0.65`. It is a **cross-check only** — not a simulation result. `cross_validate_with_openems()` compares analytical vs FDTD with 10% tolerance.

---

## Key standalone extraction modules

| Module | Purpose |
|---|---|
| `jj_array_characterization.py` | Batch Ic/Lj extraction + JC.jl sweep for calibration arrays. Schema: `text-to-gds.jj-array-characterization.v1` |
| `resistance_extractor.py` | Via chain R = N×Rvia + Rs×L/W from sidecar. Schema: `text-to-gds.resistance-extraction.v1` |
| `openems_runner.py` | Reads `extraction.json`, generates CSXCAD XML, runs openEMS subprocess, validates resulting `.s2p`. Schema: `text-to-gds.openems-runner.v1` |
| `tool_discovery.py` | Zero-config binary discovery from `.tools/` (julia, josim, openEMS, klayout, palace, elmer) |

### Artifact validation contract

Per-solver artifact requirements (enforced in tests and review committee):
- JosephsonCircuits.jl → `gain_db` or `frequencies_ghz` must be a non-empty list of finite floats
- scqubits → `execution.energy_levels_ghz` + `execution.f01_ghz` must be finite
- openEMS → `touchstone_path` must point to an existing non-empty file
- Elmer → `capacitance_matrix_pf` must be finite and positive
- JoSIM → `waveform` must be a list of ≥10 finite floats
- `status="skipped"` → `passed=True` (honest skip is valid)

### Solver evidence panel standard

Every benchmark 3-panel figure requires (Panel 3):
```
SOLVER EXECUTED
Engine:   openEMS 0.0.36
Input:    model.xml
Output:   cpw.s2p (47312 bytes)
Runtime:  15.2s
Timestamp: 2026-06-23T15:07:35
```
Green = EXECUTED with artifact path. Grey = SKIPPED with reason. Red = FAILED (investigate before signoff).
