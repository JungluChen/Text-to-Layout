# Whole-Project Review — Text-to-Layout (clean-room pass, 2026-07-03)

Scope of this review: the entire repository at commit `6604b61`, read module by
module, with the goal of upgrading the project from a demo layout generator to a
credible research-grade text-to-layout system. Every claim below was checked
against committed code, not documentation.

---

## Current architecture summary

Two Python packages live under `src/`:

| Package | Role | Status |
|---|---|---|
| `src/textlayout` | **Main product path.** Clean architecture: prompt parser → typed DSL → deterministic geometry engine → verification → exporters → guarded simulation → evidence reports. | Active; all new work lands here. |
| `src/text_to_gds` | Legacy MCP server (80+ tools), superconducting-physics compiler, backend zoo. | Frozen legacy; excluded from ruff/mypy gates; not the expansion path. |

`textlayout` pipeline as of this review:

```
prompt.py            deterministic NL parser (no LLM) → DesignIntent
schemas/dsl/         pydantic v2 LayoutSpec + per-component specs
generators/          IDC, CPW, SpiralInductor, QuarterWaveResonator, SQUID → Geometry IR
geometry/engine.py   registry + technology + typed param validation
verification/        design-rule checks + artifact checks + inline KLayout readback
exporters/           GDS (gdsfactory), SVG, PNG, JSON
research/            per-component analytical models with references
optimization/        closed-loop analytical IDC tuning
simulation/          FasterCap / openEMS / FastHenry / JoSIM / PSCAN2 / WRspice
                     adapters with the prepare → execute → parse → compare lifecycle
evidence.py          QuantityEvidence — structurally enforced honesty contract
workflows/           GenerateWorkflow (DSL→artifacts), FromTextWorkflow (prompt→loop)
cli.py               textlayout prompt | generate | verify | serve
backend/             FastAPI plugin server
```

Entry points: `textlayout` CLI (`pyproject.toml [project.scripts]`), FastAPI app
(`textlayout.backend.app`), and importable workflows
(`build_from_text_workflow()`, `build_default_workflow()`).

## What is already good

- **The evidence contract is real.** `QuantityEvidence` enforces, in a pydantic
  validator, that `PHYSICS_VERIFIED` cannot be constructed without a named
  solver, a parser, existing non-empty solver-owned output files, and error ≤
  tolerance. This is the single most important property of the project and it
  is structural, not aspirational.
- **Deterministic core.** Parser is rule-based (raises `PromptParseError`
  instead of guessing); geometry generation is pure; GDS output is
  byte-reproducible (`gds2_write_timestamps=False`, canonical top-cell names).
- **Real solver lifecycle.** `run_fastercap()` persists command, return code,
  stdout, stderr, runtime, version banner, and a schema-complete
  `simulation_result.json` for every terminal status (skipped/failed/executed).
- **Honest status vocabulary** already in production:
  `ANALYTICAL_ONLY | SIMULATION_INPUT_PREPARED | SIMULATION_EXECUTED |
  PHYSICS_VERIFIED | FAILED | SKIPPED_SOLVER_ABSENT`.
- **Claim validation exists** (`scripts/validate_readme_claims.py` + committed
  test) and already fails CI on unsupported README claims.
- **224 textlayout tests green** at review time (794 repo-wide).

## What is still toy-level

1. **No orchestrated workflow graph.** `FromTextWorkflow.run()` is a 300-line
   monolith. There is no per-stage trace (`workflow_trace.json`), so a reviewer
   cannot see which stage produced/failed what without reading code.
2. **KLayout readback is a single inline pass/fail check** (top cell + bbox)
   buried in `GenerateWorkflow._with_artifact_checks`. No layer inventory, no
   polygon counts, no unit check, no `klayout_readback.json` artifact.
3. **No multi-device structures.** Only single components. A research chip
   needs an IDC + CPW measurement structure and a multi-device test tile with
   alignment marks and labels.
4. **Showcase is text-heavy.** `examples/benchmarks/` folders exist but the
   README does not present a text-to-cad-style example table with images and
   per-example step evidence.
5. **FasterCap is built (WSL, v6.0.7) but unreachable from Windows.**
   `_find_solver` finds the ELF binary and returns `None` on win32 instead of
   invoking it through `wsl`. Real execution is one path-translation away.
6. **`langgraph` was not a dependency** despite being the natural orchestrator
   for the staged pipeline.
7. **No `textlayout doctor`** environment check command.

## What blocks research-grade chip design

- No committed, regenerable six-example showcase with full per-example artifact
  chains (intent → DSL → GDS → readback → solver input → solver result →
  comparison → report).
- No workflow trace: reproducibility claims cannot be audited stage-by-stage.
- Readback verification too shallow to catch layer/unit mistakes.
- Multi-device tiles (the thing you actually put on a research mask) missing.

## What must be refactored

- `FromTextWorkflow.run()` → named stages orchestrated by a LangGraph
  `StateGraph`, with a typed state and per-node trace. Outputs must remain
  byte-compatible with the existing contract tests.
- FasterCap discovery/execution → WSL-aware on Windows.
- `validate_readme_claims.py` → additionally validate the showcase table and
  per-example artifact folders.

## What must not be touched

- `src/text_to_gds` (legacy; strangler boundary — do not expand).
- The `QuantityEvidence` honesty validator semantics.
- Committed benchmark artifacts under `examples/benchmarks/` (byte-reproducible).
- The `simulation_result.json` schema consumed by existing claim validation.

## Dependency status

| Dependency | Before this upgrade | After |
|---|---|---|
| `gdsfactory` | core dependency | unchanged |
| `klayout` | core dependency | unchanged |
| `langgraph` | **absent** | added as core dependency + import smoke test |
| FasterCap | built at `.tools/FasterCap` (WSL ELF, v6.0.7); undiscoverable on win32 | discoverable + executable through `wsl` |
| JoSIM | `.tools/josim/bin/josim-cli.exe`, ready | unchanged |
| openEMS / FastHenry / PSCAN2 / WRspice | absent or partial → honest `SKIPPED_SOLVER_ABSENT` | unchanged |

## Solver status (honest, machine-local)

- **FasterCap**: real executions possible (WSL). Only IDC-bearing examples can
  therefore reach `SIMULATION_EXECUTED` / `PHYSICS_VERIFIED`.
- **openEMS/FastHenry**: input preparation only → CPW, spiral, and resonator
  examples are `ANALYTICAL_ONLY` or `SIMULATION_INPUT_PREPARED`, never verified.
- **JoSIM**: circuit-level transient checks only; never accepted as geometry
  capacitance evidence (enforced in `simulation/base.py`).

## README honesty status

The README before this upgrade was already unusually honest (component support
matrix validated in CI, explicit status vocabulary, "not fabrication-ready by
default" statement). Weaknesses: no per-example showcase table with committed
artifacts, no workflow diagram, and presentation buried the evidence chain.

## Prioritized implementation plan (this upgrade)

1. Add `langgraph`, `textlayout doctor`, dependency smoke tests.
2. WSL-aware FasterCap execution on Windows (real solver runs).
3. LangGraph workflow: typed `LayoutWorkflowState`, 14 named nodes,
   `workflow_trace.json`; `textlayout prompt` uses it internally.
4. `verification/klayout_readback.py` → `klayout_readback.json` (top cell,
   bbox, layers, polygon counts, ports/labels, unit check).
5. New generators: `TestStructure` (IDC + CPW launches) and `TestChip`
   (2 mm × 2 mm tile with IDC, CPW, spiral, alignment marks, title label),
   with research models, DSL schemas, and prompt-parser support.
6. `scripts/generate_showcase_examples.py` → six committed examples under
   `examples/showcase/` + `index.json`.
7. README redesign: mermaid workflow, six-example table, evidence vocabulary.
8. Extend claim validation to the showcase; extend tests; run full gates.

Every stage keeps the standing rule: a layout candidate is **not
fabrication-ready** unless process-specific DRC, expert review, and measurement
planning are complete.
