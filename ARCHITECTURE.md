# Architecture — Text-to-GDS Physics Compiler

> **Scope note (2026-07-02):** this document describes the **frozen legacy**
> `src/text_to_gds` MCP package. The supported product path is `src/textlayout`
> — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), including the
> "How to add a new generator" walkthrough.

**Version:** 2.0  
**Updated:** 2026-06-24

---

## 1. Pipeline Overview

```
[User prompt / design intent]
         │
         ▼
┌─────────────────────────────┐
│  SOP-0  Intake              │  design_intent.json
│  synthesize_design_intent() │  raises on incoherent targets
└────────────┬────────────────┘
             │ physics feasibility gate
             ▼
┌─────────────────────────────┐
│  SOP-3  Layout Backend      │  KQCircuits > Qiskit Metal
│  LayoutBackend.generate()   │  > gdsfactory > local_pcells
└────────────┬────────────────┘
             │ GDS + sidecar.json
             ▼
┌─────────────────────────────┐
│  SOP-3  DRC                 │  KLayout (or Python fallback)
│  run_drc() / run_process_drc│  .drc.json
└────────────┬────────────────┘
             │ DRC passed
             ▼
┌─────────────────────────────┐
│  SOP-2  Extraction          │  extraction.json
│  extract_layout()           │  every value: method + source
│  extract_physics_graph()    │  physics_graph.json  ← source of truth
└────────────┬────────────────┘
             │ physics_graph.json
             ▼
┌─────────────────────────────┐
│  SOP-4  Solver Input Gen    │  XML / Julia / netlist / YAML
│  generate_solver_inputs()   │  status = input_files_prepared
└────────────┬────────────────┘
             │ solver input files
             ▼
┌─────────────────────────────┐
│  SOP-4  Real Solver Exec    │  JosephsonCircuits.jl / openEMS /
│  Backend.simulate() / run() │  scqubits / JoSIM / Palace / Elmer
│  adapter_status = executed  │  output file must exist
│    or skipped / failed      │
└────────────┬────────────────┘
             │ ≥2 independent results
             ▼
┌─────────────────────────────┐
│  SOP-5  Solver Agreement    │  cross_validate() ≥2 sources
│  cross_validate()           │  confidence score; disagree → block
└────────────┬────────────────┘
             │ agreement passed
             ▼
┌─────────────────────────────┐
│  SOP-6  Review Committee    │  5 deterministic agents
│  review_committee()         │  score = min(all agents)
│                             │  pass threshold = 90
└────────────┬────────────────┘
             │ approved or blockers
             ▼
┌─────────────────────────────┐
│  SOP-7  Auto-Repair Loop    │  max 6 iterations
│  run_auto_repair()          │  stops on accepted / no-progress
└────────────┬────────────────┘
             │ accepted: True/False
             ▼
┌─────────────────────────────┐
│  SOP-5  Signoff Evaluation  │  Level 0-6
│  evaluate_signoff()         │  Level 5+ = physics signoff
│                             │  Level 6  = measurement-calibrated
└─────────────────────────────┘
```

---

## 2. Module Boundaries

### 2.1 Entry Point

**`src/text_to_gds/server.py`**

- 93 `@mcp.tool()` functions, all directly importable without the MCP server.
- `ARTIFACT_ROOT = ./workspace/artifacts/` (overridable via env var).
- No business logic here; delegates to subsystem modules.

### 2.2 Physics Compiler Stages

| Stage | Module | Schema output |
|---|---|---|
| Design intent | `design_intent.py` + `feasibility_gate.py` | `design_intent.json` |
| Layout backends | `layout/backends.py` | `GDS` + `.sidecar.json` |
| DRC | `drc.py` | `.drc.json` |
| Extraction | `extraction.py` | `.extraction.json` |
| Physics graph | `physics_graph.py` | `physics_graph.json` (v1) |
| Solver inputs | `automatic_mesh.py` | geometry.xml / netlist / YAML |
| Signoff eval | `signoff.py` | `signoff-level.v1` |
| Value records | `backends/base.py:validate_value_records` | inline validation |
| Artifact check | `artifact_validator.py` | `artifact-validation.v1` |

### 2.3 Layout Backend System

**`src/text_to_gds/layout/`**

```
layout/
  backends.py        LayoutBackend ABC + 4 concrete subclasses
  technology.py      SuperconductingTechnology dataclass + TechnologyFactory
  kqcircuits_wrapper.py  thin import guard → SKIPPED when unavailable
```

Selection priority (in `can_handle()` order):

1. **KQCircuits** — CPW feedlines, resonators, airbridges, IQM-process stack.
2. **Qiskit Metal** — Transmon, CPW routing, coupler geometry, launch pads.
3. **gdsfactory** — GDS booleans, layer remapping, routing glue.
4. **local_pcells** — Tests and demos only. `visualization_only = True` always.

An unavailable backend returns `status="UNSUPPORTED"` — never generates fake
geometry.

### 2.4 Backend System

**`src/text_to_gds/backends/`**

All backends inherit from `backends/base.py::Backend`:

```python
class Backend:
    def available() -> BackendAvailability
    def generate(...) -> dict
    def simulate(...) -> dict
    def extract(...) -> dict
```

Valid `BackendStatus` literals:

```
EXECUTED | PREPARED | SKIPPED | FAILED | UNSUPPORTED
```

`SKIPPED` when tool unavailable. Never `PASSED` or `SUCCESS` as a substitute.

**Registered backends (`backends/__init__.py`):**

| Key | Class | Role |
|---|---|---|
| `kqcircuits` | `KQCircuitsBackend` | Superconducting layout |
| `qiskit_metal` | `QiskitMetalBackend` | Qubit layout |
| `gdsfactory` | `GDSFactoryBackend` | Layout glue |
| `scqubits` | `ScQubitsBacked` | Hamiltonian spectra |
| `josephsoncircuits` | `JosephsonCircuitsBackend` | JPA harmonic balance |
| `openems` | `OpenEMSBackend` | FDTD S-parameters |
| `palace` | `PalaceBackend` | Eigenmode FEM |
| `elmer` | `ElmerBackend` | Electrostatic capacitance |
| `pyepr` | `PyEPRBackend` | Energy participation ratios |

### 2.5 Review Committee

**`src/text_to_gds/review/`**

```
review/
  __init__.py       public API
  committee.py      review_committee() — runs all 5 reviewers
  base.py           finding(), score_from_findings(), review_result()
  physics.py        review_physics()
  microwave.py      review_microwave()
  fabrication.py    review_fabrication()
  measurement.py    review_measurement()
  literature.py     review_literature()
```

**Score contract:**

```python
score = min(reviewer.score for reviewer in all_reviewers)
passed = all(reviewer.passed for reviewer in all_reviewers)
# One error in any reviewer → approved=False regardless of others
```

Pass threshold: `score >= 90` AND `approved is True`.

### 2.6 Signoff System

**`src/text_to_gds/signoff.py`**

```python
def evaluate_signoff(evidence: dict) -> dict:
    ...
    # Level 0: GDS exists
    # Level 1: DRC passed
    # Level 2: extraction complete
    # Level 3: analytical sanity + valid value records
    # Level 4: ≥1 executed solver with output file
    # Level 5: ≥2 executed solvers + agreement passed
    # Level 6: Level 5 + measurement data + fit result
```

Key guards:

- `skipped` solver → never increments level.
- `executed` without output file → blocker added.
- `source="LLM"` in any value record → blocker added.
- Level < 5 claiming `physics signoff` → blocker added.

### 2.7 Provenance Chain

**`src/text_to_gds/physics/extraction_provenance.py`**

`ExtractedQuantity` requires:

```python
@dataclass
class ExtractedQuantity:
    value: float
    unit: str
    source: str         # NOT "LLM"
    method: str         # extracted | estimated | simulated | measured
    confidence: float   # 0.0 to 1.0
    validity_range: tuple | None
    dependencies: list[str]
```

`ProvenanceChain.resolve()` raises when `"estimated"` is mixed with other
method types without a clear cross-check chain.

### 2.8 Solver Agreement

**`src/text_to_gds/solver_agreement.py`**

```python
cross_validate(sources, tolerance_pct=5.0) -> dict
```

- Requires ≥ 2 independent sources.
- Single source → `confidence = 0`.
- Confidence is monotone: 100% at perfect agreement, 50% at tolerance, 0%
  at 2× tolerance.

### 2.9 Auto-Repair

**`src/text_to_gds/auto_repair.py`**

```python
run_auto_repair(
    initial_state,
    generate_fn,   # state -> evidence dict
    repair_fn,     # (state, committee) -> new_state
    threshold=90,
    max_iterations=6,
) -> dict
```

Stops when:
1. `committee["approved"] and score >= 90` → `accepted: True`.
2. Iteration budget exhausted → `accepted: False`.
3. `repair_fn` returns unchanged state (no progress) → `accepted: False`.

### 2.10 Artifact Validator

**`src/text_to_gds/artifact_validator.py`**

Per-solver artifact requirements enforced at test and review time:

| Solver | Required artifact |
|---|---|
| JosephsonCircuits.jl | `gain_db` or `frequencies_ghz` — non-empty list of finite floats |
| scqubits | `energy_levels_ghz` + `f01_ghz` — non-empty, all finite |
| openEMS | `touchstone_path` — file exists, non-empty |
| Elmer FEM | `capacitance_matrix_pf` — finite and positive |
| JoSIM | `waveform` — list of ≥10 finite floats |
| any | `status="skipped"` → `passed=True` (honest skip is valid) |

### 2.11 Physics Modules

| Module | Key API |
|---|---|
| `cpw_physics.py` | `synthesize_cpw()` — conformal-mapping Z0, ε_eff, λ/4 length |
| `junction_physics.py` | `ambegaokar_baratoff()`, `bcs_gap_j()`, `temperature_dependent_ic()` |
| `squid_physics.py` | SQUID loop inductance, flux sensitivity |
| `process_database.py` | `FabricationProcess` dataclass; validates Jc, raises on non-physical |
| `physics/cpw_model.py` | Analytical CPW Touchstone; `method="analytical"`, `confidence=0.65` |
| `physics/extraction_provenance.py` | `ExtractedQuantity`, `ProvenanceChain` |

### 2.12 Sidecar JSON Schema

Every GDS compiled through `compile_layout()` produces a `.sidecar.json`:

```json
{
  "schema": "text-to-gds.sidecar.v0",
  "pcell": "lumped_element_jpa_seed",
  "parameters": { ... },
  "ports": [ ... ],
  "layers": [ ... ],
  "junctions": [ ... ],
  "device_info": { ... }
}
```

All downstream tools (`extract_layout`, `run_simulation`, `export_*`) take
`sidecar_path` as primary input — not the GDS path.

---

## 3. Key Invariants

These invariants are enforced by code and tests. Breaking any one causes
immediate signoff failure.

1. `source = "LLM"` in any provenance record → review failure.
2. `status = "skipped"` when solver unavailable — never `"passed"`.
3. Review committee score = **minimum** (not average) across all reviewers.
4. Local PCells must not set `visualization_only = False` for production.
5. `synthesize_design_intent()` must gate every production layout generation.
6. Module names must not shadow PyPI distribution names (e.g., no `packaging.py`).
7. Every executed solver must produce a verifiable output file.
8. `physics_graph.json` is the source of truth for solver stages — not GDS.
9. `*_layout.png` and `*_benchmark.png` are always separate output files.
10. Level 5+ is required for any claim of "physics signoff".

---

## 4. Data Flow Diagram

```
prompt
  │
  ├─► design_intent.json  ──► feasibility_gate
  │
  ├─► GDS + sidecar.json  ──► DRC (.drc.json)
  │
  ├─► extraction.json     ──► physics_graph.json  ←── SOURCE OF TRUTH
  │                                │
  │                    ┌───────────┴────────────┐
  │                    │                        │
  │               EM solver              circuit solver
  │             (openEMS/Palace/Elmer)  (JC.jl/scqubits/JoSIM)
  │                    │                        │
  │                    └───────────┬────────────┘
  │                         solver_agreement
  │                                │
  │                         review_committee
  │                           (5 agents)
  │                                │
  │                         auto_repair_loop
  │                           (≤6 iters)
  │                                │
  └─────────────────────── evaluate_signoff → Level 0-6
```

---

## 5. External Tool Discovery

**`src/text_to_gds/tool_discovery.py`**

`ToolPaths.discover()` checks in order:

1. `.tools/julia-*/bin/julia`
2. `.tools/josim-*/bin/josim-cli`
3. `.tools/openEMS-*/openEMS/openEMS`
4. `shutil.which(name)` as fallback

Tests inject fake executables via `adapter_executable=str(fake_script)`.

---

## 6. Skill Installation

```bash
npx skills install JungluChen/Text-to-Layout
```

Six skills are bundled under `skills/`:

| Skill directory | Name | Role |
|---|---|---|
| `skills/text-to-gds/` | `text-to-gds` | Core layout, DRC, extraction |
| `skills/text-to-gds-simulation/` | `text-to-gds-simulation` | Solver handoffs |
| `skills/text-to-gds-circuit-design/` | `text-to-gds-circuit-design` | Pre-layout planning |
| `skills/text-to-gds-layout-design/` | `text-to-gds-layout-design` | GDS + review |
| `skills/text-to-gds-signoff/` | `text-to-gds-signoff` | Artifact audit |
| `skills/text-to-gds-physics-signoff/` | `text-to-gds-physics-signoff` | Level 5+ signoff |
