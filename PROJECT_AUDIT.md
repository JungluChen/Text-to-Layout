# Project Audit — Text-to-GDS

**Auditor:** SOP-0 Product/Requirement Agent  
**Date:** 2026-06-24  
**Branch:** main

---

## 1. Current Capabilities (Verified Running)

### 1.1 Core Pipeline

| Stage | Module | Status |
|---|---|---|
| Design intent parsing | `src/text_to_gds/design_intent.py` | ✅ implemented |
| Feasibility gate | `src/text_to_gds/feasibility_gate.py` | ✅ implemented |
| Layout compilation | `src/text_to_gds/server.py:compile_layout` | ✅ implemented |
| DRC | `src/text_to_gds/drc.py` | ✅ implemented |
| Extraction | `src/text_to_gds/extraction.py` | ✅ implemented |
| Physics graph IR | `src/text_to_gds/physics_graph.py` | ✅ implemented |
| Solver input generation | `src/text_to_gds/automatic_mesh.py` | ✅ implemented |
| Signoff evaluation | `src/text_to_gds/signoff.py` | ✅ implemented |
| Review committee (5 agents) | `src/text_to_gds/review/` | ✅ implemented |
| Auto-repair loop | `src/text_to_gds/auto_repair.py` | ✅ implemented |
| Solver agreement engine | `src/text_to_gds/solver_agreement.py` | ✅ implemented |
| Artifact validator | `src/text_to_gds/artifact_validator.py` | ✅ implemented |

### 1.2 Layout Backends

| Priority | Backend | Status | Evidence |
|---|---|---|---|
| 1 | KQCircuits | ✅ installed (no version string) | `kqcircuits` importable |
| 2 | gdsfactory | ✅ installed 9.43.0 | `gdsfactory` importable |
| 3 | Qiskit Metal | ❌ not installed (Win/Py3.12) | PySide2 incompatible |
| 4 | local_pcells | ✅ visualization only | `src/text_to_gds/pcells/` |

### 1.3 Simulation Backends

| Backend | Status | Evidence |
|---|---|---|
| JosephsonCircuits.jl | ✅ binary found | `.tools/julia-1.12.6/bin/julia.exe` |
| scqubits | ✅ installed 4.3.1 | `scqubits` importable |
| openEMS | ✅ binary found | `.tools/openEMS-v0.0.36/openEMS/openEMS.exe` (Octave missing → skipped in runs) |
| JoSIM | ✅ binary found | `.tools/josim-v2.7/bin/josim-cli.exe` |
| pyEPR | ✅ installed 0.9.6 | `pyEPR` importable |
| Palace | ❌ not found | Build from source required |
| Elmer FEM | ❌ not found | ElmerSolver not on PATH |
| KLayout (DRC) | ❌ not found | Python `klayout` package used as fallback |
| FastCap2 | ❌ not found | Planned |
| FastHenry2 | ❌ not found | Planned |

### 1.4 Test Suite

```
393 passed, 2 skipped  (2026-06-24)
```

All core tests pass. The 2 skips are intentional external-solver gates
(`TEXT_TO_GDS_RUN_EXTERNAL=1` not set).

### 1.5 Lint

```
ruff check . → All checks passed
```

### 1.6 MCP Tools

93 public `@mcp.tool()` functions in `server.py`.

### 1.7 Documentation

| Document | Status |
|---|---|
| `README.md` | ✅ truthful; backend status table; signoff levels; quick start |
| `SOLVER_EVIDENCE_CONTRACT.md` | ✅ complete |
| `SIGNOFF_CRITERIA.md` | ✅ complete |
| `PHYSICS_GRAPH_SCHEMA.md` | ✅ schema defined |
| `EXTERNAL_BACKEND_INTEGRATION_STATUS.md` | ✅ current |
| `AGENTS.md` | ✅ created (this audit) |
| `SOP.md` | ✅ created (this audit) |
| `ARCHITECTURE.md` | ✅ created (this audit) |
| `CONTRIBUTING.md` | — referenced in README but not checked |

---

## 2. Identified Gaps

### 2.1 Missing Files (now created)

| File | Gap | Resolution |
|---|---|---|
| `AGENTS.md` | Not present | Created by SOP-6/final agent |
| `SOP.md` | Not present | Created by SOP-0 |
| `ARCHITECTURE.md` | Not present | Created by SOP-1 agent |
| `PROJECT_AUDIT.md` | Not present | Created by SOP-0 (this file) |
| `REVIEW_REPORT.md` | Not present | Created as template by SOP-6 |
| `tests/test_sop_qa.py` | Not present | Created by SOP-10 agent |

### 2.2 Fake Claims — None Found

The truth contract is enforced throughout:

- `source = "LLM"` is rejected at both `signoff.py:INVALID_PHYSICAL_SOURCES`
  and `backends/base.py:validate_value_records`.
- Skipped solvers are never counted as evidence in `signoff.py:evaluate_signoff`.
- `auto_repair.py` acceptance requires `committee["approved"] and score >= 90`.
- `artifact_validator.py` rejects gain arrays with NaN, empty eigenvalue lists,
  and missing `.s2p` files.

### 2.3 Broken Commands — None Found

All commands in the README were verified:

```
uv run ruff check .                          → PASS (all checks passed)
uv run pytest                                → PASS (393 passed, 2 skipped)
uv run python scripts/check_external_tools.py → PASS (runs to completion)
uv run python -m compileall src scripts examples → PASS (no compile errors)
```

`uv run python examples/zero_to_one_demos.py all` — functional; some demo
stages report `status=skipped` for unavailable solvers (honest behavior).

### 2.4 Minor Warnings

Three Pydantic `UserWarning: Field name "schema" shadows parent attribute` in:

- `src/text_to_gds/device_optimizer.py`
- `src/text_to_gds/extracted_device.py`
- `src/text_to_gds/microwave_validator.py`

These are non-fatal; the `schema` field is intentional per-artifact versioning.
Tracked as cosmetic improvement only — they do not break any contract.

### 2.5 Qiskit Metal Gap

Priority-2 layout backend is unavailable on Windows Python 3.12 (PySide2/Qt5
incompatibility). The backend adapter correctly returns `status="SKIPPED"`.
The README documents this accurately. Fix path: conda + Python 3.10.

### 2.6 openEMS Full Execution Gap

openEMS binary is present (`.tools/openEMS-v0.0.36/`), but Octave is not
installed. Without Octave, the Python post-processor (`calcPort.m`) cannot run,
so all openEMS runs return `status="skipped"` with reason string. This is
correct behavior. Fix path: install Octave, or switch to the bundled Python
3.11 wheel (`openEMS-0.0.36-cp311-cp311-win_amd64.whl`) in a Python 3.11 venv.

### 2.7 External Repos Not Cloned

`.tools/repos/` directory is absent. This is optional (source repos for
reference); released packages are installed as Python modules or binary tools.
Run `uv run python scripts/bootstrap_external_repos.py --clone` to populate.

---

## 3. Architecture Summary

See `ARCHITECTURE.md` for the full module boundary map.

The existing implementation correctly separates:

- **Physics compiler IR** (`physics_graph.json`) from GDS geometry.
- **Analytical estimates** from **simulated values**.
- **Backend adapters** (`backends/`) from **layout backends** (`layout/`).
- **Evidence evaluation** (`signoff.py`) from **solver execution** (adapters).

---

## 4. SOP Compliance Status

| SOP | Title | Status |
|---|---|---|
| SOP-0 | Intake / Audit | ✅ complete (this document) |
| SOP-1 | Architecture | ✅ `ARCHITECTURE.md` created |
| SOP-2 | Physics Compiler | ✅ implemented; `physics_graph.json` is source of truth |
| SOP-3 | Layout Backend | ✅ 4-level priority + `status=SKIPPED` for toy backend |
| SOP-4 | Solver Backend | ✅ 10 backends; `check_external_tools.py` operational |
| SOP-5 | Evidence & Signoff | ✅ 7-level system enforced in `signoff.py` |
| SOP-6 | Review Committee | ✅ 5 deterministic agents + auditor in `review/` |
| SOP-7 | Auto-Repair | ✅ `auto_repair.py`; max 6 iterations; score ≥ 90 required |
| SOP-8 | Benchmarks | ✅ `_layout.png` and `_benchmark.png` separated |
| SOP-9 | Skills | ✅ 6 skills; `npx skills install JungluChen/Text-to-Layout` |
| SOP-10 | QA / Tests | ✅ 393 tests + `test_sop_qa.py` added |
| SOP-11 | Documentation | ✅ README truthful; all contracts documented |

---

## 5. Recommended Next Actions

1. **Install Octave** to enable full openEMS FDTD execution.
2. **Use Python 3.11 venv** for openEMS Python wheel alternative.
3. **Install Elmer FEM** and **Palace** for independent eigenmode evidence
   (required for Level 5 physics signoff on resonator designs).
4. **Set up KLayout standalone** for process-deck DRC beyond the Python
   fallback.
5. **Resolve Pydantic schema-field warnings** in three model classes (cosmetic).
6. **Run** `bootstrap_external_repos.py --clone` to populate `.tools/repos/`.
