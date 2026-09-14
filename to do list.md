# To do list

**Document class: MANUAL_DOCUMENTATION.** This is the ordered queue for the
daily Text-to-Layout improvement task. Scientific evidence remains authoritative
in the repository's generated evidence and retained solver artifacts.

## Daily operating agreement

- Run at 01:00 Asia/Taipei (UTC+8) on the local Mac, attached to the existing
  Codex conversation. Keep the Mac on and Codex running. Automation ID:
  `improve-text-to-layout-accuracy-first`; activated on 2026-09-15.
- Setup documentation commit: `4f87e766fc06bf8a46cdb10d7979cdbfddd0d414`.
  First scheduled-run verification remains pending; see the setup report.
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

### 1. Audit current numerical and reference-validation work

- **Status:** TODO; first scheduled run.
- **Acceptance:** Existing changes and unpublished commits reviewed in coherent
  groups; focused tests and full publication gates recorded; numerical and
  benchmark claims agree with regenerated evidence; only verified work pushed.
- **Evidence:** Initial local HEAD `c613767103178fe1437a34b70f1bec780ab89441`;
  initial remote HEAD `f4da3b5e2d1a0093fde132e8dc46c52b508376ee`;
  see `docs/progress/2026-09-15-setup.md`.
- **Next:** Inspect current status and the four initially unpublished commits
  (`0681852`, `f03918c`, `52ac988`, `c613767`), audit requirements/reference-GDS
  changes, establish a fresh test baseline, and follow reproduction policy for
  failures before editing. Recheck current SHAs; setup documentation may advance
  remote and local history before the first scheduled run.
- **Completion commits:** Pending.

### 2. Restore Palace integration with valid scientific evidence

- **Status:** TODO; failure localized in remote logs, not reproduced or fixed.
- **Acceptance:** Verified install, official smoke test, reduced CPW benchmark,
  real solver invocation, convergence and retained evidence all pass required
  checks; original failure is reproduced and repeated fix verification retained.
- **Evidence:** [Run 34824773767](https://github.com/JungluChen/Text-to-Layout/actions/runs/34824773767)
  at `f4da3b5`: installation and smoke succeeded, but the reduced CPW command
  returned `SKIPPED_SOLVER_ABSENT` and exit 1. Solver discovery/invocation is a
  diagnostic lead, not an established root cause.
- **Next:** Read the full run logs and compact artifact; compare smoke and
  resonator discovery paths, including unpublished commit `0681852`; reproduce
  the smallest faithful case twice before editing, then verify the full case.
- **Completion commits:** Pending.

### 3. Audit scientific correctness across simulation tools

- **Status:** TODO.
- **Acceptance:** Each supported path has traceable equations/data, unit and
  material checks, geometry/readback checks, parser regression cases, convergence
  evidence and justified accuracy criteria, with limitations explicitly recorded.
- **Evidence:** Collect from actual solver executions and primary references.
- **Next:** Inventory existing backends and rank gaps by their effect on numerical
  correctness; validate one bounded path at a time.
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
