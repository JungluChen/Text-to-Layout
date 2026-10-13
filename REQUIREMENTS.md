# Product requirements

**Document class: MANUAL_DOCUMENTATION.** Owner-approved requirements as of
2026-09-15. These are delivery criteria, not a claim that every surface is
implemented. Scientific correctness remains the first priority in
[to do list.md](to%20do%20list.md).

## Product and supported surfaces

Text-to-Layout is one evidence-backed engineering product with multiple clients
of the same deterministic design, geometry, verification and simulation core.

| ID | Required surface | Delivery requirement |
| --- | --- | --- |
| SUR-01 | CLI | Reproducible commands, explicit units, machine-readable results where supported, useful help/errors, meaningful exit codes and resumable long jobs. |
| SUR-02 | Desktop software | Installable Windows, macOS and Linux applications with project/files, layout inspection, simulation jobs, evidence/results and help; validate each claimed platform. |
| SUR-03 | Browser tool | Shared workbench served locally and eventually online with hosted solver execution. Show execution location and data transfer before a run; local paths are not hosted-service URLs. |
| SUR-04 | MCP | Discoverable tool schemas, typed inputs/outputs, honest capability status, artifact access and explicit side effects; maintain compatibility while migrating from the existing legacy server. |
| SUR-05 | Codex plugin | Thin host integration consuming the shared core through supported tools; validate installation, discovery and an end-to-end example in the actual host. |
| SUR-06 | Claude Code plugin | Equivalent supported workflow and evidence contract, with host-specific install/configuration instructions and actual host validation. |

Do not equate a plugin manifest with a tested integration, an API server with a
finished browser product, or a Python package with native desktop installers.
Existing CLI/API and legacy MCP paths are inventoried in
[the function catalog](docs/function-catalog.md).

## UX and design ownership

- **UX-01:** [Design.md](Design.md) is the design agent's implementation brief.
  Use [dickwu/apple-design-skill](https://github.com/dickwu/apple-design-skill)
  at documented revision `da2da6dd03aacf06da3fecf205347601d38bb141` as the initial
  reference. Read the skill and relevant HIG pages before design reviews.
- **UX-02:** Apply Apple-informed clarity, hierarchy and accessibility while
  respecting Windows/Linux/web conventions. Preserve native window controls,
  platform keyboard shortcuts and accessible semantic components.
- **UX-03:** The main view is an engineering workbench: design inputs, geometry,
  simulation jobs, numerical results and supporting evidence. Always distinguish
  prepared, executed, converged, validated, failed and unavailable states.
- **UX-04:** Provide a searchable **Functions** view and guidebook catalog with
  name, purpose, CLI/API/MCP mappings, inputs/units, defaults, outputs/artifacts,
  prerequisites, side effects, maturity, examples, errors and evidence.
- **UX-05:** Design agent deliverables include screen/state specifications,
  light/dark tokens, keyboard/focus behavior, responsive layouts, accessibility
  review, implementation handoff and real screenshot evidence after implementation.
  The designer uses the same numerical status contract as the engineering core.

## Shared behavior and interfaces

- **INT-01:** All clients use shared application services and validation. No
  separate numerical implementation in UI, plugin prompts or MCP wrappers.
- **INT-02:** Publish the actual MCP `tools/list` schemas and CLI/OpenAPI mappings
  for each release. Clearly separate existing legacy tools, supported product
  functions and proposed adapters. Preserve compatibility or document migration.
- **INT-03:** Each job/result carries traceable inputs, units, solver identity,
  status, logs and artifact references. UI progress and successful process exit
  alone never establish numerical convergence or independent agreement.
- **INT-04:** Hosted artifacts use authorized service references; local file
  paths remain local. Define hosted authentication, job ownership, isolation,
  data transfer and resource limits before enabling hosted execution.
- **INT-05:** Tool discovery must not launch simulations. Execution tools expose
  their effects and prerequisites; duplicate requests must not silently start
  duplicate long jobs. Use existing job services and stable IDs where available.
- **INT-06:** Treat the 100 user-requested Quantum/RF EDA integration slots as
  candidates until upstream identity, license, version, platform and numerical
  behavior are verified. Doctor may show scoped import/version probes; a found
  tool is not an executed, converged or validated solver. Keep this inventory
  separate from callable MCP functions and the canonical evidence contract.
  See [integration boundary](docs/architecture/integrations.md).
- **INT-07:** Publish an explicit 100-slot completion checklist. A completed
  integration links its implementation commit, audited source/license, real
  execution, independent reference/convergence evidence and verified platforms;
  an existing adapter or discovery probe alone is not a completed merge.

## Distribution and updates

- **REL-01:** Python releases use exact version-matched tags on `main`, the
  three-platform test/build matrix and claim/evidence gates before PyPI
  publication. Use PyPI trusted publishing; verify installation from the
  published index before calling a release available.
- **REL-02:** Deliver separate Windows, macOS and Linux installed-app tests,
  package/signing evidence and verified update/rollback behavior before
  claiming desktop availability or automatic upgrades.
- **REL-03:** Publish to npm only after a real JavaScript/browser or CLI client
  is specified and tested against the shared core/service, with package name,
  ownership and trusted-publishing provenance recorded. See
  [release status](docs/releases/README.md).

## Illustrated guidebook is a release requirement

- **DOC-01:** Maintain [docs/guidebook/README.md](docs/guidebook/README.md) as a
  beginner-to-advanced guidebook linked from help and release documentation.
- **DOC-02:** Include step-by-step installation for Windows/macOS/Linux, first
  design, parameter editing, geometry inspection, solver setup, run monitoring,
  recovery, comparison and export, plus local/hosted browser and both plugin hosts.
- **DOC-03:** Each GUI procedure includes real screenshots from the documented
  version, numbered arrows/pointers matching the steps, alt text, expected result
  and recovery instructions. Store original screenshots and annotations with
  OS, app/version, commit, viewport, theme, input and capture date metadata.
- **DOC-04:** Each primary workflow includes copyable CLI commands, working
  directory, prerequisites, expected files/status, exit behavior and AI prompts.
  Include MCP tool-call examples whose arguments match actual `tools/list`.
- **DOC-05:** Provide a full function/MCP reference and examples for successful,
  invalid-input, missing-solver and failed-run paths. No fabricated numerical
  outputs, staged screenshots presented as real, or unsupported install claims.
- **DOC-06:** Annotated images supplement the text; tutorials remain usable by
  keyboard and screen reader. Include troubleshooting, terminology and links
  from errors/help to the relevant guidebook chapter.
- **DOC-07:** Verify commands and host examples on each claimed release/platform.
  Recapture changed screens and update affected examples in the same feature
  change. Unimplemented surfaces retain explicit documentation/evidence gaps.

## Acceptance and implementation order

1. Keep numerical audit and Palace repair ahead of feature implementation.
2. Establish the design brief, source-backed function inventory and guidebook
   scaffold now; these do not certify the future UI or plugin behavior.
3. Implement bounded vertical slices with the shared core, CLI, UI and applicable
   MCP/plugin entry points, then add actual illustrated walkthroughs.
4. Require keyboard-only flow, visible focus, measured contrast, light/dark,
   reduced motion, 200% zoom and compact-width checks for UI delivery.
5. Require each primary example's outputs/status to agree across supported
   clients. Verify `tools/list`/`tools/call`, schema errors, missing dependencies,
   cancellation/recovery and artifacts. No maturity upgrade without evidence.
6. A feature is not documentation-complete until its screenshot, CLI and AI/MCP
   tutorial evidence is recorded with the implementation commit.

The 2026-09-15 numerical audit delivers a bounded typed-goal CLI/API path for
capacitance, inductance, impedance and quarter-wave frequency. It validates
explicit units, process minima, footprint and target error through the shared
core. The catalog and guidebook document its defaults, outputs and recovery.
This does not complete desktop/web, MCP/plugin parity or screenshot acceptance.

No paid hosting, license purchase or commercial solver access is assumed.


### Timeout evidence retention

Shared solver subprocess timeouts retain partial stdout/stderr without promoting
a failed run. JosephsonCircuits failed results reference these logs; other
runners need their own audited recovery behavior. See the guidebook recovery
section and `tests/textlayout_suite/test_solver_timeout_logs.py`.

### CPW analytical comparison provenance

Reports must identify the thick-substrate primary estimate and proposed
parameters separately from optional scikit-rf values. State the optional
model's finite substrate and frequency defaults; do not infer an accuracy
bound or independent validation from agreement between analytical estimates.

### WEB-01 — public landing and app design preview (2026-09-28)

Deliver a Vercel-hosted static landing page and app design preview now, as
requested by the owner. Distinguish source-available CLI, pending PyPI release,
planned native apps and absent hosted solver execution. Deploy only `web/` and
its public, hashed benchmark snapshots. Do not expose local configuration or
credentials. This increment does not waive native release acceptance.

The 2026-09-28 Three.js increment replaces the browser 3D placeholder with actual
WebGL rendering of retained geometry. Missing physical stack data stays explicit;
no material thickness is inferred. WebGL/module failures retain the 2D fallback.


### INT-08 — scoped KQCircuits geometry adapter

Checklist entry 001 delivers straight CPW gap-mask generation only, through an
explicit process-isolated pinned runtime. Typed micrometre inputs, grid checks,
retained request/worker/output identities and independent GDS mask comparison
are required. Process completion and verified geometry remain separate, with no
electrical evidence promotion. Broader PCells, PDKs, GUI, HTTP/MCP parity and
EM simulation need separate accepted milestones.

### INT-09 — Quantum Metal export acceptance

For the bounded entry-002 mask fixture, independently reject empty GDS exports,
wrong scales/layers and polygon differences even when upstream reports success.
Keep mask verification separate from fabrication-junction completeness and
physical validation. The benchmark gate alone is not a typed product adapter
or cross-platform acceptance; do not check entry 002 until these exist.

INT-09 implementation now includes a typed positive-mask request and isolated
product CLI with explicit runtime and dimensions, containment/grid validation,
retained failure logs and independent KLayout comparison. Canonical electrical
acceptance is not promoted. Two real geometries and repeated platform evidence
are required before scoped checklist completion; complete junction support is
separate and remains pending.

### INT-10 — pyEPR numerical benchmark boundary

Entry 003 starts with a pinned, repeatable two-case ideal-circuit gate. Preserve
its predeclared convergence/reference limits, raw Hz/MHz sign conventions and
charge-offset assumptions. Passing this gate does not deliver EM extraction,
a typed product adapter, measured agreement or platform acceptance.

INT-10 product adapter: typed Hz energy inputs, bounded domain, fixed per-run
reference/refinement gates, process-isolated optional runtime and canonical
executed/rejected evidence. Neither successful process exit nor circuit
agreement establishes EM or measurement validation.

### INT-11 — CircuitQ LC conditioning and acceptance

Retain rejected SI eigenpairs and verify matrix equivalence when using natural
units. Fixed grid, domain, exact LC reference, zero-anharmonicity, Hermiticity
and residual gates precede any product adapter or platform acceptance.

INT-11 typed adapter requires explicit F/H inputs, isolated audited source,
fixed numerical checks, retained raw outputs and canonical rejected/executed
statuses. Two repeated platform examples are required for scoped acceptance.

### scqubits SI conversion traceability

Transmon EJ conversion derives Phi0=h/(2e) from exact SI defining constants.
Retain h, e and the derived flux quantum in result lineage. This numerical
correction does not promote cutoff convergence or reference validation.

### scqubits fixed benchmark scope

Entry 005 requires a locked two-case ng=0 transmon benchmark, actual adapter
outputs, six-level cutoff checks, Mathieu comparison and eigenpair residuals.
Passing its numerical gate alone does not complete platform acceptance.

The scqubits benchmark now writes canonical.json alongside benchmark.json.
Passing fixed numerical gates emits SIMULATION_EXECUTED quantities; rejection
emits CONVERGENCE_FAILED without values. Neither outcome claims physical or
measurement validation. The dedicated scqubits-integration workflow repeats
the two-case benchmark on each OS; only retained successful artifacts count
as platform evidence. General product results keep their original statuses.


### SQcircuit LC preparation boundary

`textlayout.external.sqcircuit_lc.SQcircuitLCRequest` requires capacitance_f
(80–100 fF expressed in F), inductance_h (60–100 nH expressed in H), and
branch_capacitance_f (1e-20–1e-15 F), with no physical defaults. Branch
capacitance is additional parallel capacitance, never included silently.
`prepare_sqcircuit_lc(request, output_dir=Path(...))` writes request.json in a
new directory and returns its absolute path, SHA256 and only
SIMULATION_INPUT_PREPARED. Existing directories are refused. No numerical
packages are imported, no solver is probed or run, and no quantities are
returned. Bounds limit intended scope; they do not certify the whole range.
Execution, canonical numerical results, CLI/MCP mappings and platform
acceptance remain pending. No graphical screen or screenshot is delivered.


### SQcircuit raw worker (developer interface)

The isolated `src/textlayout/external/_sqcircuit_lc_worker.py` accepts a prepared
request.json and a new output filename. It validates the fixed plan and explicit
SI bounds before numerical imports, requires SQcircuit 1.0.0 and refuses existing
outputs. It builds the public Hamiltonian with explicit branch capacitance and
uses NumPy dense eigh, retaining angular-frequency matrices/eigenpairs, resolved
capacitance, request hash, source hashes, Python/platform and dependency versions.
Raw JSON says numerical_acceptance=NOT_EVALUATED. This is not a canonical
executed/validated result, public CLI or MCP endpoint. A separate numerical
assessment and product subprocess failure/timeout wrapper remain pending.
Optional dependencies stay isolated; no base install change or UI delivery.


### SQcircuit retained-packet assessment

`textlayout.external.sqcircuit_assessment.assess_sqcircuit_lc(plan, rows)`
recomputes reference, last-truncation change, scaled eigenpair residual,
Hermiticity and orthonormality from retained raw arrays. It checks explicit
resolved C+Cbranch, component shapes, finite values, nonzero norms and ordered
levels. Malformed packets raise ValueError; finite numerical disagreement
returns numerical_checks_passed=false. No files or processes are changed.
The fixed orthonormality budget is 1e-12; last-truncation and reference limits
are both the predeclared 1 Hz numerical resolution, not experimental error.
This assessment emits no canonical quantities and verifies no process/source
identity. Product orchestration, canonical result conversion, CLI/MCP and
three-platform execution remain pending. No screenshot or UI claim is added.


### SQcircuit typed execution wrapper (2026-10-12)

`textlayout.external.sqcircuit_runner.run_sqcircuit_lc(request, *, python,
output_dir, timeout_seconds=120)` runs the bounded prepared LC plan in an
explicit isolated Python interpreter. Request fields and SI bounds remain as
above; output_dir must be new and timeout finite and positive. The wrapper
retains request.json, raw.json when available, stdout/stderr, typed result.json
and a SHA256 manifest containing command and worker identity. It verifies the
request hash, pinned SQcircuit source hashes/version, method and runtime
provenance before assessing matrices and eigenpairs. Only passing packets
produce a canonical SIMULATION_EXECUTED frequency in Hz. This is an ideal LC
calculation, not EM extraction, measurement validation or spatial convergence.
Missing interpreter is SKIPPED_SOLVER_ABSENT; worker errors/timeouts are FAILED;
malformed or mismatched output is SIMULATION_INVALID; rejected numerical checks
are CONVERGENCE_FAILED. These states contain no accepted quantities. Inspect
failure_reason and retained logs, repair the environment/input, then use a new
output directory; timed-out jobs cannot resume.

Two explicit LC cases executed twice locally with identical raw packets in each
pair. Maximum reference error was 9.5367431640625e-7 Hz (fixed limit 1 Hz);
last-truncation change, scaled residual, Hermiticity and orthonormality errors
were zero for these diagonal harmonic-basis cases. Evidence:
`docs/progress/evidence/2026-10-12-102833/`. This supersedes the pending product
orchestration/result-conversion work above. CLI/MCP mapping, dedicated
Windows/Linux execution and checklist acceptance remain pending. Base
installation stays lean; no UI or screenshot is delivered.


### SQcircuit CLI (2026-10-13)

`textlayout sqcircuit-lc REQUEST.json --python INTERPRETER --out NEW_DIRECTORY
[--timeout SECONDS]` exposes the typed ideal LC wrapper. All three SI request
fields are required: capacitance_f (8e-14–1e-13 F), inductance_h (6e-8–1e-7 H),
and additional branch_capacitance_f (1e-20–1e-15 F). No physical defaults.
Timeout defaults to 120 seconds and must be finite/positive. The external
interpreter must provide the audited SQcircuit 1.0.0 runtime; no base dependency
is added. The command writes the wrapper's evidence packet and prints typed
result JSON. Exit 0 means SIMULATION_EXECUTED with fixed numerical checks
passed; all other result states exit 1, including missing solver. Invalid
request or existing output directory produces JSON error on stderr, exit 1.
This supersedes the earlier pending CLI mapping. Dedicated solver runs on
Windows/Linux, MCP mapping and entry 006 acceptance remain pending. No UI,
screenshot, nonlinear/EM extraction or measurement claim is added.


### SQcircuit platform benchmark workflow (2026-10-13)

The manually dispatched `sqcircuit-integration` workflow runs the two explicit
LC requests in examples/integrations/sqcircuit-lc-{a,b}.json twice through the
product CLI on Windows, macOS and Linux. It provisions an isolated SQcircuit
1.0.0 runtime with the locally tested numerical pins (NumPy 2.5.3, SciPy 1.18.1,
QuTiP 5.3.1, Torch 2.14.1, stable SymPy 1.14.0), retains resolved dependency
versions and all CLI packets, and requires byte-identical raw repeats per case.
No packages are added to the base install. Uploaded packets still require
independent hash, source identity, eigenpair and reference review; green generic
CI or workflow configuration alone does not establish platform acceptance.
Entry 006 stays unchecked until actual solver execution and review are complete.
No MCP, UI/screenshot or measurement validation is added.
