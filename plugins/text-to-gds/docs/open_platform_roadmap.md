# Open Research Platform Roadmap

Sequencing plan for turning Text-to-GDS into an open-source-first superconducting
quantum-device design platform that does not depend on commercial EDA, and that
only accepts a layout after rule-based AI reviewers confirm it.

This document is the agreed architecture and execution order. It is a plan, not
an implementation. Each item below states its **current status** in the repo,
its **target module**, and concrete **acceptance criteria** (what must be true,
and testable, for the item to count as done).

## North-star goal

An open-source alternative to *HFSS + ADS + Cadence + a human microwave
engineer* for superconducting quantum devices. The platform's promise changes
from "here is a layout" to **"here is a layout proven to work"** — where "proven"
means: feasibility-checked before generation, simulated on open solvers,
cross-validated by solver agreement, and passed by every review agent.

## Locked architecture decisions

1. **Open solvers are first-class and default.** Commercial solvers
   (HFSS / Q3D / Sonnet) become *optional, validation-only* — used to
   cross-check the open stack for an industrial comparison, never required to
   produce a result.
2. **Review agents are rule-based deterministic checkers.** Each reviewer is a
   pure Python function encoding domain rules over the GDS, sidecar, and
   simulation outputs. No LLM/API calls, no network, fully reproducible and
   unit-testable. This preserves the project's local-first, offline guarantee.
   (A future optional LLM "explainer" layer is explicitly out of scope here.)
3. **Honesty invariants are preserved.** Every result keeps the existing
   contract: an adapter reports `skipped` with an install hint rather than
   claiming a tool ran; surrogate vs. real values stay labelled; the platform
   never fabricates reference data (see Phase 6 data-gating).

## Implementation status

- **Phase 1 — DONE.** 1.1 `open_solver_manager.py`, 1.2 open-first priority in
  `em_solvers.py`, 1.3 `open_eigenmode` (HFSS schema), 1.4 `open_q3d.py`
  (C/L matrix + IDC auto-tune), 1.5 `solver_agreement.py`, 1.6 `meep_bridge.py`.
- **Phase 2 — DONE.** 2.1 `device_templates/*.yaml` + `physics_templates.py`,
  2.2 `feasibility_gate.py` with the `check_design_feasibility` MCP tool.
- **Phase 3 — DONE.** Rule-based `review/` committee (physics, microwave,
  fabrication, measurement) + `auto_repair.py` bounded loop, exposed via the
  `review_layout` MCP tool. Committee score is the per-reviewer minimum, so any
  error stays below the 90 acceptance threshold.
- **Phases 4-6 — pending** (layout-understanding wiring, functional benchmarks,
  report/confidence/orchestration).

## Status legend

- **EXISTS** — already implemented and reusable as-is.
- **PARTIAL** — primitive exists; needs orchestration, policy, or extension.
- **NEW** — must be built.
- **DATA-GATED** — blocked on real reference data that cannot be fabricated.

---

## Phase 0 — Foundations already in place (no work, baseline)

These are reused by later phases and listed so the plan is grounded in reality.

| Capability | Module |
| --- | --- |
| EM solver registry + routing | `em_solvers.py` (`list_em_solvers`, `recommend_em_solver`, `get_em_solver`) |
| Solver comparison primitive | `em_extensions.py` (`compare_em_solvers`) |
| Open EM backends | openEMS (`research.py`), Palace (`palace_bridge.py`), Elmer (`elmer_bridge.py`), FastHenry/FastCap (`parasitics.py`), gmsh (`meshing.py`) |
| Circuit/RF backends | `adapters.py` (JosephsonCircuits.jl), `rf.py` (scikit-rf), `scqubits` via `research.py` |
| Feasibility physics | `physics_constraints.py` (`check_bode_fano`, `check_manley_rowe`, `check_kerr_limit`) |
| GDS → circuit graph | `verification.py` (`extract_circuit_from_gds`), `circuit_graph.py` |
| Similarity / novelty | `platform_extensions.py` (`similarity_search`), `quantum_dataset.py` (`find_similar`), `topology_search.py` (`novelty_score`) |
| Scientific report | `report.py` (`export_scientific_report`) |
| Readiness / quality scoring | `validation.py` (gated TRL), `quality_scorer.py` |

---

## Phase 1 — Open-solver-first architecture (Plan items 1–5)

Invert solver priority and add a unified manager + agreement engine.

### 1.1 Open Solver Manager — **NEW**
- **Target:** `src/text_to_gds/open_solver_manager.py`
- **What:** A `SolverManager` with `solve(device, target_accuracy="iteration"|"publication", sidecar=...)` that selects open backends by device class and accuracy target, runs them, and returns a unified result. Commercial backends are only invoked when explicitly requested as validation.
- **Device → backend policy (default open-first):**
  - CPW / resonator → openEMS + Palace
  - Capacitor / IDC → Elmer + FastCap
  - Inductor → FastHenry
  - JPA → openEMS + JosephsonCircuits.jl
  - Qubit → Palace + scqubits
- **Acceptance:**
  - `solve(device="CPW", target_accuracy="publication")` returns results from ≥2 open backends with a unified schema, no commercial dependency.
  - Commercial solvers never run unless `validation=True` is passed.
  - Unit test asserts the routing table and that absent backends report `skipped`, not error.

### 1.2 Priority inversion in routing — **PARTIAL**
- **Target:** `em_solvers.py` (`recommend_em_solver` ordering) + `server.py` tool docs.
- **What:** Reorder so open backends rank first for every device class; tag commercial entries `role: validation_only`.
- **Acceptance:** `recommend_em_solver` returns an open backend as rank 1 for CPW/JPA/qubit/cap/inductor; existing `test_em_solvers.py` updated to assert the new order.

### 1.3 Open HFSS-replacement pipeline — **PARTIAL → consolidate** (item 3)
- **Target:** thin wrapper in `open_solver_manager.py` over `meshing.py` → `palace_bridge.py`/`elmer_bridge.py`.
- **What:** `GDS → gmsh → {Palace eigenmode, Elmer capacitance}` emitting the **same schema as HFSS**: `{frequency, Q, participation, fields, convergence}`.
- **Acceptance:** Output dict keys match the documented HFSS schema; a golden test pins the schema (values may be `skipped` without solver binaries).

### 1.4 OpenQ3D module — **PARTIAL → consolidate** (item 4)
- **Target:** `OpenQ3D` class in `open_solver_manager.py` (or `parasitics.py`).
- **What:** Unified C-matrix / L-matrix / coupling / parasitic extraction over Elmer + FastCap + FastHenry. Includes an AI-driven IDC solver loop (adjust finger length/number/gap until `C = target ± 1%`) reusing `physics_extensions.optimize_idc_capacitor`.
- **Acceptance:** `OpenQ3D.extract(...)` returns `{C_matrix, L_matrix, coupling}`; the IDC loop converges to a target capacitance within tolerance on a deterministic surrogate, and uses FastCap/Elmer when installed.

### 1.5 Solver Agreement Engine — **PARTIAL → extend** (item 5)
- **Target:** `solver_agreement.py` (NEW) building on `em_extensions.compare_em_solvers`.
- **What:** Run ≥2 open solvers + the analytical model, compute pairwise relative error, and emit a **confidence score** with an explicit PASS threshold (e.g. frequency error < 5% ⇒ PASS).
- **Acceptance:** Given mock solver outputs (6.05 / 6.00 / 5.93 GHz) the engine returns a confidence value and PASS/FAIL deterministically; never reports high confidence from a single solver.

### 1.6 MEEP backend — **NEW** (field / photonics)
- **Target:** `meep_bridge.py` + registry entry in `em_solvers.py`.
- **What:** Optional FDTD field/photonics adapter following the existing adapter contract (runs when `meep` importable, else `skipped`).
- **Acceptance:** Registered in `list_em_solvers`; `skipped` with install hint when MEEP absent; smoke test for the generated input.

---

## Phase 2 — Physics-aware layout generation (Plan items 6–7)

Move from `Text → PCell → GDS` to
`Text → Specification → Circuit → Feasibility gate → Geometry → GDS`.

### 2.1 Device physics templates — **NEW** (item 6)
- **Target:** `physics_templates/` (YAML) + `physics_templates.py` loader.
- **What:** One `required_parameters.yaml` per device (CPW, Resonator, JPA, JTWPA, SFQ, Transmon) declaring `must_have` features, governing equations, and validity ranges.
- **Acceptance:** Loader validates a sidecar against a template and lists missing required features; CPW template requires signal conductor, ground planes, gap, ports, and an impedance check.

### 2.2 Pre-layout feasibility gate — **PARTIAL → orchestrate** (item 7)
- **Target:** `feasibility_gate.py` (NEW) wrapping `physics_constraints.py`.
- **What:** Before any GDS is generated, answer **"Can this exist?"** by running Bode-Fano, Manley-Rowe, Kerr, quantum-limit, and fabrication-limit checks against the request. Reject impossible specs with a reason.
- **Acceptance:** A request for "20 dB gain + 2 GHz bandwidth + single JPA" is rejected with a gain-bandwidth-violation message; a feasible request passes. Exposed as an MCP tool `check_design_feasibility`.

---

## Phase 3 — Rule-based AI review committee (Plan items 8–12)

Every generated layout must pass a committee of deterministic reviewers before
the platform accepts it. Replaces the dict-stub contracts in
`scientist_extensions.py` with real checkers.

- **Target:** `review/` package — `review/physics.py`, `review/microwave.py`,
  `review/fabrication.py`, `review/measurement.py`, `review/committee.py`.
- **Shared finding schema:** `{agent, severity: error|warning|info, finding, recommendation}` and a per-agent `passed: bool` + `score: 0–100`.

### 3.1 Physics Reviewer (item 8)
- **Checks:** topology sanity (via `extract_circuit_from_gds`), Hamiltonian validity, impedance realism, frequency match to target.
- **Acceptance:** Flags a CPW with no ground gap as FAILED ("cannot define Z0") with a regenerate recommendation; passes a valid CPW. Unit-tested on crafted good/bad sidecars.

### 3.2 Microwave Reviewer (item 9)
- **Checks:** S-parameter passivity (`|S11|² + |S21|² ≤ 1`), causality, reciprocity; ports, boundaries, modes, standing waves.
- **Acceptance:** Rejects a non-passive S-parameter set; accepts a passive one. Reuses the passivity logic already in the openEMS adapter.

### 3.3 Fabrication Reviewer (item 10)
- **Checks:** min width, spacing, alignment, junction area, via enclosure, airbridge distance (via `drc.py` + PDK rules). Emits a **tapeout-readiness score**.
- **Acceptance:** Score reflects DRC violations deterministically; a clean layout scores high, a min-width violation lowers it.

### 3.4 Measurement Reviewer (item 11)
- **Checks:** "Can this be measured?" — probe pads, wirebond pads, bias line, flux line, readout ports present in the sidecar.
- **Acceptance:** Flags a JPA missing a pump/flux port; passes a fully-padded device.

### 3.5 Committee + Auto-Repair Loop (item 12)
- **Target:** `review/committee.py` + `auto_repair.py`.
- **What:** Run all reviewers, aggregate to a single score, and loop
  `while score < 90: generate → simulate → review → fix`, applying bounded,
  known corrections (reuse `run_pyaedt_design_iteration`-style geometry edits,
  but solver-agnostic/open).
- **Acceptance:** A deliberately-broken CPW converges to score ≥ 90 within a
  bounded iteration budget; the loop terminates (no infinite loop) and records
  per-iteration findings. Never reports ≥90 while any reviewer has an `error`.

---

## Phase 4 — Layout understanding (Plan items 13–15)

### 4.1 Layout parser — **EXISTS → expose** (item 13)
- Reuse `extract_circuit_from_gds` / `circuit_graph.py`; ensure it detects
  CPW, JJ, SQUID, IDC, resonator and feeds the Physics Reviewer.
- **Acceptance:** Detected element list is asserted for each starter PCell.

### 4.2 Layout rule learning — **DATA-GATED** (item 14)
- Needs a `good_layouts/` corpus of real devices (IBM/MIT/Google/CAPP/NCU).
- **The platform will not fabricate reference layouts.** This item stays
  blocked until the user supplies licensed/permitted reference GDS. Until then,
  the reviewers use explicit hand-coded rules, not learned ones.
- **Acceptance (when unblocked):** A learned rule set reproduces the
  hand-coded reviewer verdicts on a held-out set.

### 4.3 GDS similarity search — **PARTIAL → wire** (item 15)
- Reuse `similarity_search` / `find_similar` / `novelty_score`; report
  similarity to the corpus and a novelty percentage in the final report.
- **Acceptance:** Returns ranked matches + novelty for a generated layout once a
  corpus exists; degrades to "no corpus" cleanly otherwise.

---

## Phase 5 — Benchmarks that prove function (Plan items 16–17)

### 5.1 Open benchmark suite — **PARTIAL → extend** (item 16)
- **Target:** `benchmarks/open/` + `tests/test_open_benchmarks.py`.
- **What:** Per-release, target-driven benchmarks:
  - `01_CPW`: Z0 = 50 Ω, f0 = 6 GHz → openEMS **and** Palace must agree.
  - `02_IDC`: C = 0.6 pF → Elmer/FastCap must agree.
  - `03_JPA`: Gain 20 dB, BW 500 MHz → JosephsonCircuits.jl must pass.
- **Acceptance:** Each benchmark asserts a physical quantity within tolerance via
  the Solver Agreement Engine, and `skips` (not fails) when a backend is absent.

### 5.2 Functional acceptance, not file existence (item 17)
- **What:** Tests must assert behaviour ("Z0 within 5% of 50 Ω"), never
  "the GDS file exists". Extends the golden-value pattern from
  `tests/test_review_coverage.py`.
- **Acceptance:** A grep audit shows no benchmark/test whose only assertion is
  file existence; CI gates on physical assertions.

---

## Phase 6 — Research report + confidence (Plan items 18–20)

### 6.1 Paper-quality report — **EXISTS → extend** (item 18)
- Extend `report.py` to emit the full figure set + `review_report.md`:
  `layout.png, field.png, mesh.png, S_parameter.png, gain.png, noise.png,
  bandwidth.png, uncertainty.png, review_report.md`.
- **Acceptance:** One call produces the figure set and a review report listing
  every agent's verdict and the solver-agreement confidence.

### 6.2 Confidence / research-readiness score — **PARTIAL → unify** (item 19)
- Combine reviewer scores + solver agreement + existing TRL into a single
  research-readiness number with a per-axis breakdown (Layout / Physics /
  Fabrication / Simulation / Measurement).
- **Acceptance:** A 6 GHz LJPA reports per-axis scores and an aggregate; the
  aggregate is gated (a failing axis caps the total), reusing `validation.py`'s
  gating rule.

### 6.3 Final orchestration — **NEW** (item 20)
- **Target:** `ai_scientist.py` (or extend `run_design_workflow`).
- **Flow:** `Prompt → feasibility gate → generate candidate → open EM solve →
  committee review → auto-repair → validated GDS + report`.
- **Acceptance:** End-to-end on "Design a 6 GHz JPA" yields a validated GDS, a
  report, and a readiness score — using **only** open solvers — or a clear
  rejection if infeasible.

---

## Dependency order (build sequence)

```
Phase 1 (solver manager + agreement)   <- enables real EM evidence
        |
Phase 2 (feasibility gate + templates)  <- cheap, can run in parallel with 1
        |
Phase 3 (review committee + repair)     <- needs Phase 1 evidence + Phase 2 templates
        |
Phase 4 (layout understanding)          <- feeds Phase 3 physics reviewer
        |
Phase 5 (functional benchmarks)         <- needs Phase 1 agreement engine
        |
Phase 6 (report + confidence + orchestration)  <- needs all above
```

## New / changed modules at a glance

| Module | Type | Phase |
| --- | --- | --- |
| `open_solver_manager.py` | NEW | 1 |
| `solver_agreement.py` | NEW | 1 |
| `meep_bridge.py` | NEW | 1 |
| `physics_templates/` + `physics_templates.py` | NEW | 2 |
| `feasibility_gate.py` | NEW | 2 |
| `review/{physics,microwave,fabrication,measurement,committee}.py` | NEW | 3 |
| `auto_repair.py` | NEW | 3 |
| `benchmarks/open/` + `tests/test_open_benchmarks.py` | NEW | 5 |
| `ai_scientist.py` | NEW | 6 |
| `em_solvers.py` (priority), `parasitics.py` (OpenQ3D), `report.py`, `validation.py`, `scientist_extensions.py` | CHANGED | 1/4/6 |

## Out of scope / risks

- **No fabricated reference data.** Items 14/15 stay data-gated until real,
  permitted reference layouts are supplied.
- **No commercial dependency on the critical path.** HFSS/Q3D/Sonnet remain
  optional validation only.
- **Solver binaries are environment-dependent.** Palace/Elmer/FastHenry/FastCap/
  MEEP run when installed and `skip` otherwise; CI asserts schema and routing,
  not solver numerics that require those binaries.
- **Reviewers are deterministic rules, not learned judgment.** They are only as
  good as their encoded rules; the roadmap treats them as a falsifiable gate,
  not an oracle.
