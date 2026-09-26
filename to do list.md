# To do list

**Document class: MANUAL_DOCUMENTATION.** This is the ordered queue for the
daily Text-to-Layout improvement task. Scientific evidence remains authoritative
in the repository's generated evidence and retained solver artifacts.

## Daily operating agreement

- Run at 01:00 Asia/Taipei (UTC+8) on the local Mac, attached to the existing
  Codex conversation. Keep the Mac on and Codex running. Automation ID:
  `improve-text-to-layout-accuracy-first`; activated on 2026-09-15.
- Setup documentation commit: `4f87e766fc06bf8a46cdb10d7979cdbfddd0d414`.
  First attempt was usage-blocked; resumed audit/reporting is recorded in
  `docs/progress/2026-09-15-051619.md`. The schedule was verified and restored
  to 01:00 Taipei during that continuation.
- Read `AGENTS.md`, `docs/development/reproduce_before_edit.md`, this list,
  previous `docs/progress/` reports, and current Git/CI state before working.
- Read `REQUIREMENTS.md` and `Design.md` for the approved product surfaces and
  Apple Design Skill-based UI/UX brief. Keep `docs/function-catalog.md` and
  `docs/guidebook/README.md` current with each delivered capability. Guidebook
  steps need real screenshots, numbered pointers, CLI commands and AI/MCP
  examples before they can be marked complete.
- Design/requirements brief and initial catalog/guidebook delivered in
  `df9ff2b5dc37db8985207e7c7b839d42987c8991`; UI implementation and illustrated
  release walkthroughs remain pending. See the design-requirements progress report.
- Work top to bottom. Numerical/data correctness takes priority over features.
  If blocked, record the evidence and exact next action before continuing to
  the next actionable item. Split large milestones into verifiable increments.
- Inspect ongoing local work, solver processes and CI jobs first. Resume or
  monitor existing jobs; do not duplicate jobs or terminate unrelated work.
  The current item may exceed an hour, subject to actual execution/usage limits.
- First audit the existing uncommitted work and unpublished commits. Preserve
  unfinished work and concurrent edits. Do not stage the whole tree blindly.
- Follow REPRODUCE -> RERUN UNCHANGED -> DIAGNOSE -> EDIT -> RERUN ORIGINAL
  COMMAND -> RERUN AGAIN -> REGRESSION. Investigate inconsistent runs first.
- Retain sources, assumptions, units, materials, geometry, solver versions,
  input/output hashes, logs, convergence and comparison errors. Set justified
  tolerances before evaluation. Do not weaken gates or fabricate evidence.
- Before publishing code, run `uv run pytest`, `uv run ruff check .`,
  `uv run mypy`, `uv build`, and applicable existing CI claim/evidence gates.
  Generate status documents using their prescribed generators. Keep skipped,
  failed, blocked and untested checks distinct from passes.
- Review the diff, commit verified portions with detailed messages, and push
  directly to `origin/main`. Fetch/reconcile concurrent upstream work safely;
  never force-push or discard edits. Inspect CI for the exact pushed SHA.
- Before stopping or exhausting context/usage, save exact resume commands,
  blockers, evidence and active job IDs. Publish a substantive documentation
  checkpoint when code is not ready. Record push failures explicitly.
- Save a dated report under `docs/progress/` and return a detailed result after
  every run. Use `docs/progress/README.md` as the report contract.
- Completed items need their implementation commit hashes, recorded in a
  subsequent documentation commit. No commit refers to its own hash. A push
  with pending CI does not establish completion.

## Ordered queue

### Priority 0. Whole-project Quantum/RF EDA integration architecture

- **Status:** IN PROGRESS as the first task in this queue (added 2026-09-25).
  The revised 100-target mission supersedes the 50-target list as a roadmap,
  not evidence that these tools are
  installed, open source, supported or numerically validated. Existing item
  numbers are retained so historical reports and commit references remain
  intelligible. Palace run `36148860525` has now failed at the bounded AMR
  element guard; retain its uploaded diagnostic evidence under item 2.
- **Objective:** Evolve the deterministic `textlayout` core into a modular
  Quantum/RF EDA compilation and simulation platform. Parsers/LLMs emit typed
  Pydantic v2 DSL; pure Python and supported geometry libraries generate
  reproducible geometry. Adapters consume that core rather than embedding
  loose external scripts under `src/`. Native solvers stay outside Git under
  `.tools/` or a user cache, with idempotent pinned/hash-verified setup and
  `textlayout doctor` probes. Preserve the existing evidence contract:
  prepared inputs, actual execution, parsed outputs, convergence and
  fabrication readiness remain distinct; reconcile the pasted status names
  with `src/textlayout/evidence/contract.py` before changing any schema.
- **Ten integration pillars / candidate target slots:** The exact numbered
  names and user-supplied source hints are retained in
  `src/textlayout/integrations/targets.json`; none is a verified upstream or
  license claim yet.

  | Pillar | Candidate projects and bounded purpose |
  | --- | --- |
  | Quantum chip EDA and layout | 1–10: device libraries, circuit quantization, field-to-Hamiltonian and calibration bridges. |
  | 2.5D/3D EM and multiphysics | 11–20: FEM, FDTD, BEM and PDE solvers with tagged geometry and convergence. |
  | RF analysis and synthesis | 21–30: Touchstone, de-embedding, transmission lines and matching. |
  | Geometry and meshing | 31–40: deterministic GDS, polygons, CAD, mesh and DRC. |
  | Superconducting/SPICE | 41–50: Josephson/RSFQ netlists, transient solvers and cryogenic models. |
  | Analog and mixed-signal | 51–60: general SPICE, Verilog-A and schematic interfaces. |
  | Physical design and signoff | 61–70: routing, DRC/LVS and mixed quantum/CMOS integration. |
  | AI placement and automation | 71–80: placement, routing and optimization with deterministic checks. |
  | Commercial interoperability | 81–90: optional licensed export and execution bridges, never assumed present. |
  | Visualization and audit | 91–100: 3D fields, mesh formats, charts, terminal reports and workflow traces. |

- **Acceptance criteria:** Inventory each target's canonical source, license,
  maintenance state, platform, version/hash, dependency cost, existing code,
  physical quantities, units, input/output contract, numerical limitations and
  test evidence. Resolve duplicate/ambiguous target names before treating the
  “100” as 100 distinct installable open-source tools. In particular, the
  commercial bridge pillar cannot be treated as open-source solver access.
  Specify a typed adapter
  protocol and registry under `src/textlayout/integrations/` and, where useful,
  `src/textlayout/simulation/backends/`; avoid duplicating current adapters.
  Add optional `quantum`, `mesh`, `rf`, `spice`, `fem`, `vlsi`, `commercial`,
  `ai` and `all` groups only with
  compatible pinned dependencies and a lean passing base install. Extend
  `textlayout doctor` with truthful FOUND/MISSING/BROKEN and version/path/hash
  checks. Every runner records solver provenance, inputs, outputs and
  convergence in the existing canonical evidence schema before promotion.
  Deliver one solver/CLI/benchmark slice at a time, with real fallback tests,
  platform checks, guidebook examples and accepted scientific references.
- **Current evidence:** The first scaffold retains exactly 100 requested
  candidate slots across ten pillars (60 supplied source hints, 40 without),
  and `doctor --json` attaches only eight one-to-one pre-existing probes.
  It marks the other 92 NOT_PROBED and every source/license unverified.
  Proposed optional groups now cover existing, already locked Python packages;
  empty native/commercial groups explicitly install no solver. The base
  dependency set is unchanged, but making it genuinely lean/headless needs a
  separate compatibility migration. Existing Palace/openEMS/FasterCap/
  FastHenry/JoSIM adapters have not been moved or certified by this scaffold.
  The existing `SolverAdapter` protocol is the starting boundary, as recorded
  in `docs/architecture/integrations.md`; a new registry and `simulation.json`
  parity remain pending. The Touchstone parser correction under item 3 is a bounded RF
  accuracy increment. This inventory slice was implemented in
  `10fc549f44e201165e278c6d50a2c0395955e5a9`; its exact-SHA CI is
  recorded in `docs/progress/2026-09-26-085000.md`.
- **Next:** (1) Audit and deduplicate all 100 target slots, including license
  and commercial dependencies; rank by scientific impact and feasibility.
  The first four source/scope reviews are recorded in
  `docs/architecture/integration-source-audit.md`: SQcircuit's hint points
  away from its maintainer repository, QEDA's hint resolves to a PCB tool,
  and current Quantum Metal packaging differs from the locked legacy name.
  Do not migrate the optional package until import/platform compatibility is
  tested.
  (2) Map existing adapters/evidence schemas to a minimal plugin contract and
  write an architecture decision before new scaffolding. (3) Add an optional
  dependency/doctor/adapter slice with full tests and actual solver evidence.
  (4) Expand `textlayout simulate` and later `textlayout quantum characterize`
  only for implemented, validated backends. Keep existing item 2's Palace job
  and item 3's numerical audit active rather than replacing them with claims.
- **Completion commits:** Pending; record implementation hashes in a later
  documentation commit.

### 1. Audit current numerical and reference-validation work

- **Status:** COMPLETE for the audited work at `99d8d06`; code and retained evidence published, exact-SHA CI passed.
- **Acceptance:** Existing changes and unpublished commits reviewed in coherent
  groups; focused tests and full publication gates recorded; numerical and
  benchmark claims agree with regenerated evidence; only verified work pushed.
- **Evidence:** Initial local HEAD `c613767103178fe1437a34b70f1bec780ab89441`;
  initial remote HEAD `f4da3b5e2d1a0093fde132e8dc46c52b508376ee`;
  see `docs/progress/2026-09-15-setup.md`.
- **Current evidence:** `docs/progress/2026-09-15-051619.md`; fresh full suite
  1,960 passed/11 skipped, repeated 64-case numerical grid, 16 real FastHenry
  cases and four reference masks. Requirements report consistency and OCI
  evidence classification were corrected with reproduced failure evidence.
- **Next:** Continue with item 2. Both CI workflows passed on
  `99d8d06474b5c5e9e0dfd222c8fe1ba3f92d0a0b`, including all six platform/Python
  matrix jobs. Inspect any later documentation-commit CI separately. Actual unpublished
  source commits reviewed were `f03918c`, `52ac988`, `c613767`; the setup's
  `0681852` pointer is absent from current local history.
- **Implementation commits:** `d1061bce7827c55fe5083bf2d83adc37dab510a0`,
  `5f114b2039cdb1f2f37056d44eb0e4426891cb56`,
  `fa6a31af51374bf2dc051061d261c527ce3a6268`.
  Evidence/report commit: `99d8d06474b5c5e9e0dfd222c8fe1ba3f92d0a0b`.

### 2. Restore Palace integration with valid scientific evidence

- **Status:** IN PROGRESS; native-record discovery defect reproduced twice and
  fixed on an isolated candidate branch. Real solver validation pending;
  no candidate code promoted to main yet.
- **Acceptance:** Verified install, official smoke test, reduced CPW benchmark,
  real solver invocation, convergence and retained evidence all pass required
  checks; original failure is reproduced and repeated fix verification retained.
- **Evidence:** [Run 34824773767](https://github.com/JungluChen/Text-to-Layout/actions/runs/34824773767)
  at `f4da3b5`: installation and smoke succeeded, but the reduced CPW command
  returned `SKIPPED_SOLVER_ABSENT` and exit 1. Solver discovery/invocation is a
  diagnostic lead, not an established root cause.
- **Next:** Existing failure logs and artifact `10342591878` are retained under
  `docs/progress/evidence/2026-09-15-051619/palace-existing-failure/`. The official
  smoke command uses the native Spack executable from the install record, but
  `detect_palace` only consumes recorded paths with the `wsl:` prefix in the
  current main implementation. Candidate `8705804045700d4b2bd87bd1d8e4c79839fd955d`
  on `codex/palace-native-discovery-20260915` passes both original discovery
  reproductions, nine new regression cases and the full 1,969-test suite
  (11 skipped). See `docs/progress/2026-09-15-132123.md`.
  Candidate CI `34932724963` passed. Palace attempt 1 (job `104264198805`)
  passed install/smoke but the runner shut down during the reduced benchmark
  (exit 143); no compact artifacts were uploaded. The cause is not established.
  Unchanged attempt 2 also lost its runner during the reduced benchmark and
  retained zero artifacts. Collection fix `034fc15` now checkpoints installation
  and smoke evidence before the long step. Candidate `494a51a` combines that
  collection fix with the still-isolated discovery fix. Run `35915053169` verified
  the early checkpoint (artifact `10778525629`, retained smoke hashes verified),
  then again lost the runner during the reduced benchmark. Do not repeat blindly:
  add measured in-run resource/log diagnostics without changing numerical settings.
  Runtime observer `4dfc1f2` samples bounded memory/process/solver-log
  diagnostics without changing solver behavior. Candidate run `36032456522`,
  job `107744315010`, again lost its runner during the reduced benchmark;
  GitHub returned `404 BlobNotFound` for its log, so the stream is unavailable.
  Its pre-benchmark artifact `10826536844` retains verified install/smoke
  evidence only. See the September 25 report and hashed artifact packet.
  Observer Windows fixture correction `6bd7e6f` passed actual main Windows
  3.11/3.12 CI; candidate head `303d909` also passed full platform CI.
  Documentation commit `2ca1c73` exposed an invalid XML 2.2 declaration in
  the compacted real Palace field fixture on Ubuntu/Python 3.11; its failed
  job reproduced unchanged. Correction `33bb90d` changes only the XML
  declarations, repairs all fixture provenance hashes and passes full local
  gates. Exact-SHA CI `36145914485` and test `36145914291` subsequently
  passed, including Ubuntu/Python 3.11; see September 25 report.
  Candidate work after `64c9abe` adds hash-checked base-mesh resume and a
  separate bounded diagnostic before the full AMR solve, preserving the final
  benchmark's numerical settings. Three focused resume safety cases and the
  1,979-pass candidate suite passed locally; exact-SHA CI `36148281544` passed
  the six-platform-version matrix and quality jobs. Palace run `36148860525`
  (job `108116750266`) completed **failed** on candidate SHA `2b88360`.
  Install, official smoke, base mesh and the bounded Palace process completed.
  Its base mesh had 106,439 elements and the real AMR output reached 434,227,
  exceeding the predeclared 200,000-element guard. The artifact reports
  `SIMULATION_INVALID`; full benchmark, convergence and reference error were
  skipped. The diagnostic artifact is `10873339434`; installation/smoke and
  mesh artifacts are `10873587680`, `10874010399` and `10873636070`. Retain
  the 200,000 guard while diagnosing mesh sizing/refinement and memory from
  these solver-owned outputs. Reproduce an appropriately bounded case twice
  before a focused candidate change; do not promote discovery/resume to main
  on this failure. See the next dated progress report.
  The unchanged [attempt 2](https://github.com/JungluChen/Text-to-Layout/actions/runs/36148860525)
  at the same SHA and Palace executable hash reproduced the same 434,227 / 200,000
  invalid verdict, identical base mesh and eigenvalue hashes; its compact
  evidence is in `docs/progress/evidence/2026-09-26-141550/palace-attempt2/`.
  Candidate `f407c63` changes only the bounded diagnostic AMR marking fraction
  from 0.7 to 0.1 while preserving the guard and full benchmark settings.
  This is an unverified resource experiment. Real Palace run `36223218053`,
  job `108352252265`, is active at that SHA; inspect its actual artifacts,
  rerun unchanged if it passes, then require full benchmark/convergence/reference
  evidence before merging. See `docs/progress/2026-09-26-141550.md`.
  Windows CI `35915634148` and `35933303913` both passed unchanged second
  attempts; their first-attempt timing failures remain unexplained, not fixed by
  relaxed waits. See `docs/progress/2026-09-25-010046.md` for exact continuation.
  Require real reduced-benchmark execution, repeated verification, convergence
  and valid evidence before promotion. Do not dispatch a duplicate.
- **Completion commits:** Pending.

### 3. Audit scientific correctness across simulation tools

- **Status:** IN PROGRESS. The first bounded audit corrected the optional
  Touchstone fallback parser used for openEMS S-parameter results; the broader
  cross-solver audit remains open.
- **Acceptance:** Each supported path has traceable equations/data, unit and
  material checks, geometry/readback checks, parser regression cases, convergence
  evidence and justified accuracy criteria, with limitations explicitly recorded.
- **Evidence:** IBIS Touchstone 2.1 specifies complete 1-/2-port Version 1.x
  rows, strictly increasing frequency and GHz/S/MA/50-ohm defaults. Repeated
  unchanged tests showed the prior fallback accepted a truncated `.s2p`, read
  Z-parameters as S-parameters, accepted reversed sweeps and treated a bare `#`
  as Hz/RI. The correction and retained test/gate record are in the September
  25 parser progress report. Example openEMS files were classified; no new
  solver execution or reference accuracy result is claimed.
- **Next:** Verify the parser correction on the Windows/macOS/Linux CI matrix,
  then inventory remaining backend equations, units, materials, geometry,
  parser and convergence gaps by potential numerical impact. Diagnose Palace
  run `36148860525` under item 2 from its uploaded artifacts before any rerun.
- **Completion commits:** Pending.

### 4. Expand independent reproducible comparisons

- **Status:** TODO; public references only initially.
- **Acceptance:** Reproducible cases match reference geometry, materials,
  boundary/port conditions and quantities; report tolerances and measured errors.
  Analytical reproduction and independent solver comparison remain distinct.
- **Evidence:** Primary papers, published benchmark data and real open-source
  solver outputs. Direct commercial comparisons without matching data are pending.
- **Next:** Select the first matching public case for a validated backend and
  document its protocol before execution.
- **Completion commits:** Pending.

### 5. Verify Windows, macOS and Linux software delivery

- **Status:** TODO; no new platform certification from this setup.
- **Acceptance:** Install/build and representative CLI/API/desktop workflows
  execute on each claimed platform; packaging and solver dependencies are
  documented; missing native/WSL evidence remains explicit. Follow `Design.md`
  and `REQUIREMENTS.md`; deliver Windows/macOS/Linux software and CLI with
  matching illustrated setup and first-design walkthroughs.
- **Evidence:** Existing GitHub Actions platform matrix plus actual platform runs.
- **Next:** Inventory current packaging and platform evidence, then specify and
  validate the smallest missing delivery milestone.
- **Completion commits:** Pending.

### 6. Develop browser access with local and hosted solver options

- **Status:** TODO; future product milestone.
- **Acceptance:** A shared browser interface supports a local solver service and
  later a hosted service with verified end-to-end job, result and error handling.
  Use the Apple Design Skill-based brief, searchable function catalog and
  illustrated guidebook; verify keyboard, light/dark, compact-width and failure
  flows with actual captures from each claimed surface.
- **Evidence:** Record API/UI checks and real simulation execution separately.
- **Next:** Audit existing browser/API/job interfaces and write the first bounded
  implementation specification. Hosted services are user-authorized roadmap work;
  no paid infrastructure or deployment credentials are assumed.
- **Completion commits:** Pending.

### 7. Expand HFSS/Keysight-comparable capabilities

- **Status:** TODO; no universal feature or accuracy parity claimed.
- **Acceptance:** Each capability has a concrete specification, an open-source or
  paper-based implementation, a reproducible benchmark and explicit limitations.
- **Evidence:** Primary sources and matching public comparison results; unavailable
  commercial reference evidence stays pending.
- **Next:** Build a capability-gap inventory after the accuracy foundation is
  validated, then implement and validate one prioritized capability at a time.
- **Completion commits:** Pending.

### 8. Deliver MCP and Codex / Claude Code plugin workflows

- **Status:** TODO; current legacy MCP inventory and manifests documented,
  host behavior and modern capability parity not certified.
- **Acceptance:** Typed discoverable MCP tools use the shared core; existing
  compatibility is preserved; both plugin hosts install, discover tools and
  complete bounded workflows with truthful artifacts/status and recovery.
  Function catalog lists real names, inputs/units, defaults, outputs,
  prerequisites, effects, errors and CLI/AI examples.
- **Evidence:** `docs/function-catalog.md` inventories 95 legacy MCP functions
  by static source inspection. Runtime schemas and host transcripts are pending.
- **Next:** Audit current stdio discovery and host launch configuration, then
  specify a bounded modern MCP adapter without adding product logic to the
  frozen legacy implementation. Regenerate thin bundles using their script.
- **Completion commits:** Pending.

### 9. Complete and maintain the illustrated guidebook

- **Status:** STARTED: source-grounded guidebook scaffold; real GUI and host
  screenshots/annotated walkthroughs still pending.
- **Acceptance:** Every supported CLI, desktop, browser, MCP and plugin path has
  step-by-step instructions, actual screenshots with numbered arrows/pointers,
  accessible text, runnable command lines, schema-valid tool examples and AI
  prompts. Captures record platform/version/commit and expected results; no
  unsupported interface is described as available.
- **Evidence:** `docs/guidebook/README.md`; use its capture matrix and metadata
  requirements. Historical artifact illustrations are not new UI screenshots.
- **Next:** Complete each chapter with its corresponding feature, not only after
  all features ship. Add real installation, first design, missing-solver,
  results/evidence and export captures; validate commands and both plugin hosts.
- **Completion commits:** Pending.
