# Architecture — textlayout (the supported product path)

Updated: 2026-07-02 (post branch-consolidation).
For the frozen legacy MCP package see [§ Legacy](#legacy-src-text_to_gds) below.
The root [`ARCHITECTURE.md`](../ARCHITECTURE.md) describes that legacy pipeline
and is historical.

## The one-minute map

```
src/textlayout/
  cli.py               CLI entry (`textlayout prompt|generate|verify|serve`) — thin, delegates to workflows
  backend/             FastAPI app factory, api_models (request/response schemas), settings
  prompt.py            deterministic NL → DesignIntent parser (no LLM, no API key)
  schemas/dsl/         the Layout DSL firewall: LayoutSpec envelope + one typed spec per component
  generators/          one module per component (idc.py, cpw.py, spiral.py, resonator.py, squid.py) + registry
  geometry/engine.py   DSL → Geometry IR (deterministic, AI-free)
  models/              domain entities: Geometry IR, Technology (frozen dataclasses, no pydantic)
  verification/        design-rule + geometry checks → VerificationReport (exact polygon clearance DRC)
  research/            cited analytical models per component (Bahl, Simons, Mohan …) → ResearchReport
  optimization/        closed-loop analytical tuners, per component (idc.py)
  evidence.py          THE evidence contract: QuantityEvidence + EvidenceStatus (single source of truth)
  simulation/          solver adapters: input prep (open_source.py, fastercap.py), execution+parsing
                       (runners.py, fastercap.py), SimulationResult (models.py),
                       evidence_map.py = the only SimulationResult → QuantityEvidence mapping
  workflows/           use-cases: generate.py (DSL → artifacts), from_text.py (prompt → 8-file closed loop)
  exporters/           GDS (gdsfactory + canonicalize_gds), SVG, PNG, JSON
  knowledge/           technology/PDK library (data, not logic)
  acceptance.py        physics-fit acceptance packets (feasible / infeasible / auto-size)
  ports/               abstract interfaces (Generator, Exporter) for the plugin system
tests/textlayout_suite/   mirrors the concerns above, one test module per feature
scripts/                  validate_readme_claims.py (CI gate), generate_benchmarks.py (deterministic),
                          check_benchmarks.py, generate_acceptance.py, bundle_plugin.py
examples/benchmarks/      committed, byte-reproducible benchmark packets
examples/acceptance/      committed physics-fit acceptance packets
docs/                     this file, AUDIT_REPORT, PROGRESS, BRANCH_INVENTORY, artifact_policy, …
```

Dependency rule (inward only):

```
cli / backend / scripts          (drivers)
        ↓
workflows                        (use-cases; also acceptance.py)
        ↓
prompt · optimization · research · simulation · verification · exporters
        ↓
schemas/dsl · geometry · models · knowledge · evidence   (core; no outward imports)
```

Three invariants the layout of the code enforces:

1. **The DSL is the AI firewall.** Anything above `schemas/dsl` may be driven
   by an agent; everything below is deterministic. Generators never see raw
   text; the parser never draws geometry.
2. **`evidence.py` is the only place a physics claim can be minted.**
   `simulation/evidence_map.py` is the only bridge from solver records to
   claims; `SimulationResult.target_comparison` (built by the one shared
   `models.target_comparison()` helper) is raw data, never a claim.
3. **Failed verification never exports.** `workflows/generate.py` returns
   diagnostics without writing final artifacts.

## How to add a new generator (the walkthrough)

Support levels (must match the README component support matrix — CI enforces it
via `scripts/validate_readme_claims.py`):

- **A — Supported:** everything below exists.
- **B — Experimental:** partial implementation; README row says experimental
  and states the limitation.
- **C — Not supported:** no README claim at all.

To add component `Foo` at level A, create/edit exactly these files:

1. `src/textlayout/schemas/dsl/foo.py` — a frozen pydantic `FooSpec`
   (`extra="forbid"`, `gt=0` bounds). This is the typed firewall; copy the
   shape of `idc.py`.
2. `src/textlayout/generators/foo.py` — `FooGenerator` implementing the
   `Generator` port (`ports/generator.py`): validate `spec.parameters` against
   `FooSpec`, emit `Geometry` (polygons + ports). Copy `cpw.py`.
3. Register it in **both** places:
   - `pyproject.toml` → `[project.entry-points."textlayout.generators"]`
     (`Foo = "textlayout.generators.foo:FooGenerator"`), and
   - the builtin fallback in `src/textlayout/generators/registry.py`
     (keeps tests working without reinstall).
4. `src/textlayout/research/foo_research.py` — cited analytical model +
   `ResearchReport` (equations, references, limitations). Wire it in
   `research/engine.py`. Without this the workflow fails the
   `research_evidence` check — that is intentional.
5. Verification: the generic checks in `verification/checks.py` apply
   automatically; add component-specific checks there only if the generic set
   cannot express a rule.
6. (Optional, level A closed loop) `src/textlayout/optimization/foo.py` tuner
   and a `simulation/` input-prep function; route it in
   `simulation/engine.py::simulate_layout`.
7. Tests in `tests/textlayout_suite/test_foo_generator.py`: valid build,
   invalid parameters rejected, verification pass/fail, golden DSL if the
   geometry is deterministic.
8. Example + benchmark folder `examples/benchmarks/NN_foo_*/` with `prompt.md`
   and `layout.json`; run `scripts/generate_benchmarks.py` to produce the
   committed artifacts (deterministic; see `docs/artifact_policy.md`).
9. Add the README support-matrix row at the honest level, then run
   `uv run python scripts/validate_readme_claims.py` — it fails the build if
   any cell overclaims (and `scripts/validate_readme_claims.py::COMPONENTS`
   needs the new component's file map).

A reviewer should be able to predict every path above from this list alone —
if a step surprises you, fix this document in the same PR.

## Prompt → artifacts closed loop (IDC reference flow)

```
textlayout prompt "…"          POST /layout/from-text
        └─ prompt.parse_prompt → intent.json
           optimization.optimize_idc → optimization.json     (ANALYTICAL_ONLY by construction)
           LayoutSpec → layout.json
           GenerateWorkflow → output.gds / output.svg / verification.json
           simulation prep (+ guarded solver run) → simulation.json (QuantityEvidence)
           report.md — states exactly one status:
             SKIPPED_SOLVER_ABSENT | SIMULATION_INPUT_PREPARED | SIMULATION_EXECUTED |
             PHYSICS_VERIFIED | FAILED | ANALYTICAL_ONLY
```

`QuantityEvidence` makes `PHYSICS_VERIFIED` unconstructible without a named
solver + parser, an existing non-empty solver-owned output file, and error ≤
tolerance (`tests/textlayout_suite/test_evidence_contract.py`).

## Legacy: `src/text_to_gds`

The original MCP-server package (~80 `@mcp.tool()` functions, nine solver
backends). **Frozen**: it is kept working as the MCP surface (`text-to-gds`
console script, `.mcp.json`, `plugins/text-to-gds` bundle) but receives no new
features — its `__init__.py` carries the freeze notice. It intentionally stays
at `src/text_to_gds` rather than moving to a `legacy/` directory: the import
path is load-bearing for the MCP stdio server, five console scripts, and ~60
test modules, and a physical move would be pure churn with regression risk.
Dead-code removal inside it is a separate, explicitly-scoped follow-up (see
`docs/PROGRESS.md` backlog).

## Naming conventions

- Modules are `snake_case`, named for their concern (`gds_exporter.py`,
  `evidence_map.py`) — no `utils.py`.
- One component ↔ one module name across layers: `idc.py` appears in
  `schemas/dsl/`, `generators/`, `optimization/`; `idc_research.py` in
  `research/`. A new component should follow the same rhyme.
- Schema versions are strings like `textlayout.simulation-result.v1`; bump the
  suffix on breaking change.
