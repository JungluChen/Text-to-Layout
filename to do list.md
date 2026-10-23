# To do list

**Document class: MANUAL_DOCUMENTATION.** This is the ordered queue for the
daily Text-to-Layout improvement task. Scientific evidence remains authoritative
in the repository's generated evidence and retained solver artifacts.

## Highest user-directed priority — complete the integration checklist (2026-10-03)

Work on `docs/integrations/checklist.md` before native app, landing-page or
release expansion. Begin at 001 and satisfy source/license, typed adapter,
real execution, reference and platform evidence before checking a box. If a
candidate is blocked or unidentifiable, record the specific missing evidence
and continue the next actionable entry; never count an audit as completion.
Entry **001 KQCircuits** is accepted for straight CPW gap-mask generation only,
implementation c6f023e9f69d7e353baa7b46ecc9694829c8ce51. Actual typed CLI runs
passed twice on each of Linux, Windows and macOS (37138947989); all 18 retained
GDS outputs were independently checked after download. No EM/full-toolkit claim.
See docs/progress/2026-10-04-010007.md. Entry **002 Quantum Metal** now has
scoped positive charge-pad/ground-pocket mask acceptance, implementation
dde9fcf56c84972fab804678272ed0f1a886062a. Both input cases passed twice on
macOS, Windows and Linux (37172852770); all twelve downloaded GDS packets
were independently checked. No fabrication-junction or electrical claim.
Entry **003 pyEPR** is accepted for specified ideal one-mode full-cosine circuit
execution only, implementation 4cd88ee4390d9f1353fdcca5dd036e1ef1acbba2.
Two cases passed twice on each of macOS, Windows and Linux (37187701164);
all 12 packets independently checked. Fixed convergence/reference limits pass;
no HFSS/EM or measurement claim. Exact-SHA CI 37187636083 and test 37187636081
passed. See docs/progress/2026-10-04-160007.md.
Entry **004 CircuitQ** is accepted for specified ideal parallel-LC execution,
implementation 0cc02e3b9b3639b38a3ef5046db7d352b550ab7f. Both cases passed twice
on Windows/macOS/Linux (37322754080), all twelve packets independently checked.
Fixed residual, matrix-equivalence, domain/grid and exact-reference gates pass;
no nonlinear/noise, EM or measurement claim. CI 37322701518 and test 37322701485
passed. See docs/progress/2026-10-05-220929.md.
Entry **005 scqubits** is accepted for two fixed ideal ng=0 transmon cases,
implementation 577471cd62e616facafbdea4a2e81e07a0c253e3. Dedicated run
38032886016 passed repeated cutoff/reference/residual checks on all three OSs;
six packets and 36 typed adapter calls independently verified. Exact CI/test
38032885443/38032885403 passed. No noise, EM or measurement claim.
See docs/progress/2026-10-10-150004.md. Historical item: **006 SQcircuit** — audit source,
license, version, dependencies and existing adapter before defining acceptance.
Source/license audit and repeated local LC probes retained in
`docs/progress/2026-10-10-211726.md`. Default inductor adds 1e-20 F; original
ideal-LC reference failed. Explicit capacitance semantics, deterministic
execution policy, typed adapter and three-platform evidence remain pending.
Follow-up 2026-10-11-031011: explicit Cbranch plus public Hamiltonian/dense
diagonalization passes repeated local LC checks; stable SymPy 1.14.0 tested.
Native eigs randomness traced to OS-seeded rng. Typed adapter and platform
verification remain the next implementation slice.
A typed prepared-only SQcircuit LC API now requires explicit Cbranch and writes
a bounded hashed plan without importing or executing a solver. Execution, CLI,
canonical numerical evidence and three-platform verification remain pending.
The isolated raw worker now retains real SQcircuit Hamiltonians/eigenpairs;
local unchanged outputs match. Canonical assessment and the product execution
wrapper are next; raw NOT_EVALUATED output does not complete entry 006.
Raw eigenpair assessment is now implemented with malformed/corrupted-packet
rejection. Product process/identity verification and canonical result conversion
remain next; no checklist promotion from the assessment alone.
Typed product execution now verifies packet identity, retains failures/timeouts
and emits canonical frequency evidence only after fixed numerical checks pass.
Two local LC cases passed twice with byte-identical raw pairs; see
`docs/progress/2026-10-12-102833.md`. Next: CLI and dedicated repeated
Windows/macOS/Linux benchmark evidence; entry 006 remains unchecked.
Windows lifecycle CI 37208006683 had late successful finalization and passed
unchanged on attempt 2; preserve evidence, investigate timing before any fix.
Recurrence 38148751846 on 5419cda: Windows 3.11 observed running at the
15-second wait; retained job finalized successfully about 16 seconds after start.
Unchanged failed-job retry passed. See docs/progress/2026-10-12-042554.md;
phase-level Windows timing remains required before changing lifecycle behavior.
Recurrence on db75ddd/c383c02: Windows 3.11 lifecycle wait failed again;
c383c02 unchanged failed-job repeat passed (38197649575 attempt 2). Retained
16-second finalization evidence and phase-timing next steps:
`docs/progress/2026-10-12-161614.md`. No lifecycle fix or tolerance change.


## Current human-directed release priority — v0.3.1

Finish the five-item Python MVP before the broader integration backlog below.
Implemented commits: scqubits `3799d8d`, analytical CPW selection `a6f0406`,
pinned reference contract/CLI `fba30db`, four-example promotion `b0fab5b`.
Installed-wheel gate `b334003`, benchmark regeneration `1ff2c05`, and Windows
UTF-8 repairs `4556f84` / `5e34c6e` are implemented. Exact-product-SHA CI
36373813267 and test 36373813312 passed; installed Python CLI commands passed
on macOS, Windows and Linux with verified artifact hashes. See
`docs/progress/2026-09-28-112131.md`. Publication remains blocked below. WM1 mask checks
pass; electrical agreement remains NOT_EVALUATED, with independent electrical
inputs/mapping still required. PyPI Trusted Publishing is not configured, as
confirmed by the owner: no tag or publication until configured and verified.
The owner authorized app design and a Vercel landing page on 2026-09-28 before
publication. The static design reference is in web/; native delivery remains
pending. Build the macOS-only PySide6 shell specified by the user.
Read Design.md in full before UI code. Signing, notarisation, actual installed
workflow screenshots, signed updates and rollback must be evidenced before
claiming desktop delivery. Windows/Linux desktop remain pending.

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

- **Current continuation (2026-10-03 01:18):** Palace observer's missing
  `/proc/meminfo` is reproduced and repaired with a bounded non-seeking read;
  no solver behavior or scientific gate changed. CI `36900147878` failed the
  Windows job-status assertion then passed unchanged; extend diagnostic
  retention to that matrix job. Local full suite also timed out once during
  recorded host sleep, then passed unchanged (2034 passed, 8 skipped).
  See `docs/progress/2026-10-03-011837.md`. Palace convergence/branch merge,
  native releases and publisher setup remain pending. Source reviews 22/100;
  accepted integrations 0/100. No new solver job was dispatched.

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
  `docs/integrations/checklist.md` now shows all 100 slots with completion
  evidence requirements; it currently claims **0/100 accepted integrations**,
  not 0 existing adapters. The generator rejects missing evidence and unknown
  IDs. This checklist/release preparation was implemented in `8833ec9`; its
  exact-SHA CI passed. Audit and accept each target independently before
  checking it.
- **Next:** (1) Audit and deduplicate all 100 target slots, including license
  and commercial dependencies; rank by scientific impact and feasibility.
  The first twenty-one source/scope reviews are recorded in
  `docs/architecture/integration-source-audit.md`: SQcircuit's hint points
  away from its maintainer repository, QEDA's hint resolves to a PCB tool,
  current Quantum Metal packaging differs from the locked legacy name,
  pyEPR's live HFSS path is disabled, and CircuitQ has no product adapter. The scqubits prepare-only observation
  is superseded by typed transmon execution in `3799d8d`, without independent
  reference acceptance. The SQuADDS and
  PycQED hints return 404 while their maintainer repositories have different
  names; Qiskit Dynamics is archived. The FasterCap and FastHenry2 supplied
  hints also return 404, and the actual FastHenry2 source license is not yet
  established. Slots 15–20 now distinguish Meep/gprMax/scuff-em solvers,
  component-specific Elmer licensing, and MFEM/DOLFINx numerical libraries.
  Slot 21 identifies the already-installed optional scikit-rf 1.12.0 library,
  pinned upstream release, dependencies and analytical CPW assumptions; no
  duplicate adapter was added. Source revisions do not establish numerical acceptance.
  These reviews do not raise the 0/100 accepted-integration count.
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
  Real Palace run `36223218053`, attempt 1/job `108352252265`, executed the
  bounded solver at that SHA: 106,614 then 114,276 elements stayed below the
  200,000 guard, but physical classification rejected both modes with
  `TARGET_MODE_NOT_FOUND` (mode 1 failed the quarter-wave profile gate).
  This is `SIMULATION_INVALID`, not a Palace benchmark pass. Compact solver
  outputs are retained in `docs/progress/evidence/2026-09-26-154000/` and
  analyzed in `docs/progress/2026-09-26-154000.md`. Attempt 2 of the same
  workflow was dispatched unchanged at `f407c63`; inspect that result and
  compare its hashes, mode identities and resource records before editing.
  Preserve the physical gates; diagnose the actual profile values and field
  sampling instead of guessing or weakening thresholds. Full benchmark,
  convergence and reference comparison remain unexecuted, so do not merge.
  [Palace attempt 2](https://github.com/JungluChen/Text-to-Layout/actions/runs/36223218053)
  at `f407c63` reproduced the same `TARGET_MODE_NOT_FOUND` verdict with
  byte-identical solved-state, mode-tracking, eigenvalue and regional-energy
  hashes. The 114,276-element adapted state remained under the guard.
  Attempt-2 compact evidence and comparison are in
  `docs/progress/2026-09-27-013856.md`. Diagnostic-only branch commit
  `e4f52cc` now retains mode signatures and measured longitudinal profiles
  on rejection. [Palace run 36259710684](https://github.com/JungluChen/Text-to-Layout/actions/runs/36259710684)
  attempt 1 at that SHA again rejected both modes. In the first solved state,
  mode 1 passed the endpoint and magnetic-shape tests but its electric
  quarter-wave profile correlation was 0.7423 against the existing 0.90
  criterion; mode 2 was classified as a substrate mode. Its compact packet is
  retained under `docs/progress/evidence/2026-09-27-080338/`. Attempt 2
  completed with the same invalid verdict; mode profiles, solved-state
  summary, FEM model, material map and first/final eigenvalue CSVs are
  byte-identical to attempt 1. Retained attempt-2 logs and evidence are in
  that same directory. Diagnostic-only commit `d40b165` now collects profiles
  for both solved states before first-state seed rejection. Its local full
  suite passed twice (1980 passed, 12 skipped), and exact-SHA general CI
  `36284650404` passed. Real Palace run
  [36295978520](https://github.com/JungluChen/Text-to-Layout/actions/runs/36295978520),
  job `108554791553`, completed with TARGET_MODE_NOT_FOUND. Both states
  were retained: mode-1 electric correlations 0.7422995731 and 0.8745187355
  remain below 0.90. Attempt 2 was requested unchanged on 2026-09-28; monitor
  it without dispatching a duplicate. Compare per-state hashes before editing.
  Evidence is in `docs/progress/2026-09-28-122322.md`. See
  `docs/progress/2026-09-27-080338.md` for validation and resume commands. The
  first-state diagnostic frequencies must not be conflated with the final
  adapted-state CSV. Full
  scientific acceptance and branch merge remain pending.
  Windows CI `35915634148` and `35933303913` both passed unchanged second
  attempts; their first-attempt timing failures remain unexplained, not fixed by
  relaxed waits. See `docs/progress/2026-09-25-010046.md` for exact continuation.
  The newer Windows test workflow `36281590003` again failed its first attempt
  at the 15-second job-status assertion and passed unchanged on attempt 2.
  A deterministic local interleaving reproduced a stale `running` record
  overwriting `completed` twice. The focused cross-process record-lock repair
  and regression in `f687841` pass local full gates. Exact-SHA CI at
  `f45ce81` passed Windows/macOS/Linux on Python 3.11/3.12, including the
  Windows job regression; see `docs/progress/2026-09-27-080338.md`. This
  validates the focused state-write repair, not the Palace physics.
  Require real reduced-benchmark execution, repeated verification, convergence
  and valid evidence before promotion. Do not dispatch a duplicate.
- **Completion commits:** Pending.

### 3. Audit scientific correctness across simulation tools

- **2026-09-28 CPW reporting increment:** Reproduced a misleading global
  backend label twice. Research reports now identify the primary thick-substrate
  estimate/proposals separately from the optional 500 um / 1 GHz scikit-rf
  comparison; removed an unestablished blanket accuracy claim. Equations,
  numerical values and geometry are unchanged. Verification and continuation:
  `docs/progress/2026-09-28-143715.md`.

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
  validate the smallest missing delivery milestone. The Python tag workflow
  now gates PyPI on Windows/macOS/Linux source tests, build, CLI and evidence
  checks, but no native desktop installer or auto-update channel exists.
  Build and verify one installed app per platform with signing, update/rollback
  and versioned tutorial captures before a desktop release. The npm package
  remains pending a tested JS client and package identity. See
  `docs/releases/README.md`; do not tag a release until publication readiness
  and the trusted publisher are verified.
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

### 2026-09-29 browser continuation

Three.js geometry preview replaces the static3D placeholder; source/validation
and remaining physical-stack/accessibility gaps are recorded in
`docs/progress/2026-09-29-011521.md`. Native Qt delivery is still pending.

### 2026-10-12 latest Palace diagnostic

Scheduled run 38238001763 on d85c9dc passed installation and official smoke,
then received runner shutdown/exit 143 at 3,366,845 elements. Last OOM counters
were zero; cause unproven. Full reduced/convergence/reference evidence absent.
See `docs/progress/2026-10-12-221735.md`; review resource bounds and retention
before a smallest faithful repeated diagnostic. Palace branch merge remains blocked.

### 2026-10-13 SQcircuit CLI slice

The typed LC wrapper is now exposed as `textlayout sqcircuit-lc` with explicit
SI request, interpreter, fresh output directory and timeout. Two local cases
ran twice; no checklist promotion. Next: dedicated repeated solver platform
benchmark and independent downloaded-packet verification before entry 006
acceptance. See `docs/progress/2026-10-13-042014.md`.

### 2026-10-13 SQcircuit platform workflow

Dedicated manual sqcircuit-integration workflow now provisions isolated pinned
runtimes and runs two cases twice on Windows/macOS/Linux, retaining packets and
repeat checks. Actual platform execution and downloaded-packet review pending;
entry 006 remains unchecked. See `docs/progress/2026-10-13-102945.md`.


### SQcircuit bounded acceptance (2026-10-13)

Entry 006 is accepted only for the two specified ideal parallel LC cases with
explicit additional branch capacitance, public SQcircuit Hamiltonian and NumPy
dense eigh. Implementation e2f75ad56b00972530a9a1bbe9990f54e8476b97 passed
repeated solver workflow 38337411823 on all three OSs; all twelve downloaded
packets independently verified. Exact CI 38337385997 and test 38337385977
passed. Worst reference error 9.5367431640625e-7 Hz; raw repeats identical
within each platform. Evidence: docs/progress/2026-10-13-102945.md. This
supersedes earlier pending platform/checklist statements for this narrow scope.
Nonlinear/noise/EM/measurement and broader domain support remain pending;
harmonic truncation does not demonstrate nontrivial spatial convergence.

Next ordered item: audit entry 007 source/license/version, existing adapters and
numerical evidence before defining a bounded implementation.

### 2026-10-13 entry 007 inventory

SQuADDS source/dependency/existing-adapter audit retained in
`docs/integrations/squadds.md`. Tag v0.4.5 declares 0.4.4 while PyPI reports
0.4.5; reconcile artifact identity before installation. Reuse existing prior
and WM1 geometry boundaries; next specify an offline typed prior slice with
explicit units/provenance. Electrical reproduction remains NOT_EVALUATED;
entry 007 unchecked. See `docs/progress/2026-10-13-162826.md`.

### SQuADDS package identity reconciled (2026-10-13-235906)

Published wheel/sdist hashes verified twice; 107 package files match the pinned
tag. Only pyproject version differs, 0.4.4 to 0.4.5. No installation or numerical
acceptance; entry 007 remains unchecked. Next specify the offline prior data
contract and independently verify its dataset provenance/units. See
`docs/progress/2026-10-13-235906.md`.

### Windows lifecycle recurrence (2026-10-14-043935)

30660f3 CI 38426799625 failed Windows 3.11 lifecycle wait; retained artifact
shows successful finalization after 20 seconds. Unchanged failed-job retry
dispatched; no fix or timeout change. Compare retry and collect phase timings
before implementation. See `docs/progress/2026-10-14-043935.md`.

### Offline SQuADDS WM1 slice

The prior boundary now selects an exact device from the pinned offline dataset,
retains source/units and converts three frequency fields to Hz. All six real
records checked twice locally; no electrical or checklist promotion. Next add
CLI and repeated platform data-provenance checks; upstream package execution
remains distinct. Windows retry 38426799625 attempt 2 and checkpoint CI
38464627633/38464627332 passed unchanged; the lifecycle cause is still unresolved.

### WM1 offline CLI

Thin squadds-prior CLI now exposes the verified loader with exact device
selection, stdout JSON and explicit failure exits. Repeated local real-data
output matches; platform benchmark acceptance and upstream toolkit execution
remain pending. Entry 007 stays unchecked.

Manual WM1 platform benchmark added; actual exact-SHA execution and downloaded
packet review pending. No entry-007 checklist promotion from workflow code.

Entry 007 follow-up (2026-10-18): three-platform WM1 prior run and exact-SHA
CI passed. Unchanged upstream metadata helper executed twice locally; foundry
lookup discrepancy and constructor cache-deletion/forced-fetch effects audited.
Normal installed-package execution remains pending; isolate home as well as
environment before constructor probes. See docs/integrations/squadds.md and
docs/progress/2026-10-18-224826.md. Checklist remains 6/100.

2026-10-19 entry 007: normal SQuADDS 0.4.5 import failed twice with
PyArrow 26/NumPy 1.26.4 despite passing dependency metadata checks. A separately
hash-pinned set constrained to PyArrow 21 passed normal import twice on macOS;
related dataset/network versions also changed. No base install changes or
checklist promotion. Next controlled constructor/data execution with disposable
user home; retain Windows/Linux as untested. See docs/progress/2026-10-19-114302.md.

2026-10-19 installed-helper follow-up: normal SQuADDS imports and real local
datasets.Dataset now pass repeated metadata/lookup checks against pinned bytes.
Evidence docs/progress/2026-10-19-160828.md. Next implement the isolated typed
offline metadata boundary with source/schema checks and repeated platform
execution; no constructor or remote retrieval required for that narrow scope.
Entry 007 remains unchecked; no electrical claim.

2026-10-19 failure audit: latest Palace 39225214993 again shut down at
3,366,845 elements/4,044,674 ND unknowns; smoke passed but full reduced
convergence/reference absent. Retained logs, memory observations and smoke
packet in docs/progress/2026-10-19-221501.md. No automatic solver rerun or
branch merge. Windows Python 3.12 CI 39220790303 observed running, then
finalized return 0 at 16 seconds from creation; unchanged failed-job retry
attempt 2 pending. Retain phase timings before any lifecycle fix.

Entry 007 raw metadata worker now executes pinned installed helpers offline.
Two local packets match the retained independent projections. Next typed
product-side assessment/runner, retained failures and platform execution;
raw NOT_EVALUATED output does not complete the checklist.

Entry 007 independent raw metadata assessment now rejects corrupted source,
records and identity/status claims. It establishes data agreement only;
process-verifying product runner and repeated platform execution remain next.

Entry 007 metadata process runner now retains local child provenance, logs,
timeouts and independently assessed packets. Local unchanged repeats pass;
next add the CLI and repeated three-platform evidence before scoped acceptance.

Entry 007 metadata CLI now exposes the typed runner; next repeat the exact
pinned optional stack on all three OSs and review downloaded evidence.

Entry 007 platform locks preflighted: Windows and explicit Linux glibc 2.34
resolve twice with unchanged shared versions. Next install on actual target
runners, retain failures and repeat CLI packets; resolution is not acceptance.

Entry 007 manual metadata platform benchmark prepared; dispatch once, inspect
all actual jobs and independently verify artifacts before any acceptance.

### Accepted metadata-only scope (2026-10-21)

Entry 007 is accepted only for pinned offline measured-device metadata helpers
and WM1 lookup, implementation 1249e11bf067e98162f1c7c99869b10ac9864c6d.
Run 39568673901 executed twice on Windows/macOS/Linux; six downloaded packets
and 30 artifact hashes were independently checked twice. Same-platform raw
repeats are identical; metadata agrees across platforms and with pinned source.
Results remain PRIOR_ONLY. Numerical convergence is not applicable to metadata
lookup; no electrical reconstruction, measurement agreement or full-toolkit
acceptance is implied. Evidence: docs/progress/2026-10-21-221821.md.

Entry 008 QEDA audit pins qeda/qeda at 8a8f890362e6099deef460457cd236d1d14fdca8
(package declares 0.4.7, MIT): a PCB library generator, not a quantum solver.
Next verify npm archive/source identity and an isolated lock, then define a
local two-pin geometric reference before adapter work. See docs/integrations/qeda.md.

Entry 008 npm audit (2026-10-22): declared source 0.4.7 is not published
at the npm version endpoint (404 twice); registry latest 0.4.1 maps to a
different source commit. Archive integrity and 38 shared files match; 85
compiled files still need reproducible compilation. Next pin CoffeeScript
2.3.2 and inspect local-only behavior before selecting runtime/adapter scope.
Evidence: docs/progress/2026-10-22-101637.md. No acceptance or numerical claim added.

Entry 008 compilation audit: all 85 published 0.4.1 JavaScript files match
pinned source compiled twice with CoffeeScript 2.3.2. Next isolated runtime lock
and closed local YAML/base inputs before geometric reference execution.
Evidence: docs/progress/2026-10-22-161039.md; no acceptance promotion.

Entry 008 runtime lock and repeated imports verified locally; geometry remains
pending. Paper benchmark run 39747389879 failed on Python 3.14.4 with overflow
and bands[1] IndexError; local unchanged command passes twice. Remote unchanged
attempt 2 queued; investigate environment discrepancy before edits. Evidence:
docs/progress/2026-10-22-220849.md. No numerical acceptance or tolerance change.

Paper diagnostic update: unchanged Linux attempt2 of 39747389879 fails again.
Local scalar/vector unit-cell probe repeats identically and finds three bands;
Linux equivalent probe remains needed before attributing cause to Python/NumPy.
Retained evidence and exact next experiment: docs/progress/2026-10-23-040737.md. No numerical
fix, relaxed tolerance or checklist promotion.

Entry008 local QEDA custom-pad probe now executed twice after correcting A/B to
upstream L/R resistor pin groups. Pad readback zero error, pins1/2 present;
full acceptance remains rejected pending parser/identity/timestamp and platform
evidence. See docs/progress/2026-10-23-100753.md. Linux paper diagnostic remains blocked
locally: no docker/podman/orb command available; controlled CI probe still needed.
