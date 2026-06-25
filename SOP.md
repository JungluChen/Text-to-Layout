# SOP — Standard Operating Procedures

**Text-to-GDS Physics Compiler**  
**Version:** 2.0  
**Updated:** 2026-06-24

---

## Purpose

This document defines the end-to-end standard operating procedure for
upgrading and operating the Text-to-GDS system as a professional solver-first
superconducting quantum EDA platform. All truth contracts from the README are
preserved and strengthened.

Core invariants that no SOP step may violate:

1. `source = "LLM"` is an invalid provenance label for physical values.
2. A skipped solver is reported as `SKIPPED` and never counts as signoff evidence.
3. Review committee score = minimum across all reviewers (never averaged).
4. `physics_graph.json` is the source of truth for all solver and signoff stages.
5. Level 5+ is required for any claim of "physics signoff".
6. Level 6 is required for any claim of "measurement-calibrated".

---

## SOP-0: Intake

**Agent:** Product / Requirement Agent  
**Output:** `PROJECT_AUDIT.md`

### Tasks

1. Read `README.md`, `pyproject.toml`, `examples/`, `skills/`, `scripts/`, `src/`.
2. Run `uv run python scripts/check_external_tools.py`.
3. Run `uv run pytest --tb=no -q`.
4. Run `uv run ruff check .`.
5. Identify:
   - Current capabilities (what executes today).
   - Missing pieces (absent modules, schemas, tests, docs).
   - Fake claims (any `SOLVER EXECUTED` without output file evidence).
   - Broken commands (non-zero exit from documented command).
6. Record SOP compliance table.

### Pass

All documented commands run or are marked optional with install steps.

---

## SOP-1: Architecture

**Agent:** System Architect Agent  
**Output:** `ARCHITECTURE.md`

### Tasks

1. Define the full pipeline:

   ```
   prompt → design_intent.json → physics gate → layout backend
   → GDS + sidecar → DRC → extraction.json → physics_graph.json
   → solver inputs → solver execution → agreement → review
   → repair → signoff
   ```

2. Map every stage to a module, its input contract, and its output schema.
3. Define module boundaries (backends vs layout vs review vs signoff).
4. List all key invariants.
5. Document external tool discovery logic.

### Pass

Every stage has a corresponding module listed with schema output.

---

## SOP-2: Physics Compiler

**Agent:** Physics Compiler Agent  
**Output:** Updated `PHYSICS_GRAPH_SCHEMA.md` + validator hooks

### Tasks

1. Make `physics_graph.json` the source of truth for all solver stages.
2. Every numeric value must include:

   ```json
   {
     "value": 50.0,
     "unit": "ohm",
     "source": "extracted width/gap + process",
     "method": "conformal CPW model",
     "confidence": 0.86,
     "file_path": "workspace/artifacts/device.physics_graph.json"
   }
   ```

3. Reject `source = "LLM"` at both `signoff.py` and `backends/base.py`.
4. Define schemas: `text-to-gds.physics-graph.v1`, `text-to-gds.sidecar.v0`,
   `text-to-gds.extraction.v1`.
5. Add validator hooks to `PHYSICS_GRAPH_SCHEMA.md`.

### Pass

No `source = "LLM"` record passes `validate_value_records()`.

---

## SOP-3: Layout Backend

**Agent:** Layout Backend Agent  
**Output:** Updated `src/text_to_gds/layout/backends.py`

### Tasks

1. Enforce backend priority:

   | Priority | Backend | When |
   |---|---|---|
   | 1 | KQCircuits | CPW, resonators, airbridges, IQM stack |
   | 2 | Qiskit Metal | Transmon, CPW routing, launch pads |
   | 3 | gdsfactory | GDS booleans, layer remapping |
   | 4 | local_pcells | Tests/demos only; never EM solver input |

2. Log selected backend in sidecar `info.backend`.
3. Return `status = "UNSUPPORTED"` (not fake geometry) when backend unavailable.
4. Local PCell used for production → emit error to review committee.
5. Separation invariant: `*_layout.png` is geometry only; never mixed with solver
   status.

### Pass

Backend selection logged; unavailable backend returns UNSUPPORTED; no local PCell
for production without explicit warning.

---

## SOP-4: Solver Backend

**Agent:** Solver Integration Agent  
**Output:** Updated backends + status scripts

### Managed Solvers

| Solver | Role | Output |
|---|---|---|
| JosephsonCircuits.jl | JPA/JTWPA harmonic balance | gain array, pump sweep |
| scqubits | Qubit Hamiltonian spectra | eigenvalues, f01, anharmonicity |
| openEMS | FDTD S-parameters | `.s2p` Touchstone |
| JoSIM | SFQ transient | voltage/flux waveform |
| Palace | Eigenmode FEM | f0, Q factor |
| Elmer FEM | Electrostatic capacitance | capacitance matrix |
| FastCap2 | Capacitance extraction | capacitance values |
| FastHenry2 | Inductance extraction | inductance matrix |

### Status Rules

Only `executed` with a real output file counts as solver evidence:

| Status | Meaning | Evidence |
|---|---|---|
| `executed` | Solver ran, output file exists and non-empty | **Yes** |
| `installed` | Package importable | No |
| `binary_found` | Executable found | No |
| `input_files_prepared` | Handoff files exist | No |
| `skipped` | Unavailable or not configured | No |
| `failed` | Attempted, no output | No |
| `planned` | Future integration | No |

### Scripts

- `scripts/check_external_tools.py` — report all backend statuses.
- `scripts/bootstrap_external_repos.py --clone` — clone upstream repos.
- `scripts/setup_external_tools.py` — install Julia packages.

### Pass

`adapter_status == "executed"` and output file exists and is non-empty.  
Fail: `status == "executed"` but no output file.

---

## SOP-5: Evidence and Signoff

**Agent:** Evidence / Signoff Agent  
**Output:** `SOLVER_EVIDENCE_CONTRACT.md`, `SIGNOFF_CRITERIA.md`

### Signoff Levels

| Level | Name | Required |
|---|---|---|
| 0 | Geometry generated | GDS file exists |
| 1 | DRC passed | Level 0 + DRC `status=passed` |
| 2 | Extraction complete | Level 1 + sidecar + `extraction.json` |
| 3 | Analytical sanity | Level 2 + analytical checks + valid value records |
| 4 | One solver executed | Level 3 + ≥1 real solver output file |
| **5** | **Physics signoff** | Level 4 + ≥2 independent solvers + agreement |
| **6** | **Measurement-calibrated** | Level 5 + imported measurement data + fit |

**Only Level 5+ may be called physics signoff.**  
**Only Level 6 may be called measurement-calibrated.**

### Hard Stops

- Skipped solver → never evidence.
- Missing output file → `executed` is invalid → blocker.
- `source = "LLM"` → blocker.
- Generated plot alone → not evidence.
- Generated solver deck → not evidence.

---

## SOP-6: Review Committee

**Agent:** Final Auditor Agent  
**Output:** `REVIEW_REPORT.md` per design

### Five Reviewers

1. **Physics Review Agent** — JJ topology, nonlinear model, Ic/Lj/C ranges,
   resonance plausibility, JPA pump model.
2. **Microwave Review Agent** — CPW GSG, Z0, ports, S-parameter
   passivity/reciprocity, Touchstone file.
3. **Fabrication Review Agent** — layer map, min width, spacing, JJ overlap,
   via enclosure, airbridge rules.
4. **Measurement Review Agent** — RF port, pump port, flux line, DC bias,
   wirebond/probe pads, measurable quantities.
5. **Literature Review Agent** — values plausible vs known superconducting
   device ranges; flags unrealistic gain, bandwidth, Ic, C, Z.

### Scoring Rules

```
score = min(reviewer.score for all reviewers)
approved = all(reviewer.passed for all reviewers)
pass = score >= 90 AND approved is True
```

- One error (−40 pts) in any reviewer → score ≤ 60 → cannot pass.
- Scores are never averaged.
- One error in any reviewer blocks signoff regardless of other scores.

---

## SOP-7: Auto-Repair

**Agent:** Repair Agent  
**Output:** Updated artifacts + `accepted: True/False`

### Tasks

1. Read blocking issues from review committee output.
2. Fix only the blocking issues (no scope creep).
3. Re-run DRC, extraction, solver checks, and review.
4. Stop after max 3 repair loops (SOP target; implementation default is 6).
5. Report `accepted: True` or `accepted: False` with reason.

### Pass

`accepted: True` with `score >= 90`.

### Fail

Budget exhausted or `repair_fn` returns unchanged state.

---

## SOP-8: Benchmarks

**Agent:** Benchmark Agent  
**Output:** Separate `*_layout.png` and `*_benchmark.png`

### Asset Rules

- `*_layout.png` — geometry only; produced by `render_layout_screenshot()`.
- `*_benchmark.png` — geometry + extraction summary + solver evidence panel.
- **Never overwrite** `*_layout.png` with a benchmark panel.

### Solver Panel States

| State | Color | When |
|---|---|---|
| `SOLVER EXECUTED` | Green | Output file exists and verified |
| `SKIPPED: <reason>` | Grey | Solver unavailable |
| `FAILED: <reason>` | Red | Solver attempted, no output |
| `INPUT FILES PREPARED` | Orange | Handoff files exist, solver not run |

**Never show `SOLVER EXECUTED` unless a real solver-owned output file exists.**

---

## SOP-9: Skills

**Agent:** Skill Packaging Agent  
**Install:** `npx skills install JungluChen/Text-to-Layout`

### Skills

| Skill | Role |
|---|---|
| `text-to-gds` | Core layout, DRC, extraction, graph |
| `text-to-gds-simulation` | Solver handoffs, JC.jl, openEMS, scqubits |
| `text-to-gds-circuit-design` | Pre-layout planning, feasibility gate |
| `text-to-gds-layout-design` | GDS + route + DRC + extract + review |
| `text-to-gds-signoff` | Artifact audit, level evaluation |
| `text-to-gds-physics-signoff` | Full signoff: rejects layout without solver evidence |

### Each Skill SKILL.md Must Include

- YAML frontmatter with `name` and `description`.
- **When To Use** section.
- **Hard Stops** section listing non-negotiables.
- **Solver Requirements** section.
- **Example Commands** runnable from the repository root.
- **Failure Cases** section.

---

## SOP-10: QA

**Agent:** QA / Test Agent  
**Output:** Updated `tests/` including `tests/test_sop_qa.py`

### Required Test Coverage

| Invariant | Test location |
|---|---|
| `source="LLM"` physical value fails validation | `test_no_fake_gain.py` |
| Skipped solver cannot increment signoff level | `test_signoff_contract.py` |
| Missing output file makes `executed` invalid | `test_solver_artifacts_required.py` |
| CPW without GSG fails microwave review | `test_sop_qa.py` |
| JPA without nonlinear JJ model fails physics review | `test_sop_qa.py` |
| `*_layout.png` and `*_benchmark.png` are separate | `test_sop_qa.py` |
| README commands run or are marked optional | `test_sop_qa.py` |
| Skill install path exists for all 6 skills | `test_sop_qa.py` |

---

## SOP-11: Documentation

**Agent:** Documentation Agent  
**Output:** `README.md` + all contract docs

### Rules

1. All backend status claims in README must match `check_external_tools.py` output.
2. All install commands must be verified runnable.
3. All solver evidence claims must point to real output files.
4. All limitations must be stated explicitly.
5. All signoff level claims must be backed by evidence.

### Documents Required

| Document | Purpose |
|---|---|
| `README.md` | Truthful overview + install + quick start + limitations |
| `ARCHITECTURE.md` | Pipeline + module boundaries + invariants |
| `AGENTS.md` | Agent descriptions + responsibilities + pass/fail rules |
| `SOP.md` | This document |
| `PROJECT_AUDIT.md` | Current state + gaps + next actions |
| `REVIEW_REPORT.md` | Template for per-design review output |
| `SOLVER_EVIDENCE_CONTRACT.md` | Solver status vocabulary + numeric value contract |
| `SIGNOFF_CRITERIA.md` | Level 0-6 definitions + hard stops |
| `PHYSICS_GRAPH_SCHEMA.md` | IR schema + node/edge types + validator hooks |
| `EXTERNAL_BACKEND_INTEGRATION_STATUS.md` | Live backend status table |
| `skills/*/SKILL.md` | Per-skill operating instructions |

---

## Final Deliverables Checklist

- [x] `PROJECT_AUDIT.md`
- [x] `ARCHITECTURE.md`
- [x] `AGENTS.md`
- [x] `SOP.md` (this file)
- [x] `REVIEW_REPORT.md`
- [x] `SOLVER_EVIDENCE_CONTRACT.md`
- [x] `SIGNOFF_CRITERIA.md`
- [x] `PHYSICS_GRAPH_SCHEMA.md`
- [x] Updated `README.md`
- [x] Updated `skills/*/SKILL.md` (all 6)
- [x] Updated `tests/` (SOP-10 coverage)
- [x] All commands verified:
  - `uv run ruff check .` → PASS
  - `uv run python -m compileall src scripts examples` → PASS
  - `uv run pytest` → 393 passed, 2 skipped
  - `uv run python scripts/check_external_tools.py` → PASS
  - `uv run python examples/zero_to_one_demos.py all` → functional
