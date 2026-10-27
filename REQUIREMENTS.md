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

### INT-15 — offline WM1 prior selection

The bounded SQuADDS API must read only the pinned local dataset, select an
explicit qubit_1 through qubit_6, and preserve source identity and original
unit fields alongside ordinary-Hz values. Reject changed bytes and ambiguous
records. Return PRIOR_ONLY with no geometry inference or electrical promotion.
Upstream package execution, CLI/MCP/GUI and platform acceptance are separate.

Offline WM1 priors are also accessible through `textlayout squadds-prior DATABASE
--device qubit_N`. The CLI prints JSON, preserves PRIOR_ONLY and performs no
network access or file writes. GUI and MCP delivery remain pending.

### Offline SQuADDS metadata worker

Developer interface: run `src/textlayout/external/_squadds_metadata_worker.py
DATABASE NEW_OUTPUT.json` with the explicitly selected isolated Python runtime.
Requires SQuADDS 0.4.5, datasets 5.0.1, PyArrow 21.0.0, NumPy 1.26.4 and
pandas 2.3.3 (complete audited runtime pins retained in the integration audit).
It checks dataset SHA256/1 MiB bound and installed helper hash, uses normal
upstream imports with offline dataset flags, and writes a new raw JSON packet.
Existing outputs are refused. No base dependency is added, no SQuADDS_DB
constructor or remote retrieval is invoked. Optional imports may create library
caches; use the isolated runtime/cache configuration documented in the audit.

Output is PRIOR_ONLY, physics_verified=false, assessment_status=NOT_EVALUATED.
Configuration names are identifiers, not simulation values. The observed
SQUILL/N/A foundry discrepancy is preserved. This raw worker is not a typed
public runner, CLI command, MCP endpoint or electrical validation; product-side
assessment, timeout/log retention and Windows/Linux execution remain pending.
No UI or screenshot delivered. On errors retain stderr, repair the explicit
runtime/input and retry with a new output path; do not promote partial results.

### SQuADDS metadata packet assessment

`textlayout.external.squadds_metadata_assessment.assess_metadata(database: bytes,
packet: dict)` checks raw worker records, lookup results, pinned hashes/revision,
versions and status flags against an independent projection of the pinned local
dataset. No defaults, filesystem writes, optional imports or processes. Returns
frozen MetadataAssessment(records_checked, dataset_sha256, PRIOR_ONLY, false);
malformed or mismatched data raises ValueError. Runtime strings are required
but are self-reported: data agreement does not prove execution identity.
The upstream foundry discrepancy is preserved. Boolean/numeric substitutions
and extra fields are rejected. No electrical or measurement promotion.

Example: read the pinned database bytes and raw JSON packet, call assess_metadata,
and expect records_checked=3 for the retained example. On rejection retain both
inputs and inspect source/identity differences; do not rewrite the evidence to
make it pass. AI prompt: “Assess this raw metadata packet against pinned local
source bytes, report discrepancies, and keep process verification separate.”
Product runner, timeout/log retention and Windows/Linux execution remain next.
No public CLI/MCP tool or GUI/screenshot is added by this pure assessment API.

### Metadata process runner

The SQuADDS metadata runner requires an explicit optional-runtime interpreter and a fresh output directory. It must retain input, raw output, logs, return code and hashes on attempted execution, and must never promote metadata agreement to electrical validation.

### Metadata CLI

`textlayout squadds-metadata DATABASE --python PYTHON --out NEW_DIRECTORY
[--timeout SECONDS]` calls the existing typed metadata runner, prints its JSON
result and exits zero only for successful metadata assessment. Timeout defaults
to 120 finite positive seconds. Pinned local data and the audited optional
SQuADDS environment are required. Inputs, logs, raw output and hashes are written
in the fresh directory; invalid inputs or existing output return nonzero.
Results remain PRIOR_ONLY; no electrical validation, MCP method or GUI is added.
Repeated Windows/Linux execution of this new command remains pending.

### Metadata platform benchmark

Manual workflow `squadds-metadata-integration.yml` installs the retained
platform hash manifests into isolated Python 3.12 environments, checks Linux
glibc >=2.34/macOS ARM64, retains install/check/freeze logs and runs the metadata
CLI twice. It requires matching raw bytes and verifies artifact hashes and
PRIOR_ONLY status. Failed runs upload available evidence; caches are excluded.
Before dispatch inspect `gh run list --workflow squadds-metadata-integration.yml`,
then dispatch once with `gh workflow run squadds-metadata-integration.yml --ref main`.
Retain the exact SHA/run ID and download all three artifacts for independent
review. On failure retain logs and rerun unchanged before modifying pins.
Workflow configuration is not platform acceptance; entry 007 remains pending.
AI prompt: “Review these repeated metadata packets, verify source and output
hashes, and distinguish package execution from electrical validation.”
No MCP method, GUI screenshot or physical comparison is added.

### QEDA bounded syntax reader

`textlayout.external.qeda_syntax.parse_footprint_syntax(data: bytes)` returns an
immutable `Expression`/`Atom` tree or raises `ValueError`. UTF-8 input is bounded
to 1 MiB, 20,000 nodes, depth 32 and 4,096 decoded characters per atom. Quotes
and escaped quote/backslash are explicit; malformed/trailing tokens and control
characters in atoms fail closed. It has no optional dependencies, file writes,
network access or execution side effects. This is syntax parsing only: numeric
finiteness, units, geometry, pin identity, solver provenance and KiCad schema
acceptance are not evaluated. No CLI/MCP equivalent or GUI is delivered yet.

### QEDA rectangular-pad decoder

`textlayout.external.qeda_pad.decode_rectangular_pad(data: bytes)` returns a frozen
`RectangularPad` with number, x/y/width/height/mask-margin in mm and SHA-256 of
the original bytes. It accepts one unrotated F.Cu/F.Mask/F.Paste SMD rectangle
numbered 1 or 2; required fields appear exactly once. Extra/drill/rotation fields,
quoted numbers, exponents and non-finite values fail with `ValueError`. Decimal
coordinates are bounded to +/-1000 mm with at most nine fractional digits; sizes
are positive, mask margin nonnegative. These are supported input limits, not
scientific tolerances. No defaults, optional dependencies or side effects.
This decodes one pad only: whole-footprint identity, extra conductive geometry,
symbol mapping, reference comparison and execution provenance remain pending.
No CLI/MCP/GUI equivalent or solver/geometry acceptance is implied.

### QEDA planar graphic decoder

`textlayout.external.qeda_graphic.decode_planar_graphic(data: bytes)` decodes
one fp_line or fp_circle into frozen PlanarGraphic: kind, layer, origin_mm,
end_mm, width_mm and raw_sha256. Origin is line start or circle centre; end is
line endpoint or a point on the circle. Required fields are unique and explicit;
only F.SilkS/F.Fab/F.CrtYd are supported. Copper/unknown layers, extra or nested
fields, nonpositive width and degenerate shapes raise ValueError. Coordinates
use the pad decoder's bounded decimal mm domain. No defaults, dependencies,
I/O or execution side effects. No whole-footprint, clearance, reference, 3D or
fabrication acceptance; no CLI/MCP/GUI equivalent yet.

### QEDA model-reference record

`textlayout.external.qeda_model.decode_model_reference(data: bytes,
expected_basename: str)` requires an explicit keyword basename: ASCII letter,
digit or underscore first, up to128 stem characters from letters/digits/_/-,
then `.wrl`. No paths, quoted names or implicit defaults. Returns frozen
ModelReference (basename, dimensionless scale triple, zero_translation,
zero_rotation, raw_sha256). Exactly one at/scale/rotate field with xyz triples
is required, matching the audited 0.4.1 emitter's zero/0.3937/zero values.
Bounded decimal equality rejects changed, non-finite, exponent or nested values
with ValueError. No file/network access, dependency or side effect. This checks
record identity only: VRML existence, units, geometry, full-footprint/reference
acceptance and execution provenance remain unverified. CLI/MCP/GUI pending.

### QEDA text-annotation decoder

`textlayout.external.qeda_text.decode_text_annotation(data: bytes,
expected_text: str)` requires keyword text identity and returns frozen
TextAnnotation: role, text, layer, hidden, position_mm, font_size_mm,
thickness_mm and raw_sha256. Supported forms: visible reference REF** on
F.SilkS, visible ASCII-identifier value on F.Fab, hidden user REF** on F.Fab.
Only zero or omitted angle; explicit unique at/layer/effects/font/size/thickness
fields, bounded decimal mm coordinates and positive font metrics. Unknown,
duplicate, nested extra fields and copper layers raise ValueError. No I/O,
optional dependencies or defaults for missing required fields. Full-module,
placement reference, text clearance/readability and provenance remain pending;
no CLI/MCP/GUI equivalent or integration acceptance.

### QEDA whole-module structural decoding

`textlayout.external.qeda_module.decode_footprint_module(data: bytes,
expected_name: str)` requires keyword ASCII identifier (1–128 stem characters)
and returns frozen FootprintModule: name, pad/graphic/annotation tuples,
model record and raw_sha256. Requires matching module/value/model identity,
F.Cu+smd metadata, unique pads1/2, one reference/value/user annotation each and
one model. Every child is dispatched to its strict record decoder; unknown
atoms/lists, duplicates, missing required records and unsupported geometry reject
with ValueError. Original child byte slices are checked against the parsed tree
before decoding; hashes do not describe reserialized text. All syntax resource
limits apply. No dependencies, I/O or execution side effects. Supported graphics
may vary in count: shape/reference agreement, required outline completeness,
clearance, symbol mapping, VRML units and execution provenance remain pending.
A successful decode is structural evidence only, not integration acceptance.
CLI/MCP/GUI delivery remains pending.

### Fixed QEDA custom-pad reference assessment

`textlayout.external.qeda_reference.assess_probe_pad_reference(data: bytes)`
first decodes the complete Resistor_PROBERESISTOR module, then compares pad1/2
x/y/width/height to the pre-execution reference (centres(-1.5,0)/(1.5,0)mm,
size1x1.5mm). Returns frozen PadReferenceAssessment with eight PadComparison
records (actual/expected/error in mm and within_tolerance), maximum error,
pad_reference_matches, module raw hash and fixed reference ID/hash. Absolute
1e-6mm tolerance is fixed with no caller override: it permits parsing roundoff,
not the generator's0.001mm quantization shift. Decimal decisions use an isolated
32-digit context. Invalid structure raises ValueError; valid out-of-tolerance
geometry returns a mismatch. No dependencies/I/O/side effects. This is pad
position/size agreement only; mask margins, graphics completeness, symbol pins,
VRML, execution provenance and whole-integration acceptance remain pending.
No CLI/MCP/GUI equivalent yet; no electrical or fabrication claim.

### QEDA fixed-probe symbol identity

`textlayout.external.qeda_symbol.decode_probe_symbol(data: bytes)` returns frozen
ProbeSymbol: name, footprint_reference, pin_mapping, raw_date, raw_sha256 and
body_sha256. It checks every token/record of the audited ProbeResistor legacy2.3
symbol template, including passive L1/R2 pins and probe:Resistor_PROBERESISTOR
association; no caller defaults/options. A valid calendar Date header is retained
with no timezone assertion. Input limit16KiB, ASCII template only; LF/CRLF and
horizontal whitespace may vary, but raw hashes never normalize them. Unexpected,
missing/extra records, changed identity or malformed timestamps raise ValueError.
No I/O/dependencies/process effects. Pin mapping is checked against the retained
input YAML in tests; drawing-template equality is not independent geometry proof.
General KiCad/native import, electrical accuracy, fresh execution/provenance and
integration acceptance remain pending. No CLI/MCP/GUI equivalent yet.

### QEDA fixed-probe preparation

`textlayout.external.qeda_prepare.prepare_probe(output_dir: Path, *,
runtime_package: Path) -> PreparedQedaProbe` creates a new directory containing
fixed library/probe.yaml (geometry in mm), generate.cjs and preparation.json.
Parent must exist and be trusted; existing paths are refused. Runtime package
path must be absolute, bounded and control-free; JSON encoding preserves it as
a JavaScript string. No runtime import/discovery/download or process is invoked.
The returned frozen record provides paths, input/script/manifest SHA256 values
and input_files_prepared status. Manifest explicitly reports runtime NOT_VERIFIED,
execution NOT_EXECUTED and reference NOT_EVALUATED. Required version0.4.1 is a
requirement, not an observed version. Expected output names are a plan only.
I/O failures propagate and may leave a partial directory for inspection; use a
new directory after recovery. No hostile-parent/concurrent-writer guarantee.
Optional dependencies and base install are unchanged. Runtime identity checks,
bounded execution, CLI/MCP, platform acceptance and GUI captures remain pending.

### QEDA supplied-inventory comparison

`textlayout.external.qeda_inventory.decode_inventory(data: bytes)` returns a
sorted immutable tuple of InventoryEntry records (path and exactly one SHA256 or
relative symlink target). UTF-8 JSON is bounded to2MiB/20000entries; duplicate
keys/paths, unknown fields, malformed hashes, non-normalized/absolute paths and
lexically escaping links raise ValueError. No links are followed or files read.
`compare_inventories(expected: bytes, observed: bytes)` returns frozen
InventoryComparison with both raw snapshot hashes and sorted missing/added/changed
paths plus matches_supplied_inventory. Empty expected snapshots are rejected;
empty observed snapshots report all entries missing. Ordering/JSON whitespace
can differ while records match; raw hashes preserve those differences.
No dependencies, filesystem/process/network side effects, units or defaults.
This compares caller-supplied records, NOT installations: snapshot authority,
freshness, actual file hashing, lock/root-package coverage, executable identity,
symlink resolution and concurrent mutation require separate capture/probe logic.
Matching does not establish installed/ready/executed status or numerical validity.
No CLI/MCP/GUI endpoint yet; entry008 remains pending.
