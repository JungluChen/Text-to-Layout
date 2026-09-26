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
