# AGENTS.md — Text-to-GDS Multi-Agent System

**Version:** 2.0  
**Updated:** 2026-06-24

Local-first EDA harness for superconducting quantum GDS layout. Every agent
listed here is a **deterministic Python function** — no LLM API calls, no
network calls, no fake data. All verdicts are reproducible functions of inputs.

---

## Development Commands

```bash
py -3 -m uv sync                              # core install
py -3 -m uv sync --extra research             # all optional backends
uv run pytest                                  # full suite
uv run ruff check .                            # lint
uv run python scripts/check_external_tools.py # backend status
uv run python examples/zero_to_one_demos.py all
```

---

## Project Layout

```
src/text_to_gds/
  server.py                 MCP server + 93 public tools
  signoff.py                Signoff level evaluator (Level 0-6)
  auto_repair.py            Auto-repair loop (≤6 iterations)
  artifact_validator.py     Per-solver artifact checker
  solver_agreement.py       Cross-validate ≥2 independent sources
  physics_graph.py          Compiler IR extractor
  design_intent.py          Pre-layout feasibility gate
  review/
    committee.py            Aggregate verdict (score = min)
    physics.py              Physics reviewer
    microwave.py            Microwave reviewer
    fabrication.py          Fabrication reviewer
    measurement.py          Measurement reviewer
    literature.py           Literature reviewer
  backends/
    base.py                 Backend ABC + value_record()
    kqcircuits_backend.py   Priority-1 layout backend
    qiskit_metal_backend.py Priority-2 layout backend
    gdsfactory_backend.py   Priority-3 layout backend
    josephsoncircuits_backend.py  JPA solver
    scqubits_backend.py     Qubit spectrum solver
    openems_backend.py      FDTD EM solver
    palace_backend.py       Eigenmode FEM solver
    elmer_backend.py        Electrostatic capacitance
    pyepr_backend.py        Energy participation
  physics/
    cpw_model.py            Analytical CPW (confidence=0.65, method=analytical)
    extraction_provenance.py  ExtractedQuantity + ProvenanceChain
  layout/
    backends.py             LayoutBackend ABC
    technology.py           SuperconductingTechnology
    kqcircuits_wrapper.py   Import guard
  core/
    units.py                Physical constants (CODATA 2019) + Quantity
    provenance.py           provenance_record() + write_bundle()

skills/
  text-to-gds/SKILL.md
  text-to-gds-simulation/SKILL.md
  text-to-gds-circuit-design/SKILL.md
  text-to-gds-layout-design/SKILL.md
  text-to-gds-signoff/SKILL.md
  text-to-gds-physics-signoff/SKILL.md

scripts/
  check_external_tools.py     Backend status report
  bootstrap_external_repos.py Clone upstream repos
  setup_external_tools.py     Install Julia packages
  generate_assets.py          Regenerate all benchmark assets
  bundle_plugin.py            Package skill for npx install

tests/
  test_no_fake_gain.py        source="LLM" and NaN gain rejection
  test_solver_artifacts_required.py  Missing output file → failed
  test_signoff_contract.py    Skipped solver → no level increment
  test_physics_engine.py      CPW, JJ, provenance, agreement, repair
  test_openems_real_s2p.py    openEMS skipped/failed/executed paths
  test_pdk.py                 PDK loading + layer map validation
  test_sop_qa.py              SOP-10 invariant checks
```

---

## Agent Descriptions

### SOP-0 · Product / Requirement Agent

**Module:** `scripts/check_external_tools.py`  
**Input:** Repository root  
**Output:** `PROJECT_AUDIT.md`

Reads the full codebase, identifies capabilities, missing pieces, fake claims,
and broken commands. Runs `check_external_tools.py` and `pytest`.

**Pass:** All documented commands run or are marked optional with install steps.  
**Fail:** Any README command returns non-zero without explanation.

---

### SOP-1 · System Architect Agent

**Output:** `ARCHITECTURE.md`

Defines full pipeline with module boundaries, data flow, invariant list, and
external tool discovery logic.

**Pass:** Every stage maps to a module and a schema output.

---

### SOP-2 · Physics Compiler Agent

**Module:** `src/text_to_gds/physics_graph.py::extract_physics_graph`  
**Input:** `.sidecar.json` + process parameters  
**Output:** `physics_graph.json` (schema: `text-to-gds.physics-graph.v1`)

Makes `physics_graph.json` the source of truth for all downstream stages.
Every numeric value must carry `value`, `unit`, `source`, `method`,
`confidence`, `file_path`. Rejects `source="LLM"`.

**Pass:** All nodes have valid parameter records; `source_of_truth = physics_graph.json`.  
**Fail:** `source="LLM"` in any record; no extracted nodes; JPA without JJ node.

---

### SOP-3 · Layout Backend Agent

**Module:** `src/text_to_gds/layout/backends.py`  
**Input:** `design_intent.json` or PCell name + parameters  
**Output:** `.gds` + `.sidecar.json` + `.layout.png`

Selects the highest-priority available backend. Never silently falls back to
local PCells for production.

**Priority:** KQCircuits → Qiskit Metal → gdsfactory → local_pcells  
**Pass:** Backend logged in sidecar; unavailable backend returns `UNSUPPORTED`.  
**Fail:** `visualization_only=True` cell used as EM solver input.

---

### SOP-4 · Solver Integration Agent

**Module:** `src/text_to_gds/backends/` + `src/text_to_gds/adapters.py`  
**Input:** `physics_graph.json` + binary availability  
**Output:** Solver result JSON + solver-owned output file, or `status=skipped`

Invokes 8 external solvers with honest status reporting.

**Status vocabulary:**
- `executed` — real solver ran, output file exists and is non-empty.
- `installed` — package available; did not run. **Not evidence.**
- `binary_found` — executable found; did not run. **Not evidence.**
- `input_files_prepared` — handoff files exist; solver not run. **Not evidence.**
- `skipped` — unavailable or not configured. **Not evidence.**
- `failed` — attempted, no output. **Not evidence.**
- `planned` — future only. **Not evidence.**

**Pass:** `adapter_status == "executed"` and output file exists.  
**Fail:** `status == "executed"` but no output file.

---

### SOP-5 · Evidence / Signoff Agent

**Module:** `src/text_to_gds/signoff.py::evaluate_signoff`  
**Input:** Evidence bundle  
**Output:** `{"level": 0-6, "label": str, "passed": bool, "blockers": list}`

| Level | Label | Required |
|---|---|---|
| 0 | Geometry generated | GDS exists |
| 1 | DRC passed | Level 0 + DRC passed |
| 2 | Extraction complete | Level 1 + sidecar + extraction.json |
| 3 | Analytical sanity | Level 2 + valid value records |
| 4 | One solver executed | Level 3 + ≥1 real output file |
| 5 | **Physics signoff** | Level 4 + ≥2 solvers + agreement |
| 6 | **Measurement-calibrated** | Level 5 + measurement data + fit |

**Pass:** `level >= 5` for physics signoff claim.  
**Fail:** Any hard-stop condition; `source="LLM"`; skipped solver counted.

---

### SOP-6 · Review Committee (5 Agents + Auditor)

All agents are deterministic Python functions. No LLM.

#### Physics Review Agent
`src/text_to_gds/review/physics.py::review_physics`

Checks JJ topology, nonlinear model, extracted Ic/Lj/C, resonance plausibility
(0.1–100 GHz), and JPA pump model presence.

**Error:** Missing JJ node in JPA; Ic ≤ 0.

#### Microwave Review Agent
`src/text_to_gds/review/microwave.py::review_microwave`

Checks CPW GSG structure, Z0 (10–200 Ω), phase velocity, port existence, S-parameter
passivity and reciprocity, Touchstone file presence when openEMS reports executed.

**Error:** CPW without GSG; S-parameter gain in passive device.

#### Fabrication Review Agent
`src/text_to_gds/review/fabrication.py::review_fabrication`

Checks layer map, minimum width, spacing, JJ overlap, via enclosure, airbridge
clearance per PDK rules.

**Error:** Feature below min width; JJ layer with no base-metal overlap.

#### Measurement Review Agent
`src/text_to_gds/review/measurement.py::review_measurement`

Checks RF, pump, flux, DC ports; wirebond/probe pads; measurable quantities.

**Error:** JPA without pump port; CPW without RF port.

#### Literature Review Agent
`src/text_to_gds/review/literature.py::review_literature`

Checks parameter plausibility against known superconducting device ranges:
- JPA gain: 0–40 dB plausible; < 0 dB error.
- Ic: 0.01–100 µA per junction.
- CPW Z0: 40–70 Ω typical.
- Transmon Ej/Ec: 10–200 typical.

**Error:** Gain < 0 dB from JPA; Ic ≤ 0.

#### Final Auditor Agent
`src/text_to_gds/review/committee.py::review_committee`

- `score = min(reviewer.score for all reviewers)`
- `approved = all(reviewer.passed for all reviewers)`
- One error (−40 pts) → score ≤ 60 → cannot pass.
- Never averages scores.
- Pass: `score >= 90` AND `approved is True`.

Produces blocker list and repair suggestions in `REVIEW_REPORT.md` format.

---

### SOP-7 · Repair Agent

**Module:** `src/text_to_gds/auto_repair.py::run_auto_repair`  
**Input:** Initial state + `generate_fn` + `repair_fn`  
**Output:** `{"accepted": bool, "iterations": int, "final_score": int, ...}`

Bounded loop: stop at accepted, budget exhausted, or no-progress.

**Pass:** `accepted=True` with `score >= 90`.  
**Fail:** Budget exhausted or repair stalled.

---

### SOP-8 · Benchmark Agent

**Module:** `scripts/generate_assets.py`  
**Output:** `*_layout.png` (geometry only) + `*_benchmark.png` (geometry + evidence)

Never overwrites layout image with status panel. Never shows `SOLVER EXECUTED`
without a real output file.

**Panel states:** EXECUTED (green) | SKIPPED: reason (grey) | FAILED: reason (red)
| INPUT FILES PREPARED (orange).

---

### SOP-9 · Skill Packaging Agent

**Module:** `scripts/bundle_plugin.py`  
**Install:** `npx skills install JungluChen/Text-to-Layout`

Six skills in `skills/`. Each has YAML frontmatter + Hard Stops + Solver
Requirements + Example Commands sections.

---

### SOP-10 · QA / Test Agent

**Module:** `tests/test_sop_qa.py` + existing test files  
**Coverage required:**

| Contract | Test |
|---|---|
| `source="LLM"` fails | `test_no_fake_gain.py` |
| Skipped solver not evidence | `test_signoff_contract.py` |
| Missing output → failed | `test_solver_artifacts_required.py` |
| CPW without GSG → microwave error | `test_sop_qa.py` |
| JPA without JJ → physics error | `test_sop_qa.py` |
| Layout ≠ benchmark image | `test_sop_qa.py` |
| Skill paths exist | `test_sop_qa.py` |

---

### SOP-11 · Documentation Agent

**Output:** All `*.md` documents in repo root + `skills/*/SKILL.md`

**Hard stops:**
- Never write `SOLVER EXECUTED` without output file evidence.
- Never claim Level 5+ signoff without two independent solvers.
- Never mark a backend `executed` without version and output file.

---

## Operating Model

- All layout, DRC, and simulation stays local. No cloud backends.
- Artifacts land under `workspace/artifacts/` unless overridden.
- Prefer registered PCells over raw polygons.
- Fab/process data must be named inputs or documented defaults.
- `physics_graph.json` is the source of truth; GDS is geometry evidence only.

## Development Rules

- `uv` for dependency management.
- Public tools return typed, JSON-serializable dicts.
- `.tools/` is gitignored; binaries discovered by `tool_discovery.py`.
- Do not commit `.venv/`, caches, or large artifacts.
- Do not create module files that shadow PyPI distribution names.
