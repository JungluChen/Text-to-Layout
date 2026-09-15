# Text-to-Layout UI/UX design and agent brief

**Document class: MANUAL_DOCUMENTATION.**

Status: **planned design specification**, 2026-09-15. This document defines the target experience; it does not certify existing UI, platform support, solver accuracy, or commercial feature parity. No UI code or mockups are implemented by this documentation change.

Related contracts: [Requirements](REQUIREMENTS.md), [function and MCP catalog](docs/function-catalog.md), [guidebook](docs/guidebook/README.md), [existing workbench workflow](docs/ui_ux_workflow.md), and [plugin architecture](docs/plugin_design.md).

## Design authority and limits

Use [dickwu/apple-design-skill](https://github.com/dickwu/apple-design-skill/tree/da2da6dd03aacf06da3fecf205347601d38bb141), pinned to `da2da6dd03aacf06da3fecf205347601d38bb141`. Its [SKILL.md](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/SKILL.md) was read for this brief, together with its reference lookup, five foundation references and six workbench references below. This is a source reference, not a claim that the skill is installed. Do not vendor Apple's reference text or redistribute Apple fonts.

Apple HIG guides macOS conventions. Its accessibility, hierarchy, legibility, and feedback principles inform the other surfaces; Windows, Linux, browsers, terminals, and AI clients retain their own interaction conventions. Concrete dimensions, tokens, screen organization, status presentation, and product flows below are **project design judgments**, not claims that Apple prescribes an EDA interface.

The existing documentation describes both the newer `textlayout` CLI/API and older `text-to-gds` workbench/MCP. Audit their actual entrypoints before connecting controls. Do not rename, merge, or advertise interchangeable interfaces merely to simplify the UI. Bind user-visible functions to verified entries in the function catalog.

## Product thesis and audience

**Help an engineer turn a stated design intent into inspectable geometry and reproducible simulation evidence.** The signature element is the evidence ribbon: every active revision visibly connects inputs, verification, solver execution, and comparison evidence. Geometry and scientific plots carry the visual identity; surrounding controls stay quiet.

Primary users are researchers and RF/quantum/layout engineers, with guided examples for newcomers and repeatable CLI/MCP workflows for automation. Data correctness takes priority over visual polish and new feature breadth.

The same design revision and run must mean the same thing in CLI, desktop, browser, and AI integrations. Each surface exposes supported capabilities and their limitations rather than promising complete parity before verification.

## Supported experience targets

| Surface | Design requirement | Release evidence required |
| --- | --- | --- |
| CLI | Discoverable commands, explicit units, readable diagnostics, machine-readable output where supported, documented artifacts | Command transcripts and exit-status checks on each claimed OS |
| Windows desktop | Resizable workbench, native window controls and file dialogs, standard Ctrl shortcuts | Actual installed application walkthrough |
| macOS desktop | Native window controls, menu access to commands, Command shortcuts, system appearance | Actual installed application walkthrough |
| Linux desktop | Respect desktop environment window conventions, keyboard focus, system font fallback | Actual installed application walkthrough on documented environment |
| Local browser | Same workbench with visible local service connection and browser navigation | Browser-to-service-to-artifact walkthrough |
| Hosted browser | Show remote execution destination and transfer scope; authenticated access where needed | Deployed-environment walkthrough before claiming availability |
| MCP | Discoverable typed tools, outcomes, artifact references, and capability limitations | Real discovery and representative tool-call transcripts |
| Codex / Claude Code plugins | Client-specific installation/configuration, function discovery, prompts, reconnect and failure help | Separate verified end-to-end walkthrough per client |

The hosted browser must never imply that its server can access a user's local filesystem or local solver automatically. Local connector work is an explicit capability with its own setup. An existing OpenAPI example, MCP server, or plugin manifest alone is not evidence of a working Codex or Claude Code plugin.

## Navigation and screen specification

Open into the active project workbench or a useful empty project screen. Do not start with a marketing landing page. Preserve the repository's prompt → clarification → parameters → artifacts → review → iteration workflow.

Use a leading sidebar with **Project**, **Runs**, **Compare**, **Artifacts**, **Functions**, and **Guidebook**. Project children may list recent revisions; run detail and nested artifacts open in the content area, keeping sidebar hierarchy at two levels. Keep Settings in the platform's normal location with an additional discoverable entry in Functions for browser users.

Global header: project name, revision label, unsaved state, execution destination (Local / named remote service), and connection status. Context toolbar: **Review Inputs**, **Generate Layout**, **Prepare Simulation**, **Run Simulation**, **Export Evidence**; show only applicable actions and explain disabled states in nearby text. No critical action depends on the window's bottom edge.

| Screen | Required content and primary behavior |
| --- | --- |
| Project / Intent | Editable prompt, example prompt, goals with units, source references, unresolved questions, editable typed parameters; review AI suggestions before applying them |
| Project / Layout | 2D layout first; optional 3D stack, layer legend, dimensions, ports, scale bar, fit/reset controls, synchronized selection inspector |
| Project / Setup | Materials/process, boundaries/ports, mesh or discretization, solver and version, execution location, known limitations, validation messages |
| Runs | Sortable history with revision, solver, stage, elapsed time, last update, outcome; selecting a run opens its retained inputs, logs and artifacts |
| Run detail | Persistent evidence ribbon, stage progress, real solver messages, convergence view, cancel/retry controls where supported, timestamps and reproduction instructions |
| Compare | Select compatible runs/reference datasets; show normalization, units, tolerances, source provenance and error; separate evidence absent from comparison failed |
| Artifacts | Group by run and purpose: geometry, diagnostics, simulation output, plots/data, reports; preview, download/open, inspect provenance |
| Functions | Human-searchable function catalog including MCP name, namespace, availability, input/output summary, dependencies, side effects, CLI equivalent and guidebook link |
| Guidebook | Searchable beginner paths, screenshots with numbered pointers, CLI commands, AI prompts, troubleshooting and version/platform metadata |

Do not use the raw JSON pane as the primary explanation. Offer it as **Inspect Data**, alongside a concise human-readable summary. Link a metric to the underlying artifact, solver output and method; retain full precision in exports while displaying appropriate units and significant figures.

## Layout, typography and visual tokens

The central layout/plot workspace gets the remaining width after navigation and the selection inspector; secondary controls collapse before scientific content becomes illegible.

```text
Regular: 1280 × 800 logical viewport
┌ Project / revision       Local · Connected       Context actions ┐
├ Evidence: Inputs · Geometry · Solver output · Comparison          ┤
├──────────────┬──────────────────────────────┬──────────────────────┤
│ Navigation   │ Layout / Plot / Run detail   │ Selection / Inputs   │
│ 208–240      │ Flexible, min 480            │ 280–360, collapsible │
│              │                             │                      │
└──────────────┴──────────────────────────────┴──────────────────────┘
Compact: 390 × 844 logical viewport
┌ Menu · Project · Local status ┐
│ Evidence summary + details   │
│ Current workspace view       │
│ Layout / Inputs selector     │
│ Full-width content area      │
│ Inline applicable action     │
└──────────────────────────────┘
```

Project defaults: at 1200px and above use three panes; at 800–1199px collapse the inspector; below 800px use a navigation drawer and one content pane. Support 360px browser width. At enlarged text, collapse panes based on available content width even if nominal breakpoints have not been crossed. Scientific canvases may pan, but explanatory content and forms must reflow without page-level horizontal scrolling.

Use system UI fonts for navigation and body, and a platform monospace stack for commands, hashes and numeric data. Web/shared UI defaults: body 16px/24px, utility labels 14px/20px, section titles 20px/28px semibold, project title 24px/32px semibold. Native macOS controls use system text styles; do not mechanically interpret CSS px as native points. Allow at least 200% content text scaling and browser zoom; preserve all primary actions.

Use a 4px spacing unit with 8/12/16/24px group spacing, restrained 6px control corners and 8px panel corners. Default pointer controls are at least 32×32 CSS px; touch/coarse-pointer controls at least 44×44 CSS px. These are project targets, not a claim about HIG unit equivalence. Keep native platform controls at their recommended sizes or larger.

Six semantic roles below are initial **project content tokens**, not hard-coded Apple system colors. Ratios are calculated using sRGB relative luminance against the listed surface; they are not measured UI conformance. Native chrome and controls use dynamic system roles. Implement high-contrast/forced-color overrides and validate actual composited colors before release.

| Role | Light | Dark | Contrast against light/dark surface |
| --- | --- | --- | --- |
| Surface | `#FFFFFF` | `#161B22` | Background role |
| Content | `#18212B` | `#E7EDF4` | 16.26:1 / 14.68:1 |
| Secondary | `#4D5B68` | `#ABB8C8` | 6.97:1 / 8.58:1 |
| Action/focus | `#075CB3` | `#89BFFF` | 6.58:1 / 9.03:1 |
| Evidence passed | `#17633A` | `#85D6A2` | 7.29:1 / 10.00:1 |
| Attention | `#92421A` | `#FFC18B` | 6.96:1 / 10.92:1 |

Use labels and distinct symbols to distinguish failure, warning and pending, even when they share an attention color. Chart series use line patterns/markers and direct labels; never borrow the passed indicator to imply an unverified curve is trustworthy. Text on filled action buttons needs its own contrast check.

Follow system light/dark appearance. Keep plots, tables, forms and geometry backgrounds opaque. Optional native material belongs only to platform chrome; blur is not required for this design. Respect reduced transparency and increased contrast. Use one consistent vector icon family in shared UI; do not bundle SF Symbols or Apple fonts for other platforms.

No decorative entrance animation. Short selection feedback is sufficient; use no motion for run completion when Reduce Motion is enabled. Preserve meaningful progress text without animation.

## Evidence, inputs and interaction contracts

Evidence ribbon stages show **Inputs**, **Geometry checks**, **Solver output**, and **Reference comparison**, each with a text status and drill-down. A successful process exit and scientific validation are separate results.

Expose backend states truthfully, with human-readable labels such as Draft, Prepared, Queued, Running, Executed, Failed, Cancelled and Unknown. These labels are a display vocabulary, not a new wire schema. Map each actual backend enum explicitly during implementation. Comparison has its own state: Not evaluated, Passed, Failed or Evidence missing. Never map Prepared to Executed or Executed to Validated automatically.

- Each result shows input revision/hash, parameter units, material/process sources, solver/version, run location, timestamps, discretization/convergence information and artifact links. Missing information is labeled missing.
- Changed parameters mark older results **From an earlier revision**. Keep previous evidence available; never silently attach it to a changed design.
- Numeric entry has an explicit unit next to the field, an accessible name, documented bounds where known and inline validation. Preserve invalid input for correction. Never silently coerce incompatible units.
- Geometry selection is possible through both the canvas and a semantic object table. Offer fit, reset, zoom controls and inspect-by-name; dragging or pointer precision is not required to obtain dimensions or ports.
- Comparison plots use named axes with units, clear normalization/log-scale disclosure and a table alternative. Offer residual/error and convergence plots when supported. Overlay only compatible quantities; explain mismatches.
- Actions have stable verb labels, visible focus and hover feedback. Preserve selection/focus after updates. Use standard Open/Save/Undo/Redo shortcuts; do not override browser or terminal commands.
- Undo reversible edits. Separate **Retry Same Inputs** from **Edit and Run Again**, keeping a new run identifier and a link to the original where run tracking supports it. Do not invent a resume operation for a solver without checkpoint support.

## First-run, waiting and recovery flows

1. **First run:** open a useful empty workbench with **Open Project** and **Try an Example**. Offer an optional short guided path and a permanent Guidebook entry. Do not require an account for local operations.
2. **Capability check:** inspect solver readiness for the selected execution location; list detected version, unavailable dependency and the correct installation/connection guide. Loading an example must not imply a real solver executed.
3. **Missing solver:** preserve the project, explain “Simulation has not run: Palace is unavailable at this execution location,” and offer **View Setup Guide**, **Check Again**, or **Prepare Inputs** if supported. Never silently substitute an analytical result.
4. **Review:** summarize the selected revision, solver, units, target metrics, source assumptions and unresolved requirements before execution. Block invalid required inputs with field-level explanations.
5. **Run:** show stage, elapsed time, last solver update and real progress information; use indeterminate progress when the solver supplies no reliable denominator. Keep other project views usable and attach to an existing job rather than duplicate it on reconnect.
6. **Failure:** keep inputs, logs, partial artifacts and the exact failed stage. Give a concise cause, diagnostic link and concrete next action. Only call a failure “timeout” when evidence supports that cause.
7. **Disconnect:** retain the last known state with its timestamp and label it stale; reconnect by job identity. Do not report a network interruption as solver cancellation or failure without checking.
8. **Cancel:** explain any lost work before a destructive cancellation, then display the confirmed outcome. Offer pause/resume only if the backend supports it.
9. **Results:** distinguish executed output, converged output and reference agreement. Show the method, tolerance basis and reproduction route. Unavailable commercial comparisons remain **Not evaluated**.

## CLI, MCP and AI plugin UX

The [function catalog](docs/function-catalog.md) is the shared discovery surface. For each real function, provide its user goal, exact callable name/interface, typed inputs with units, outputs/artifacts, execution prerequisites, side effects, errors and implementation/verification status. Show planned functions separately from callable ones. MCP discovery must reflect the server actually connected, including package/namespace distinctions.

The Functions screen provides **Copy CLI Example**, **View MCP Inputs**, and **Copy AI Prompt** only when the corresponding example is verified for that function. A natural-language example must not imply a fictional tool exists. CLI help should expose equivalent task vocabulary without renaming existing commands in documentation.

AI-generated parameters and prose are visibly identified. Keep the repository boundary: AI proposes the typed DSL; deterministic generators, verification and solver-owned output establish the artifacts and evidence. Users can inspect, change and revert proposed inputs. A prompt cannot authorize a false claim of verification.

The typed-goal CLI/API increment audited on 2026-09-15 supplies the future
workbench with explicit quantity, units, process minima, footprint and target
tolerance. Surface its final verification consistently in summaries and detail
views. A prepared-input or analytical result must keep that label even when the
target check passes. Its GUI controls, real screenshots and modern MCP adapter
remain delivery work; the current command tutorial is in the guidebook.

Plugin setup covers Codex and Claude Code separately: prerequisites, installation/configuration, credentials when relevant, tool discovery, a harmless capability call, one representative workflow, output locations, reconnect and removal. Preserve native client consent behavior. Remote processing shows what is sent and to which destination; do not silently publish local projects.

## Guidebook and screenshot acceptance

Build the [guidebook](docs/guidebook/README.md) as part of feature delivery. Every claimed working surface needs a beginner path from installation to first inspectable result, plus an advanced reproducibility path.

- Each tutorial states platform, software version/commit, prerequisites, solver readiness, inputs, numbered actions, expected result, artifact location and recovery instructions.
- Capture actual UI screenshots from the tested build. Add numbered pointer callouts/arrows beside matching numbered steps; retain readable labels and provide descriptive alt text. Preserve the unannotated capture and capture metadata. Conceptual wireframes are labeled **Planned**, never presented as product screenshots.
- Include first run, parameter review with units, layout inspection, missing solver, active/failed run, scientific result, comparison provenance and exported evidence. Cover native platform differences and both local/hosted destinations when those surfaces ship.
- Pair supported workflows with copyable CLI commands and expected output/exit status; distinguish POSIX-shell and PowerShell syntax where necessary. Verify examples in a clean sample workspace.
- Provide exact AI prompt examples for capability discovery, units/assumption clarification, generating/reviewing a design, preparing versus running a solver, interpreting evidence and reproducing results. Include the expected tool sequence and a representative transcript per supported client.
- Keep credentials and unrelated private information out of screenshots/transcripts. State which sample dataset generated every scientific screenshot; screenshots alone cannot substantiate numerical correctness.

## Assigned design-agent work and deliverables

**Assignment:** the UI/UX design agent owns this brief, flow diagrams, responsive screen specification and visual/accessibility review. It must read the pinned upstream skill and relevant references, inspect the real workbench and function catalog, then hand off concrete states and acceptance evidence to the implementation agent. This documentation task establishes the assignment; it does not imply that a permanent independent agent is running.

Deliver work in this order, preserving the accuracy-first backlog:

1. Audit the current UI and callable surfaces; label implemented, unverified and planned behavior. Review accessibility first, platform conventions second, then craft and polish.
2. Produce regular/compact and light/dark designs for the screens and failure states above, linked to actual capabilities. Supply component variants, focus order, semantic labels and responsive behavior.
3. Implement one verified vertical path from inputs to evidence before expanding feature breadth. Share domain workflows across surfaces and retain current safety/evidence gates.
4. Deliver actual screenshots, annotated guidebook pages, CLI/MCP/plugin transcripts, and a design QA report referencing the tested commit/platforms. Update the function catalog and backlog with evidence and next steps.
5. Record completion hashes in a subsequent documentation commit. Follow repository checks, progress reporting and push instructions; do not call untested native/hosted surfaces complete.

Design review should use the upstream severity vocabulary: Critical accessibility/usability blockers, High friction or platform breaks, Medium interaction refinements, Low polish. Findings cite a read source file and heading; product judgments are explicitly labeled.

## Design QA checklist

- [ ] Complete keyboard-only input → generate → inspect → run → evidence flow; focus remains visible and returns predictably after dialogs.
- [ ] Screen-reader names, landmarks, tables, validation and restrained live status announcements work; charts and canvas have equivalent nonvisual access.
- [ ] Actual rendered text contrast reaches at least 4.5:1 and meaningful controls/focus at least 3:1 in supported appearances; measure composited values.
- [ ] 360, 800 and 1280px widths, 200% text/zoom, increased contrast, reduced motion and reduced transparency preserve actions and evidence.
- [ ] macOS, Windows and Linux native interaction claims are supported by separate platform evidence; browser back/refresh/reconnect preserve expected state.
- [ ] Missing solver, invalid units, stale revision, cancellation, run failure and absent reference evidence never produce a success claim.
- [ ] Comparisons expose sources, units, normalization, tolerance basis and raw data; charts do not confuse analytical estimates with executed solver results.
- [ ] CLI, browser, MCP and plugin walkthroughs identify the same inputs/artifacts where equivalence is claimed; unsupported functions remain visibly planned.
- [ ] Guidebook screenshots, pointers, commands and AI transcripts match the tested build; no placeholder or fabricated execution evidence remains.
- [ ] Craft review retains the evidence ribbon and removes decorative cards/banners that do not help engineering work.

## Source map: read references and applied guidance

The short excerpts below identify the source principle; the concrete implementation above is this project's adaptation. Pinned files retain the context used for this brief; Apple links lead to the authoritative living guidance.

| Read file and heading | Short source excerpt / application |
| --- | --- |
| [accessibility.md › Vision](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/accessibility.md#vision) · [Apple](https://developer.apple.com/design/human-interface-guidelines/accessibility) | “Support larger text sizes.” Scale text, measure contrast and avoid color-only evidence status. |
| [layout.md › Best practices / Adaptability](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/layout.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/layout) | “Group related items” through responsive workbench panes and visible primary information. |
| [typography.md › Ensuring legibility / Desktop (macOS)](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/typography.md#ensuring-legibility) · [Apple](https://developer.apple.com/design/human-interface-guidelines/typography) | “In general, avoid light font weights.” Use system fonts; macOS text zoom requires explicit implementation rather than assuming Dynamic Type. |
| [color.md › Inclusive color / System colors](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/color.md#inclusive-color) · [Apple](https://developer.apple.com/design/human-interface-guidelines/color) | “Avoid hard-coding system color values” and retain labels/shapes alongside semantic color. |
| [designing-for-macos.md › Best practices](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/designing-for-macos.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/designing-for-macos) | “Use the menu bar” to expose desktop commands; support resizing and keyboard work. |
| [sidebars.md › Best practices / Desktop (macOS)](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/sidebars.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/sidebars) | “show no more than two levels of hierarchy”; provide hide/show navigation. |
| [windows.md › Best practices](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/windows.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/windows) | “Avoid creating custom window UI.” Use actual platform chrome and fluid resizing. |
| [progress-indicators.md › Best practices](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/progress-indicators.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/progress-indicators) | “When possible, use a determinate progress indicator.” Use solver progress only when measurable. |
| [onboarding.md › Best practices / Additional requests](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/onboarding.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/onboarding) | “Teach through interactivity.” Offer optional sample-driven guidance and delay unnecessary setup. |
| [generative-ai.md › Transparency / Outputs](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/generative-ai.md#transparency) · [Apple](https://developer.apple.com/design/human-interface-guidelines/generative-ai) | “Communicate where your app uses AI.” Make proposals inspectable, editable and reversible. |
| [charting-data.md › Best practices / Designing effective charts](https://github.com/dickwu/apple-design-skill/blob/da2da6dd03aacf06da3fecf205347601d38bb141/references/hig/charting-data.md#best-practices) · [Apple](https://developer.apple.com/design/human-interface-guidelines/charting-data) | “Make every chart in your app accessible.” Supply understandable plots and equivalent data access. |
