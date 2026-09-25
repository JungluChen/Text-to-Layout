# Text-to-Layout guidebook

**Document class: MANUAL_DOCUMENTATION.** Initial guidebook and production
documentation contract. Current CLI/API examples below are grounded in source;
this documentation change has not rerun simulations or certified plugin hosts.
New desktop/web screenshots are pending implementation, not fabricated here.

Read [product requirements](../../REQUIREMENTS.md), [Design.md](../../Design.md)
and the [function/MCP catalog](../function-catalog.md) for coverage and status.

## Choose an interface

| Interface | Starting point | Current boundary |
| --- | --- | --- |
| CLI | `uv run textlayout --help` | Existing product entry point; solver/platform availability varies. |
| Local API | `uv run textlayout serve --host 127.0.0.1 --port 8000` | API docs at `/docs`; this is not the finished workbench. |
| Desktop | Windows/macOS/Linux application | Planned delivery; installer walkthroughs/screenshots pending. |
| Browser | Local and hosted workbench | Planned shared UI; hosted deployment and execution not assumed available. |
| MCP | Installed `text-to-gds` stdio server | Existing legacy tool surface; discover schemas before calling tools. |
| Codex / Claude Code | Thin plugin under `plugins/text-to-gds` | Manifests exist; verify each host installation/workflow before claiming support. |

## First CLI design: explicit geometry without simulation

Run from the repository root in a terminal with Python and `uv` installed.
Python 3.12 is the project recommendation; optional solvers need separate setup.
On Windows, use PowerShell; use `py -3 -m uv` instead of `uv` if that is how uv
is installed. These commands use no shell-specific line continuation.

1. Install the locked environment:

   ```sh
   uv sync --frozen --python 3.12
   ```

2. Read available commands and inspect environment/solver readiness:

   ```sh
   uv run textlayout --help
   uv run textlayout doctor --json
   ```

   Keep the doctor output. A missing optional solver is not a passing simulation.

3. Request a bounded example without executing a solver:

   ```sh
   uv run textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/guidebook/idc --no-solver
   ```

   Inspect the returned file paths and report under `out/guidebook/idc`. Separate
   geometry checks and analytical target estimates from actual solver evidence.
   Do not interpret a requested 0.6 pF value as an independently measured result.

4. For deterministic DSL-driven generation, inspect the input, validate it, then
   generate an artifact packet:

   ```sh
   uv run textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json
   uv run textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/guidebook/idc-dsl
   ```

5. Open the returned GDS/preview and read the verification/report artifacts.
   Follow [solver installation](../simulators/install.md) before attempting a
   real simulation. Recheck solver readiness and retain logs, convergence and
   independent comparison evidence. See [Palace troubleshooting](../troubleshooting/palace.md).

### Picture-reading example

![Historical CPW layout artifact; geometry illustration, not a new GUI screenshot or simulation result](../../assets/fabrication_real_cpw_resonator.layout.png)

This existing layout artifact illustrates the kind of geometry a walkthrough
must explain. Its presence does not certify a new run. In the completed
workbench tutorial, numbered pointers must identify **1: input/units**,
**2: geometry/layer controls**, **3: run status**, and **4: evidence/export**
in the actual application screenshot; pair each pointer with a written action.

## Design from an electrical goal

This CLI example executed successfully on the local Apple Silicon Mac with
Python 3.12.14 on 2026-09-15. Other platform and GUI walkthroughs remain pending.

1. Open `examples/requirements/50ohm_connection.json`. It requests 50 ohms,
   a minimum 8 um gap, a 300 × 500 um footprint and 0.1% target tolerance.
   The 6 GHz operating context does not establish operating bandwidth.
2. Run from the repository root:

   ```sh
   uv run textlayout design examples/requirements/50ohm_connection.json --out out/guidebook/connection --no-solver
   ```

3. Open `out/guidebook/connection/output.png` and the GDS. Read
   `requirements.json` and `intent.json` for requested limits, chosen CPW topology
   and assumptions. Inspect `requirements_verification.json` for each measured
   footprint/target check; do not judge the design from the preview alone.
4. Read `design_review.json` and `report.md`. In the retained local run, the
   analytical impedance error was approximately 0.002%, the layout checks
   passed and the solver status was `SIMULATION_INPUT_PREPARED`. No solver ran.
   The CLI, general verification, requirements verification and report now all
   reflect a failed target consistently when it misses the specified tolerance.
5. On exit 1, inspect the validation error, failed check or
   `requirements_feasibility.json`. Correct the input or reassess its physical
   feasibility; do not silently relax a scientific tolerance. For real extraction,
   install the required solver, check its readiness, then run with
   `--require-simulation` and retain its output and convergence evidence.

**AI prompt example**

> Use the typed electrical-goal workflow to prepare a 50 ohm CPW at a 6 GHz
> operating context with at least 8 um gap, within 300 by 500 um, and 0.1%
> target tolerance. Show the technology assumptions and chosen topology. Run
> without a solver first, return the GDS and all verification/report paths,
> and distinguish the analytical estimate from executed simulation evidence.

This function is available through CLI/API. Its future GUI screenshots and
modern MCP adapter are still pending; do not invent a tool name for this prompt.

## Inspect an S-parameter result before quoting a frequency

1. From the repository root, read a committed two-port example through the
   product parser:

   ```sh
   uv run python -c 'from textlayout.simulation.sparameters import read_sparameters; data = read_sparameters("examples/showcase/02_cpw_50ohm/extraction/capacitance_input/openems_result.s2p"); print(len(data.frequencies_hz), data.frequencies_hz[0], data.frequencies_hz[-1], data.reference_ohm)'
   ```

   The checked local command printed `401 1500000000.0 12000000000.0 50.0`:
   401 samples, a 1.5–12 GHz sweep, and a 50 ohm reference. The file is an
   existing example, not evidence of a new solver run.
2. If parsing raises an error, keep the original file and solver log. Check
   whether the sweep is finite and ordered, whether each `.s2p` row has four
   complex parameter pairs, and whether its option line describes S-parameters.
   Do not quote a resonance or impedance from a rejected or incomplete file.
3. A reported number still needs the solver identity, model inputs, geometry,
   materials, convergence and an independent reference before an accuracy claim.
   The parser only establishes that the data file is structurally usable.

**AI prompt example**

> Read this Touchstone result, report the sweep range, units and reference
> impedance, then check for incomplete rows, non-finite samples and frequency
> ordering. If it fails, show the exact error and retain the original file;
> do not invent a resonance or treat parse success as solver validation.

## Local API walkthrough

1. Start the service from the repository root:

   ```sh
   uv run textlayout serve --host 127.0.0.1 --port 8000
   ```

2. Open `http://127.0.0.1:8000/docs` in your browser and inspect `/health`.
3. Open the `POST /layout/research` operation, choose **Try it out**, and enter
   the JSON from `examples/benchmarks/01_idc_0p6pf/layout.json`.
4. Execute the request. Read equations, assumptions and proposed simulation
   steps before using `/layout/generate`. Use the live `/openapi.json` schema
   for exact request/response fields; [Tool API](../tool_api.md) adds context.
5. Stop the local server with Ctrl+C when finished. A hosted agent cannot access
   this Mac's localhost without an explicitly configured connection.

## AI prompt examples

These are prompts to an agent with project/tool access; tool and solver access
must be verified first. AI text alone is not simulation evidence.

**Discover capabilities**

> List the available Text-to-Layout MCP tools and installed solvers. Distinguish
> supported product functions from legacy tools, and list missing prerequisites.
> Do not start a simulation during discovery.

**Prepare a design**

> Create an IDC targeting 0.6 pF on silicon at 6 GHz with at least 2 um gap.
> Show material assumptions and units first. Use deterministic geometry tools,
> verify the exported layout, and return artifact paths. Prepare solver inputs
> without claiming a simulation ran.

**Validate a real run**

> Check that the required open-source solver is runnable, then execute the
> prepared case. Report its version, inputs, convergence, actual numerical
> result, reference source and comparison error. Preserve a failed or unavailable
> status and its logs; do not substitute an estimate for missing solver evidence.

**Recover work**

> Inspect the existing run and job IDs, resume only supported unfinished work,
> and avoid launching a duplicate. Tell me what completed, what remains and the
> exact next action, with links to evidence.

## MCP and plugin walkthrough contract

The existing plugin config launches the legacy `text-to-gds` server. Root
`.mcp.json` currently assumes the Windows `py -3 -m uv` launcher; it is not
a portable macOS/Linux install recipe. Host-specific launch configuration,
absolute working-directory/package discovery and installation must be tested.

1. Install the documented package/plugin version using the target host's current
   supported flow; record Codex or Claude Code version and OS.
2. Connect the server and inspect `tools/list`. Compare its names and schemas
   with the [catalog](../function-catalog.md).
3. Call the existing `list_simulators` discovery tool with no arguments:

   ```json
   {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_simulators","arguments":{}}}
   ```

   This is a request after a successful MCP initialization handshake, not a
   standalone HTTP endpoint or complete stdio session. The client manages the
   handshake and transport. Inspect the returned content; availability is not
   numerical validation.
4. Use the discovery prompt above, then one bounded geometry example. Validate
   the actual schema before providing arguments; retain host screenshots and
   the resulting artifact/evidence records.
5. Repeat on both plugin hosts; report unsupported or missing capabilities.

## Required illustrated chapters and capture checklist

All rows below are **pending real capture/validation** for the delivered UI.
Do not ship a placeholder as a completed screenshot tutorial.

| Chapter | Required screenshots and numbered pointers | Matching examples |
| --- | --- | --- |
| Windows/macOS/Linux installation | Installer, project selection, readiness and missing dependency recovery | CLI install/help/doctor per OS |
| First design | Prompt, units/material assumptions, validation, geometry preview | IDC CLI command and design AI prompt |
| Edit and inspect | Selected geometry, parameter field, layer visibility, before/after result | CLI DSL validation and matching MCP operation |
| Simulate and recover | Solver choice, execution location, progress, missing solver, failure/retry | Real solver command, job ID and failure AI prompt |
| Compare and export | Convergence, source/reference, numerical error, export destination | Result/evidence inspection and comparison AI prompt |
| Local and online browser | Connection state, local versus hosted run, artifact access | Local server command and authenticated hosted procedure |
| Codex and Claude Code | Plugin installation, MCP discovery, tool invocation, results | `tools/list`, validated `tools/call`, AI prompt |
| Function browser | Search/filter, function details, prerequisites, copy example | Catalog mapping and schema example |

Store original captures under `docs/guidebook/images/`. Pair every annotated
capture with a metadata record naming commit, OS, app/host version, viewport,
theme, date, input case, exact capture steps and numbered callout descriptions.
Keep callouts off important text and numerical evidence. Include alternative
text and a numbered prose explanation; users must not depend on seeing arrows.

Before marking a chapter complete, rerun every command/tool example, check
expected files/status and failures, validate image links and review screenshots
at normal size and 200% zoom. Update screenshots when the documented UI changes.
