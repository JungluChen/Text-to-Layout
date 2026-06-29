# PROJECT_AUDIT.md — Text-to-GDS → QuantumCAD OS

**Auditor:** Multidisciplinary engineering org (Principal EDA Architect lead)
**Date:** 2026-06-29
**Branch:** `main` (working tree dirty — see §1.2)
**Method:** Every quantitative claim below was produced by running the tool/command on this
checkout, not from prior reports. Where a previous report disagrees with measured reality,
the measured value is used and the discrepancy is flagged (§12).

> This document **supersedes** the prior `PROJECT_AUDIT.md` (2026-06-24), which is now stale:
> it reported "393 passed", "Fake Claims — None Found", and "Dead Code — none". All three are
> contradicted by current measurements (§8, §10, §12). **No code is modified by this audit.**

---

## 0. How to read this

The repository's *aspiration* (README, `IMPLEMENTATION_REPORT.md`, `SOP.md`) is a world-class
AI-native quantum EDA platform. The repository's *measured state* is a large, rapidly-accreted
research codebase with a **broken test gate**, **significant dead/shadowed code**, and a
**newly-added architecture layer that is not wired into the product**. The gap between the two
is the central finding. This audit quantifies that gap so Phase 1 can start from truth.

---

## 1. Executive Summary

### 1.1 Top findings (severity-ordered)

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F1 | 🔴 **Blocker** | Test suite does **not** pass cleanly. `642 passed, 8 skipped, **1 collection error**`. A committed test imports a symbol (`extract_device`) that no longer exists. | `pytest --continue-on-collection-errors` → §10 |
| F2 | 🔴 **Blocker** | Working-tree edit to `extracted_device.py` (status `M`) removed/renamed `extract_device`, breaking `tests/test_physics_compiler_loop.py` (tracked). `grep "def extract_device"` → **0 hits anywhere**. | §10, §12 |
| F3 | 🟠 **High** | **~1,907 LOC of dead code**: 5 top-level modules are shadowed by same-named packages and are unreachable. | §8 (verified via `import … __file__`) |
| F4 | 🟠 **High** | **17+ new "engine" subpackages orphaned** — 0 references in `server.py`. The new "AI-Native platform" layer is implemented but **not integrated** into the MCP/product surface. | §3.3 |
| F5 | 🟠 **High** | Published status reports overclaim. `IMPLEMENTATION_REPORT.md` says "648 passed, 0 failed"; reality is 1 error + a missing symbol. The truth-contract the project enforces on *physics* is not enforced on its *own status docs*. | §12 |
| F6 | 🟡 **Medium** | Massive duplication: 3 overlapping review systems, ≥6 duplicate-concept module pairs, "wave"/"extensions"/"phase" accretion layers (15 modules). | §7 |
| F7 | 🟡 **Medium** | `server.py` is a 3,050-LOC god module hosting 95 `@mcp.tool` functions and importing nearly the whole package. No clean public-API boundary. | §3.1, §9 |
| F8 | 🟡 **Medium** | No type-checking gate. `mypy` is referenced as a goal (CLAUDE.md, CI vision) but is **not** a dependency and not run. Strict typing is unverified across 70k LOC. | §5, `pyproject.toml` dev group = `pytest, ruff` only |

### 1.2 Health scorecard

| Dimension | State | Note |
|---|---|---|
| Builds / imports | 🟡 | Package imports; one test module fails to import |
| Lint (ruff) | 🟢 | `All checks passed!` |
| Type check (mypy) | ⚫ Not configured | Absent from toolchain |
| Tests | 🔴 | 1 collection error; suite not green |
| Dead code | 🔴 | ~1.9k LOC shadowed + unknown unreferenced surface |
| Architecture coherence | 🟠 | Two architectures coexist (legacy flat + new "engine" packages); new one not wired |
| Doc accuracy | 🟠 | Aspirational docs overstate verified state |

### 1.3 Scale

| Metric | Value |
|---|---|
| Python files in `src/text_to_gds` | **315** |
| Source LOC (src only) | **69,856** |
| Top-level modules (`*.py`) | ~130 |
| Subpackages | **41** |
| `server.py` LOC | 3,050 |
| `@mcp.tool` functions | 95 |
| Test files / tests collected | 63 / **650** |
| Largest non-server module | `research.py` (1,225 LOC) |

---

## 2. Repository Architecture (as-built)

The repo is **not** organized as the target `src/{cad_kernel,geometry,pdk,...}` layout. It is a
mostly-flat package with ~130 sibling modules plus 41 subpackages added in layers over time.
Two generations of architecture coexist:

```
src/text_to_gds/
├── server.py                  ← GOD MODULE: MCP entry + public API (95 tools, 3050 LOC)
├── cli.py                     ← 5 console-script entry points
│
├── ░ Generation 1: flat physics-compiler modules (the documented pipeline) ░
│   design_intent.py  feasibility_gate.py  physics_graph.py  physics_compiler.py
│   drc.py  extraction.py(DEAD)  signoff.py  solver_agreement.py  auto_repair.py
│   cpw_physics.py  junction_physics.py  squid_physics.py  jpa_physics.py …
│
├── ░ Generation 1.5: "wave"/"extensions"/"phase" accretion (15 modules) ░
│   improvements.py  next_improvements.py  third_wave.py  phase8_operations.py
│   *_extensions.py ×9  (delivery, em, foundry, measurement, nonlinear,
│                         physics, platform, quantum, scientist)
│
├── ░ Generation 2: the "AI-Native platform" engine packages (mostly untracked) ░
│   design_graph/  dependency_graph/  geometry_intelligence/  topology_reasoning/
│   engineering_reasoner/  engineering_rules/  engineering_visualization/
│   design_memory/  design_optimization/  device_understanding/  digital_twin/
│   literature_graph/  generators/  device_classifier/  device_library/
│   device_templates/  measurement_kb/
│
├── ░ Backend / solver abstraction layers (overlapping) ░
│   backends/  simulation/  solvers/  em_solvers.py  em_bridges.py  em_extensions.py
│   *_bridge.py (palace, elmer, meep, pyaedt)  open_q3d.py  open_solver_manager.py
│
├── ░ Layout / geometry ░  layout/  geometry/  pcells/  components/  routing/  pdk/
├── ░ Review ░             review/  +  review/layout_critic.py  +  layout_critic/   (3 systems)
├── ░ Misc subsystems ░    theory/  physics/  process/  reports/  synthesis/  core/
└── extraction/  validation/  verification/  optimization/   ← packages shadowing flat .py (DEAD .py)
```

**Architectural reading:** the documented pipeline (CLAUDE.md §"physics-compiler pipeline") still
lives in Generation-1 flat modules and is what `server.py` actually calls. Generation-2 "engine"
packages — the substance of the QuantumCAD OS vision (design graph, geometry intelligence, topology
reasoning, engineering reasoner, digital twin) — exist as standalone APIs with their own tests but
are **not invoked by the product pipeline** (§3.3). The repo is mid-migration with no migration
having been completed end-to-end.

---

## 3. Dependency Graph

### 3.1 `server.py` is the hub of a star, not a layered DAG
`server.py` imports broadly across the flat module set and re-exports it as both the MCP tool
surface and the Python public API (CLAUDE.md confirms: "All 80+ `@mcp.tool()` functions … are also
importable directly"). Consequences:

- **Import cost is paid eagerly.** Test *collection* alone takes ~15 s — the import graph fans out
  through nearly the whole package before a single test runs (§11).
- **No enforced layering.** Physics, layout, solver, review, and reporting are all reachable
  laterally; there is no `core → kernel → domain → api` direction. Any module can import any other.
- **Change blast radius is large.** F2 is a live example: a single edit to `extracted_device.py`
  silently broke a test two layers away, undetected until this audit.

### 3.2 Backend abstraction is triplicated
Three parallel notions of "a solver backend" coexist with overlapping responsibilities:
- `backends/` (the documented `Backend` ABC + availability + sidecar integration),
- `simulation/` (`SolverAdapter` ABC — raw subprocess/parse cycle),
- `solvers/` + flat `*_bridge.py` + `em_solvers.py`/`em_bridges.py`/`em_extensions.py`.

CLAUDE.md acknowledges `backends/` vs `simulation/` as intentional, but the flat `em_*` and
`*_bridge.py` families are a third, undocumented layer.

### 3.3 The new engine packages are orphaned (measured)
References to each Generation-2 package **from `server.py`**:

| Package | refs in server.py | Package | refs in server.py |
|---|---|---|---|
| `design_graph` | **0** | `device_understanding` | **0** |
| `dependency_graph` | **0** | `digital_twin` | **0** |
| `topology_reasoning` | **0** | `engineering_rules` | **0** |
| `engineering_reasoner` | **0** | `engineering_visualization` | **0** |
| `design_memory` | **0** | `literature_graph` | **0** |
| `design_optimization` | **0** | `generators` | **0** |
| `geometry_intelligence` | 1 | | |

This confirms `IMPLEMENTATION_REPORT.md` §9 ("Stage 2 — not wired in server.py") and quantifies it:
the platform's flagship reasoning layer reaches the user through **zero** MCP tools.

---

## 4. Module Maturity Matrix

Maturity tiers: **Prod** (wired into pipeline + tested + truth-contract enforced) · **Lib**
(implemented + tested, not wired into product) · **Stub** (API surface only / dict placeholders) ·
**Dead** (unreachable) · **Debt** (works but structurally problematic).

| Subsystem | Representative modules | Tier | Evidence / note |
|---|---|---|---|
| Physics-compiler pipeline | `design_intent`, `feasibility_gate`, `physics_graph`, `signoff`, `auto_repair`, `solver_agreement` | **Prod** | Called by `server.py`; covered by `test_physics_*`, `test_signoff*` |
| Physics analytics | `cpw_physics`, `junction_physics`, `squid_physics`, `theory/` | **Prod/Lib** | Labelled `analytical`, confidence ≤0.65; matches-literature tests |
| Layout backends | `layout/`, `backends/kqcircuits…`, `pcells/` | **Prod** | Priority chain works; `pcells` correctly `visualization_only` |
| Solver adapters | `simulation/openems_adapter`, `…josephsoncircuits_adapter`, `scqubits_adapter` | **Prod** | JC.jl + scqubits EXECUTE; openEMS/Palace/Elmer honest SKIP |
| Review committee | `review/` (5-agent) | **Prod** | `review_committee()` min-score; tested |
| Review (2nd) | `review/layout_critic.py` (12-agent) | **Lib** | Per IMPLEMENTATION_REPORT; overlaps `committee.py` |
| Review (3rd) | `layout_critic/` package | **Debt/Dup** | Third parallel critic; relationship to the other two undocumented |
| Design graph | `design_graph/` | **Lib** | 0 server refs |
| Geometry intelligence | `geometry_intelligence/` (pkg) | **Lib** | pkg active; flat `geometry_intelligence.py` is **Dead** |
| Topology reasoning | `topology_reasoning/`, flat `topology.py` (718 LOC) | **Lib + Debt** | pkg + flat module, overlapping concern |
| Engineering reasoner | `engineering_reasoner/` | **Lib** | 0 server refs |
| Engineering rules | `engineering_rules/` (7 rule modules) | **Lib** | 0 server refs |
| Digital twin | `digital_twin/` | **Lib** | 0 server refs; reliability models confidence 0.35–0.45 |
| Literature graph | `literature_graph/` (incl. `paper_kb.py` 711 LOC) | **Lib** | 11 reference devices; 0 server refs |
| Engineering visualization | `engineering_visualization/` | **Stub** | IMPLEMENTATION_REPORT §4: "output … are stub dicts. No matplotlib figures generated" |
| ML / GNN | — | **Absent** | Correctly deferred (IMPLEMENTATION_REPORT §4) |
| Shadowed flat modules | `extraction.py`, `verification.py`, `validation.py`, `optimization.py`, `geometry_intelligence.py` | **Dead** | §8 |
| Accretion layer | `improvements`, `next_improvements`, `third_wave`, `phase8_operations`, `*_extensions`×9 | **Debt** | §7.3 |

---

## 5. Technical Debt

1. **God module (`server.py`, 3,050 LOC, 95 tools).** Public API, MCP wiring, and orchestration
   are fused. No façade; tests reach in via `from text_to_gds.server import …`.
2. **No type gate.** `mypy` absent from `pyproject.toml` dev deps (only `pytest`, `ruff`). The
   CLAUDE.md/CI vision requires mypy; 70k LOC are currently type-unchecked. Pydantic models exist
   but there is no static contract verification.
3. **Three `schema`-field Pydantic warnings** (`device_optimizer.py`, `extracted_device.py`,
   `microwave_validator.py`) — `Field name "schema" shadows attribute in parent "BaseModel"`.
   Cosmetic but persistent; surfaces on every test run.
4. **Mixed source/working-tree state.** Generation-2 packages are largely **untracked** (`??` in
   git status) and intermixed with tracked modifications (`M`). The "new platform" has never been
   committed, so CI/history cannot have validated it.
5. **Process/config sprawl at repo root.** `process.yaml`, `process.py`, `process/`,
   `process_database/`, `process_database.py`, `process_reference.json` — six process-related
   roots with unclear precedence.
6. **No enforced dependency direction** (§3.1) → high change blast radius (F2 is the proof).

---

## 6. Placeholder Modules

- **`engineering_visualization/`** — *self-declared* placeholder. `IMPLEMENTATION_REPORT.md` §4:
  view outputs are "stub dicts. No matplotlib figures are generated yet." API surface + `ViewType`
  enum exist; rendering does not. This is the clearest honest stub.
- **`generators/`** — thin wrappers delegating to `server.compile_layout()`; not standalone
  generators (IMPLEMENTATION_REPORT §4). Acceptable as adapters but mislabeled by name.
- **String `placeholder` appears across 14 files** (incl. `adapters.py`, `pyaedt_bridge.py`,
  `superconducting_eda_compiler.py`, `device_library/devices.py`, several `pcells/*`). Each needs
  individual triage in Phase 0 to separate "placeholder geometry for visualization" (legitimate,
  must carry `visualization_only=True`) from "placeholder result standing in for a solver"
  (truth-contract risk).
- **2 `NotImplementedError`** sites — abstract-method guards (expected for ABCs); verify they are
  on base classes, not reachable product paths.

---

## 7. Duplicated Logic

### 7.1 Three review/critic systems
- `review/` package: `committee.py` (5-agent, documented) **plus** `layout_critic.py` (12-agent)
  **plus** `reviewer.py`, `layout.py`, `layout_design_review.py`, `final_reviewer.py`,
  `solver_evidence_agent.py` — multiple overlapping entry points in one package.
- `layout_critic/` **top-level package** (`critic.py`, `types.py`) — a third critic.

Three implementations of "review the layout"; only `review/committee.py` is documented as the
contract. The min-score invariant must hold across whichever wins — today it is ambiguous which does.

### 7.2 Duplicate-concept module pairs (verified present)
| Concept | Files |
|---|---|
| Design-intent parsing | `design_intent.py` **and** `ai/design_intent.py` (CLAUDE.md says intentional — but two parsers for one job is still drift risk) |
| Reference comparison | `reference_compare.py` **and** `reference_matching.py` |
| Layout quality scoring | `layout_quality.py` **and** `quality_scorer.py` |
| JPA physics | `jpa_physics.py` **and** `jpa_analysis.py` (+ `theory/kerr_jpa.py`) |
| Traveling-wave | `traveling_wave.py` **and** `jtwpa.py` **and** `pcells/traveling_wave.py` |
| Topology | flat `topology.py` (718) **and** `topology_reasoning/` package |
| Geometry intelligence | flat `geometry_intelligence.py` (dead) **and** `geometry_intelligence/` |

### 7.3 Accretion layers (15 modules)
`improvements.py`, `next_improvements.py`, `third_wave.py`, `phase8_operations.py`, and 9
`*_extensions.py` files. Names encode *when* code was added, not *what concern* it owns — the
signature of feature-bolting without an abstraction. Server exposes `list_improvement_functions`,
`list_next_improvement_functions`, `list_third_wave_improvement_functions` as separate tools,
cementing the accretion into the API.

---

## 8. Dead Code (verified)

**Five top-level modules are shadowed by same-named packages.** Python resolves the *package*
(`__init__.py`) and never the `.py`, confirmed by importing each and printing `__file__`:

```
import text_to_gds.geometry_intelligence → …/geometry_intelligence/__init__.py   (446-LOC .py unreachable)
import text_to_gds.extraction            → …/extraction/__init__.py              (548-LOC .py unreachable)
import text_to_gds.verification          → …/verification/__init__.py            (495-LOC .py unreachable)
```

| Shadowed (dead) file | LOC | Shadowing package |
|---|---|---|
| `extraction.py` | 548 | `extraction/` (note: `extraction/_legacy.py` is also 548 LOC — the migration copied the file and left the original) |
| `verification.py` | 495 | `verification/` |
| `geometry_intelligence.py` | 446 | `geometry_intelligence/` |
| `validation.py` | 304 | `validation/` |
| `optimization.py` | 114 | `optimization/` |
| **Total** | **1,907** | |

> ⚠️ Risk for Phase 0: CLAUDE.md documents `src/text_to_gds/extraction.py::quantity()` as "the only
> correct way to record a derived value." If callers do `from text_to_gds.extraction import quantity`,
> they now hit `extraction/__init__.py`, **not** the documented file. Confirm the package re-exports
> an equivalent `quantity()` before deleting the shadowed `.py`, or provenance recording silently
> changes behavior. (`process.py` is **not** dead — `process/` has no `__init__.py`.)

Beyond shadowing, the orphaned Generation-2 packages (§3.3) are *effectively* dead from the
product's perspective: reachable by tests only, never by a user through the MCP surface.

---

## 9. Missing Abstractions

1. **`Component` model (the #1 vision gap).** The user's brief demands a component-centric kernel
   (`Component → Reference → Port → CrossSection → Route → Hierarchy → Technology → Metadata`).
   Today geometry is polygon-/PCell-centric; there is no first-class `Component`/`Port`/`CrossSection`
   abstraction owning geometry. gdsfactory already provides this — it should be adopted, not
   reinvented.
2. **A public-API façade** separating "MCP transport" from "library API" so `server.py` stops being
   both.
3. **One backend protocol.** Collapse `backends/` + `simulation/` + `solvers/` + `*_bridge.py` into a
   single `prepare/run/parse/verify/report` adapter interface (the brief's solver-adapter contract).
4. **A single review interface** with pluggable reviewers (replace the 3 systems in §7.1).
5. **A graph layer** unifying `design_graph`, `dependency_graph`, `geometry_graph`, `physics_graph`,
   `literature_graph`, `topology` onto one node/edge/serialization substrate (NetworkX) — today each
   reinvents nodes/edges.
6. **Plugin registration.** The brief requires every subsystem to register via a plugin interface;
   currently `PCELL_REGISTRY` and ad-hoc dicts in `server.py` are the only registries.

---

## 10. Testing Coverage

**Measured (`uv run pytest --continue-on-collection-errors`):**
```
642 passed, 8 skipped, 1 warning, 1 ERROR  in 119.90s
```

- 🔴 **`tests/test_physics_compiler_loop.py` fails to collect.**
  `ImportError: cannot import name 'extract_device' from 'text_to_gds.extracted_device'`.
  `grep "def extract_device"` → **0 matches** anywhere in `src/`. The symbol was removed/renamed in
  the working-tree edit to `extracted_device.py` (git `M`); the importing test is **committed**.
  Net: the green-suite claim is false until this is fixed.
- 8 skips are legitimate external-solver gates (`TEXT_TO_GDS_RUN_EXTERNAL`), not failures.
- **No coverage measurement exists** — `pytest-cov` is not a dependency; line/branch coverage is
  unknown. "63 test files / 650 tests" measures *volume*, not *coverage*. Given 315 source files,
  many modules (esp. the orphaned engine packages and dead shadowed files) are likely untested or
  tested only through their package `__init__`.
- **Tests reach into internals** (`from text_to_gds.server import …`), so they pin the god-module
  shape and will resist the refactor in §9.

---

## 11. Performance Bottlenecks

Assessed structurally (no profiler was run; flagged honestly):
- **Import-time fan-out.** ~15 s to *collect* tests and ~120 s for the suite. The eager,
  import-everything `server.py` means every entry point pays the full dependency graph (gdsfactory,
  klayout, matplotlib, numpy, trimesh, optional heavy libs) up front. For an MCP stdio server this is
  per-process startup latency.
- **No lazy backend loading.** Optional heavy backends (qiskit-metal, scqubits, pyaedt) are gated by
  availability checks, but the module graph still imports broadly at startup.
- **70k LOC / 315 files in one importable package** inflates the namespace Python must build.

Recommend adding `pytest --durations=25` and an import-time profile (`python -X importtime`) in
Phase 0 to get real numbers before optimizing.

---

## 12. Documentation Quality & Reconciliation

Documentation is **voluminous and well-written** (README 55 KB; ARCHITECTURE, SOP, AGENTS, multiple
status reports) — but **aspirational claims outrun verified state**, which is the project's own
cardinal sin applied to its docs:

| Claim (source) | Measured reality | Verdict |
|---|---|---|
| "393 passed, 2 skipped … Dead Code — none" (old `PROJECT_AUDIT.md`) | 642 passed + 1 error; 1.9k LOC dead | ❌ stale/false |
| "648 passed, 8 skipped, 0 failed" (`IMPLEMENTATION_REPORT.md`) | 642 passed, 8 skipped, **1 error** | ❌ false now |
| "Fake Claims — None Found" (old audit) | True for *physics provenance*; **not** for status docs | ⚠️ partial |
| "All benchmark figures regenerated" (IMPLEMENTATION_REPORT) | Not re-verified this audit | ⚠️ unverified |
| Engineering-visualization implemented | Self-declared stub dicts | ⚠️ honest in body, oversold in headline |

The same truth-contract enforced on `source="LLM"` quantities must be extended to **status reports
and README claims** (the brief's "Claim validation" / "If README claims a feature there must be
tests, examples, artifacts — otherwise fail CI"). Today nothing enforces that, so docs drift.

Positive: CLAUDE.md, `SOLVER_EVIDENCE_CONTRACT.md`, `PHYSICS_GRAPH_SCHEMA.md`, and the honest
SKIPPED-solver accounting are genuinely high quality and should be preserved as the contract spine.

---

## 13. Reconciliation: what is actually solid vs. what is scaffolding

**Solid, keep, build on:**
- Physics-compiler pipeline + provenance/lineage contract (`quantity()`, value records).
- Honest solver gating (EXECUTED/PREPARED/SKIPPED/FAILED) — JC.jl + scqubits truly execute.
- Solver-agreement engine (≥2 sources, confidence model).
- 5-agent min-score review committee.
- Literature `paper_kb.py` (11 papers w/ citations) — strong seed for the knowledge graph.

**Scaffolding, integrate or cut:**
- Generation-2 engine packages (great ideas, 0% wired).
- 3 review systems → 1.
- 15 accretion modules → fold into owning subsystems.
- 1.9k LOC dead shadowed files → delete after confirming re-exports.

---

## 14. Prioritized Remediation Roadmap (gates Phase 1)

**Phase 0 — Stop the bleeding (must complete before *any* new feature code):**
1. Fix F1/F2: restore `extract_device` (or update the committed test) → suite green.
2. Decide the fate of the 5 shadowed files (§8); confirm `extraction/` re-exports `quantity()`;
   delete dead `.py` or rename packages. Re-run suite.
3. Commit (or explicitly remove) the untracked Generation-2 packages so git history reflects reality.
4. Add `mypy` + `pytest-cov` to dev deps; record a **baseline** (don't gate yet).
5. Add a CI job that runs `ruff`, `pytest` (no `--continue-on-collection-errors`), and a
   **claim-validation** check (README feature → test/artifact exists), per the brief.

**Phase 1 — Establish the kernel boundary (first real architecture work):**
6. Introduce the target `src/` layout incrementally with a façade; map the existing flat modules
   onto `cad_kernel/geometry/pdk/routing/topology/graph/extraction/simulation/optimization/review/
   knowledge/learning/reports/visualization` **without** big-bang moves.
7. Adopt gdsfactory's `Component/Port/CrossSection` as the geometry kernel (§9.1) — do not reinvent.
8. Collapse the backend triplication (§3.2) behind one `prepare/run/parse/verify/report` adapter.
9. Wire **one** Generation-2 capability end-to-end through `server.py` as the integration template
   (recommend `geometry_intelligence` or `design_graph`), then replicate.

Each subsequent phase follows the brief's 10-step cycle (design → implement → test → benchmark →
artifacts → README → API docs → diagrams → migration notes → IMPLEMENTATION_REPORT).

---

## 15. Audit Sign-off Gate

Per the brief ("Do NOT modify code until this report is complete"), this report is the gate. The
**single most important precondition** for starting Phase 1 is closing **F1/F2** — a codebase whose
own test suite cannot collect cannot be safely refactored. Recommend the first action after this
audit is approved be a tightly-scoped Phase-0 fix PR (items 1–5 above), reviewed and merged, before
any architectural work begins.

*No source code was modified in producing this audit. All numbers are reproducible on this checkout
as of 2026-06-29.*
