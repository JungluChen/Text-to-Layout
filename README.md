# Text-to-Layout

Text-to-Layout converts natural-language chip design requests into typed layout
DSL, deterministic GDS geometry, KLayout-verified artifacts, and honest
simulation evidence — every claim in this README is backed by committed files
and enforced by CI claim validation.

## 30-second demo

One command runs the full closed loop — natural language → intent → tuned Layout DSL → verified geometry → solver preparation (execution if a solver is installed) → honest evidence report:

```bash
textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap and prepare a JoSIM LC/JJ circuit check" --out out/idc_josim_demo
```

The same eight-file contract is available for the new closed-loop paths:

```bash
textlayout prompt "Design a CPW transmission line on silicon at 6 GHz with 50 ohm impedance" --out out/cpw_demo
textlayout prompt "Create a 3 nH spiral inductor with 4 turns" --out out/spiral_demo
```

Generated files in `out/idc_demo/`:

```text
intent.json          parsed design intent (deterministic parser, no LLM/API key)
layout.json          tuned Layout DSL
output.gds           layout artifact
output.svg           preview
output.png           raster preview
verification.json    geometry + design-rule check results
simulation.json      typed simulation evidence (status vocabulary below)
optimization.json    analytical initialization plus solver-aware tuning iterations
simulation/capacitance/input/   FasterCap/FastCap inputs
simulation/capacitance/output/  retained capacitance solver outputs
simulation/josim/circuit.cir    passive LC transient deck
simulation/josim/circuit_jj.cir JJ-ready transient deck when requested
report.md            target-vs-result report with explicit evidence status
```

**Naming:** the repository is *Text-to-Layout*, the installable Python
distribution is `text-to-gds` (historical name), and the supported product
package you import and run is `textlayout`. `textlayout` owns all new CLI, API,
layout, solver, optimization, and reporting code. `text_to_gds` is frozen
legacy compatibility code (the MCP-server surface) and is not the expansion
path.

FasterCap/FastCap performs geometry-based electrostatic capacitance extraction.
JoSIM performs superconducting circuit transient simulation. JoSIM is not an EM
or capacitance field solver and cannot prove that physical IDC geometry meets a
capacitance target. Solver input preparation is not solver execution, and an
analytical estimate is not physical verification.

Current committed showcase evidence includes real FasterCap and FastHenry runs:

<!-- BEGIN GENERATED: headline-evidence -->

<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->

| Quantity | Target | Solver-extracted | Error | Evidence status |
| --- | --- | --- | --- | --- |
| 01_idc_0p6pf capacitance | 0.600000 pF | 0.598641 pF | 0.227% | `PHYSICS_VERIFIED` |
| 02_cpw_50ohm characteristic_impedance | 50.000000 ohm | 49.712535 ohm | 0.575% | `PHYSICS_VERIFIED` |
| 03_idc_cpw_test_structure capacitance | 0.600000 pF | 0.610019 pF | 1.670% | `PHYSICS_VERIFIED` |
| 04_spiral_inductor_3nh inductance | 3.000000 nH | 2.958308 nH | 1.390% | `SIMULATION_EXECUTED` |

Solvers that ran but produced unusable output (no value extracted): `05_quarter_wave_resonator_6ghz`.
<!-- END GENERATED: headline-evidence -->

Example 3 is `PHYSICS_VERIFIED` only for its embedded IDC region. CPW launches,
transitions, resonator behavior, and the full test-chip tile are not full-wave
verified. A solver-owned output must be parsed and compared with its target
before any `PHYSICS_VERIFIED` claim is allowed.

> This project is not fabrication-ready by default. Geometry generation and analytical estimation are supported. Physics verification is only claimed when an external solver is executed and its output is parsed successfully.

## Why this is not AI-random drawing

The natural-language parser is deterministic (no LLM, no API key) and produces
*typed design intent* only. The intent becomes a validated Layout DSL
(pydantic v2), deterministic Python generates every polygon, gdsfactory writes
the GDS, and KLayout — a different code base than the writer — reads the file
back and verifies top cell, bounding box, layers, and per-layer polygon counts.
LangGraph orchestrates the stages and records `workflow_trace.json`, but owns
no geometry and can invent no evidence: a false `PHYSICS_VERIFIED` record is
structurally unconstructible (see `src/textlayout/evidence.py`).

## Workflow

```mermaid
flowchart LR
    A[Prompt] --> B[Intent parser]
    B --> C[Typed Layout DSL]
    C --> D[LangGraph workflow]
    D --> E[gdsfactory geometry]
    E --> F[KLayout readback]
    F --> G[Verification]
    G --> H{Solver route}
    H -->|IDC| I[FasterCap]
    H -->|Spiral| J[FastHenry]
    H -->|CPW / Resonator| K[openEMS]
    I --> L[Parse C]
    J --> M[Parse L/R]
    K --> N[Parse S-parameters]
    L --> O[Target comparison]
    M --> O
    N --> O
    O --> P[Evidence gate]
    P --> Q[Report]
```

## Installation

Python 3.11+ is required.

```bash
git clone https://github.com/JungluChen/Text-to-Layout
cd Text-to-Layout
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev]"
```

Or with `uv`: `uv sync` (Windows: `py -3 -m uv sync`).

Install the repository's agent skills:

```bash
npx skills install JungluChen/Text-to-Layout
```

Install the supported WSL FastHenry build with:

```bash
uv run python scripts/install_fasthenry.py
```

## Required dependencies

```text
Python >= 3.11
klayout      (GDS readback verification)
gdsfactory   (geometry construction and export)
langgraph    (workflow orchestration)
```

## Optional external solvers

```text
FasterCap / FastCap  capacitance extraction (WSL builds are auto-detected on Windows)
openEMS              CPW / resonator S-parameters (input preparation is always available)
FastHenry            spiral inductance (input preparation is always available)
JoSIM                Josephson circuit transient simulation — never geometry capacitance evidence
WRspice / PSCAN2     optional circuit cross-checks
Palace + Gmsh        3D FEM eigenmode/reference simulation (see below)
```

### Optional 3D FEM: Palace + Gmsh

Palace 0.17.0 (Apache-2.0) and Gmsh 4.15.2 (GPL, with upstream exception
wording as applicable) are **optional external tools**. They are not bundled
in the `text-to-gds` wheel, and their source code is never merged into `src/`.
Gmsh is installed through the `mesh` optional dependency as an external GPL
runtime whose source is not vendored into this MIT package. Windows users
should use WSL Ubuntu — the installer drives the pinned Spack release inside
WSL.

**Storage model.** The installer separates auditable artifacts from the large,
reproducible build tree:

```text
.tools/external/sources/
    pinned, SHA-256-verified upstream source archives (committed-adjacent, git-ignored)

.tools/palace/install.json
    the Palace installation identity: version, executable path, and executable SHA-256

$HOME/.cache/textlayout-palace/
    the WSL-native Spack clone, environment, caches, transient build stage,
    and the installed Palace binary (git-ignored, never committed, never in src/)
```

The Spack tree and installed binary live on **native WSL ext4** rather than the
`/mnt/c` 9p mount, because the many-small-file operations of the FEM-stack build
and install stall on the Windows filesystem. Override the native location with
the `TEXTLAYOUT_PALACE_NATIVE_ROOT` environment variable. The pinned archives
and the installation identity remain under `.tools/` for audit; the binaries on
native storage are fully reproducible from those pinned sources.

Installing the tools does **not** make a result physics-verified. Only parsed
Palace-owned output (`eig.csv`, `domain-E.csv`, `error-indicators.csv`, the
`*_resolved.json` configuration sidecar) may become simulation evidence, and
only with passing AMR and numerical-domain-convergence gates; anything else is
reported as `SKIPPED_SOLVER_ABSENT`, `SIMULATION_INVALID`, or
`CONVERGENCE_FAILED` by the evidence contract.

```bash
uv sync --all-extras
uv run python scripts/external/install_palace.py
uv run python scripts/external/check_palace.py
uv run python scripts/external/run_palace_smoke.py
uv run textlayout simulate palace-resonator \
  --out out/palace_resonator_v017
```

Make equivalents:

```bash
make setup-palace
make check-palace
make smoke-palace
make benchmark-palace
```

Details: [external_tools/palace/README.md](external_tools/palace/README.md) ·
[docs/install/palace.md](docs/install/palace.md) ·
[docs/troubleshooting/palace.md](docs/troubleshooting/palace.md) ·
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Run the doctor

```bash
textlayout doctor
```

Checks Python version, `textlayout`/gdsfactory/KLayout/LangGraph imports,
FasterCap discovery, optional solver availability, and output-directory write
permission. A missing solver is reported as *absent* — execution will be
skipped honestly; it is never an environment failure.

## Six research-grade examples

Generated by `python scripts/generate_showcase_examples.py --force` through the
full LangGraph pipeline; every cell below links to committed artifacts under
[`examples/showcase/`](examples/showcase/) and is enforced by
`scripts/validate_readme_claims.py` and `tests/textlayout_suite/test_showcase_examples.py`.

<!-- BEGIN GENERATED: showcase-table -->

<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->

| # | Target | Prompt | Output | Step Results | Evidence Status |
|---|--------|--------|--------|--------------|-----------------|
| 1 | 0.6 pF interdigitated capacitor for a lumped LC / JPA front end | Create a 0.6 pF interdigitated capacitor on silicon at 6 GHz with 2 um minimum gap, 4 um finger width, and two RF ports. | [![IDC](examples/showcase/01_idc_0p6pf/output.png)](examples/showcase/01_idc_0p6pf/output.svg) | [report](examples/showcase/01_idc_0p6pf/report.md) · [simulation](examples/showcase/01_idc_0p6pf/simulation.json) · [trace](examples/showcase/01_idc_0p6pf/workflow_trace.json) · [evidence](examples/showcase/01_idc_0p6pf/evidence/canonical.json) | **PHYSICS_VERIFIED** — FasterCap extracted 0.598641 pF versus 0.600000 pF target; 0.227% error, within the 5% tolerance. Convergence: `fastercap_automatic_refinement`. **NOT_FABRICATION_READY** |
| 2 | 50 ohm coplanar-waveguide feedline for microwave routing | Create a 50 ohm CPW feedline on silicon at 6 GHz with ground-signal-ground geometry and labeled input/output ports. | [![CPW](examples/showcase/02_cpw_50ohm/output.png)](examples/showcase/02_cpw_50ohm/output.svg) | [report](examples/showcase/02_cpw_50ohm/report.md) · [simulation](examples/showcase/02_cpw_50ohm/simulation.json) · [trace](examples/showcase/02_cpw_50ohm/workflow_trace.json) · [evidence](examples/showcase/02_cpw_50ohm/evidence/canonical.json) | **PHYSICS_VERIFIED** — openEMS+scikit-rf extracted 49.712535 ohm versus 50.000000 ohm target; 0.575% error, within the 5% tolerance. Convergence: `fdtd_energy_decay_and_excitation_support`. **NOT_FABRICATION_READY** |
| 3 | 0.6 pF IDC with CPW launches for on-chip measurement | Create a test structure with a 0.6 pF IDC connected to two 50 ohm CPW feedlines, with GSG-style launch regions, ground clearance, and measurement-friendly port labels. | [![TestStructure](examples/showcase/03_idc_cpw_test_structure/output.png)](examples/showcase/03_idc_cpw_test_structure/output.svg) | [report](examples/showcase/03_idc_cpw_test_structure/report.md) · [simulation](examples/showcase/03_idc_cpw_test_structure/simulation.json) · [trace](examples/showcase/03_idc_cpw_test_structure/workflow_trace.json) · [evidence](examples/showcase/03_idc_cpw_test_structure/evidence/canonical.json) | **PHYSICS_VERIFIED** — FasterCap extracted 0.610019 pF versus 0.600000 pF target; 1.670% error, within the 5% tolerance. Convergence: `fastercap_automatic_refinement`. **NOT_FABRICATION_READY** |
| 4 | Compact planar spiral inductor targeting 3 nH | Create a compact planar spiral inductor targeting 3 nH with 4 turns, 4 um trace width, 2 um spacing, and two labeled ports. | [![SpiralInductor](examples/showcase/04_spiral_inductor_3nh/output.png)](examples/showcase/04_spiral_inductor_3nh/output.svg) | [report](examples/showcase/04_spiral_inductor_3nh/report.md) · [simulation](examples/showcase/04_spiral_inductor_3nh/simulation.json) · [trace](examples/showcase/04_spiral_inductor_3nh/workflow_trace.json) · [evidence](examples/showcase/04_spiral_inductor_3nh/evidence/canonical.json) | **SIMULATION_EXECUTED** — fasthenry extracted 2.958308 nH versus 3.000000 nH target (-1.390%), but no convergence criterion is evidenced, so it is **not** physics-verified. **NOT_FABRICATION_READY** |
| 5 | 6 GHz quarter-wave CPW resonator layout candidate | Create a 6 GHz quarter-wave resonator on silicon with a weakly coupled input line, open end, shorted end, and port labels. | [![QuarterWaveResonator](examples/showcase/05_quarter_wave_resonator_6ghz/output.png)](examples/showcase/05_quarter_wave_resonator_6ghz/output.svg) | [report](examples/showcase/05_quarter_wave_resonator_6ghz/report.md) · [simulation](examples/showcase/05_quarter_wave_resonator_6ghz/simulation.json) · [trace](examples/showcase/05_quarter_wave_resonator_6ghz/workflow_trace.json) · [evidence](examples/showcase/05_quarter_wave_resonator_6ghz/evidence/canonical.json) | **SIMULATION_INVALID** — openEMS+scikit-rf ran to completion, but its output failed a physical-sanity check: openems_result.s2p: 401/401 S-parameter samples are non-finite (NaN/Inf) — the solver produced no usable output (typically zero injected port energy); refusing to extract numbers from it No value was extracted. **NOT_FABRICATION_READY** |
| 6 | Multi-device comparison tile (IDC + CPW + spiral + marks + title) | Create a 2 mm by 2 mm research test chip tile containing a 0.6 pF IDC, a 50 ohm CPW line, a spiral inductor, alignment marks, port labels, and a title text label. | [![TestChip](examples/showcase/06_research_test_chip/output.png)](examples/showcase/06_research_test_chip/output.svg) | [report](examples/showcase/06_research_test_chip/report.md) · [simulation](examples/showcase/06_research_test_chip/simulation.json) · [trace](examples/showcase/06_research_test_chip/workflow_trace.json) · [evidence](examples/showcase/06_research_test_chip/evidence/canonical.json) | **ANALYTICAL_ONLY** for scope `full_tile`. **NOT_FABRICATION_READY** |
<!-- END GENERATED: showcase-table -->

No example is fabrication-ready. All generated layouts are research candidates
requiring process-specific DRC, expert review, EM correlation, and measurement
validation. Every example is marked **NOT_FABRICATION_READY**.
Each folder carries the full step chain: `prompt.txt`, `intent.json`,
`layout.json`, `output.gds/.svg/.png`, `klayout_readback.json`,
`verification.json`, `simulation.json`, `optimization.json`,
`workflow_trace.json`, `report.md`, and a per-example `README.md`.

## Evidence status vocabulary

| Status | Meaning |
| --- | --- |
| `GEOMETRY_PASS` | Layout generated and KLayout readback passed |
| `ANALYTICAL_ONLY` | Equation estimate only, no solver execution |
| `SIMULATION_INPUT_PREPARED` | Solver input files generated |
| `SKIPPED_SOLVER_ABSENT` | Solver not found, execution skipped honestly |
| `SIMULATION_EXECUTED` | Solver executed and output was parsed |
| `PHYSICS_VERIFIED` | Solver result meets target tolerance |
| `FAILED` | Workflow failed |
| `NOT_FABRICATION_READY` | Not approved for fabrication |

## What is verified and what is not

<!-- BEGIN GENERATED: evidence-summary -->

<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->

| Showcase | Status | Confidence | Scope | Evidence |
| --- | --- | --- | --- | --- |
| 01_idc_0p6pf | `PHYSICS_VERIFIED` | `VERIFIED` | idc_electrodes | extracted `0.598641` pF versus `0.600000` pF target; `-0.227%` error |
| 02_cpw_50ohm | `PHYSICS_VERIFIED` | `VERIFIED` | through_line_center_conductor | extracted `49.712535` ohm versus `50.000000` ohm target; `-0.575%` error |
| 03_idc_cpw_test_structure | `PHYSICS_VERIFIED` | `VERIFIED` | embedded_idc_region_only | extracted `0.610019` pF versus `0.600000` pF target; `+1.670%` error |
| 04_spiral_inductor_3nh | `SIMULATION_EXECUTED` | `SIMULATED` | spiral_winding | extracted `2.958308` nH versus `3.000000` nH target; `-1.390%` error |
| 05_quarter_wave_resonator_6ghz | `SIMULATION_INVALID` | `NONE` | resonator_plus_coupler | no value extracted — openems_result.s2p: 401/401 S-parameter samples are non-finite (NaN/Inf) — the solver produced no usable output (typically zero injected port energy); refusing to extract numbers from it |
| 06_research_test_chip | `ANALYTICAL_ONLY` | `ANALYTICAL` | full_tile | no solver-extracted value |

**PHYSICS_VERIFIED** (3): `01_idc_0p6pf`, `02_cpw_50ohm`, `03_idc_cpw_test_structure` — a solver ran, its output re-parses to the value shown, a convergence criterion was met, and the result is inside tolerance.

**SIMULATION_EXECUTED** (1): `04_spiral_inductor_3nh` — a solver ran and produced a finite value, but no convergence criterion is evidenced, so the result is not verified.

**SIMULATION_INVALID** (1): `05_quarter_wave_resonator_6ghz` — a solver ran and its output failed a physical-sanity check. No quantity was extracted.

**ANALYTICAL_ONLY** (1): `06_research_test_chip` — no solver result for this scope.

**Not claimed at all:** self-resonance, loss/Q, EM transitions, JJ physics on generic placeholders, and the fabrication readiness of anything. No example is fabrication-ready.
<!-- END GENERATED: evidence-summary -->

## Component support matrix

Validated in CI by `scripts/validate_readme_claims.py` — every "yes" below must be backed by committed code, tests, and artifacts, or the build fails.

| Component            | Geometry | Analytical estimate                                                | Solver input                                      | Solver executed                                                    | Physics verified                                                 | Status                                                                 |
| -------------------- | -------- | ------------------------------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| IDC                  | yes      | yes (Bahl/Alley)                                                   | yes (FasterCap/FastCap)                           | environment-dependent (runs when installed; honest skip otherwise) | environment-dependent (never claimed without solver output)      | Supported — full closed loop                                          |
| CPW                  | yes      | yes (scikit-rf Ghione/Naldi with`[rf]`; Simons/Hilberg fallback) | yes (runnable openEMS/CSXCAD Octave model)        | environment-dependent (external openEMS stack)                     | environment-dependent (target/tolerance gated)                   | Supported — conditional solver closed loop                            |
| SpiralInductor       | yes      | yes (Mohan/Wheeler)                                                | yes (FastHenry)                                   | environment-dependent (external FastHenry)                         | environment-dependent (target/tolerance gated)                   | Supported — conditional solver closed loop                            |
| QuarterWaveResonator | yes      | yes (λ/4 line theory)                                             | yes (runnable openEMS/CSXCAD Octave model)        | environment-dependent (external openEMS stack)                     | environment-dependent (target/tolerance gated)                   | Supported — conditional solver closed loop                            |
| SQUID                | yes      | yes (RSJ/Josephson + rectangular-loop estimate)                    | conditional (JoSIM deck requires explicit Ic/R/C) | environment-dependent (JoSIM + explicit inputs)                    | no by default (circuit extraction is not geometry qualification) | Experimental — Option B; generic JJ geometry is not foundry-qualified |
| TestStructure        | yes      | yes (Bahl IDC + conformal CPW feed)                                | yes (FasterCap on the embedded IDC region only)   | environment-dependent (runs when installed; honest skip otherwise) | environment-dependent (IDC region only; transitions never claimed) | Supported — measurement structure with documented extraction region  |
| TestChip             | yes      | yes (per-sub-device analytical models)                             | yes (IDC, CPW, spiral sub-block decks)             | sub-block only (FasterCap IDC + FastHenry spiral); no full-tile run | no for the full tile                                             | Supported — sub-block evidence map; whole-tile coupling not modeled  |

IDC status: geometry **yes**; analytical estimate **yes**; FasterCap
input **yes**; FasterCap execution **conditional**; physics verification
**conditional**; fabrication ready **no**.

The compact IDC contract used by automated claim validation is repeated here
without presentation padding:

| IDC | yes | yes (Bahl/Alley) | yes (FasterCap/FastCap) | environment-dependent (runs when installed; honest skip otherwise) | environment-dependent (never claimed without solver output) | Supported - full closed loop |

Install optional Python RF support with `pip install "text-to-gds[rf]"`.
openEMS, FastHenry, FasterCap/FastCap, and JoSIM remain separately installed
external executables; no solver source is vendored or linked into this project.

## Trust and reproducibility

Live project status (package version, CLI surface, solver-backed vs
analytical vs skipped examples, EPR/measurement support, PDK readiness) is
**generated, never hand-edited**: run `python scripts/generate_project_status.py`
and read [PROJECT_STATUS.md](PROJECT_STATUS.md) /
`out/evidence/project_status.json`. `python scripts/check_project_claims.py`
fails CI when any hand-written doc drifts from that ground truth (fake
PHYSICS_VERIFIED claims, stale test counts, version drift, unnegated
fabrication-readiness language).

The honesty claims above are backed by committed, checkable artifacts:

- [CLEAN_ROOM_VERIFICATION.md](CLEAN_ROOM_VERIFICATION.md) — what was verified from a fresh clone (local CLI / API / plugin-style). This repo is **not** claimed to be "public ChatGPT plugin ready"; that requires a public HTTPS deployment (see [docs/public_gpt_action_deployment.md](docs/public_gpt_action_deployment.md)).
- [docs/artifact_policy.md](docs/artifact_policy.md) — why committed benchmark artifacts are byte-reproducible (normalized timestamps, stable GDS top-cell names, `gds2_write_timestamps=False`).
- [examples/acceptance/](examples/acceptance/) — three physics-fit acceptance packets: an infeasible target that is *refused* (5 MHz LC), a feasible resonator, and an auto-sized IDC.

## What it does

Text-to-Layout is not "AI randomly draws layout." The AI researches the target and proposes a typed Layout DSL. Deterministic code owns geometry, layer mapping, ports, verification, simulation preparation, and export.

```text
Research
  -> first-principles model
  -> initial parameter calculation
  -> Layout DSL (Pydantic v2)
  -> deterministic geometry
  -> gdsfactory Component
  -> verification gate
  -> SVG / PNG / GDS / JSON
  -> open-source simulation preparation or execution
  -> evidence-backed report
```

If required verification fails, final geometry artifacts are not exported.

> **Warning:** Generated layouts are design candidates, not fabrication-ready masks. Final fabrication requires process-specific DRC, EM simulation, expert review, and foundry or lab rule validation.

## Status vocabulary

This project uses explicit status labels to avoid misleading claims:

| Label                               | Meaning                                                         |
| ----------------------------------- | --------------------------------------------------------------- |
| **GEOMETRY PASS**             | Files exist, parameters verified, geometry is valid             |
| **ANALYTICAL ONLY**           | Equations computed; no solver executed                          |
| **SIMULATION INPUT PREPARED** | Solver input files exist; solver not executed                   |
| **SIMULATION EXECUTED**       | Solver ran and produced non-empty output file                   |
| **PHYSICS VERIFIED**          | Extracted values compared against target with tolerance         |
| **FABRICATION READY**         | Process-specific DRC, EM simulation, and expert review complete |
| **INFEASIBLE**                | Target not achievable under realistic constraints               |

**No `examples/benchmarks/` default artifact is PHYSICS VERIFIED, and nothing in this repository is FABRICATION READY.**

<!-- BEGIN GENERATED: verified-list -->

The `PHYSICS_VERIFIED` artifacts are [01_idc_0p6pf](examples/showcase/01_idc_0p6pf/) (FasterCap, scope `idc_electrodes`), [02_cpw_50ohm](examples/showcase/02_cpw_50ohm/) (openEMS+scikit-rf, scope `through_line_center_conductor`), [03_idc_cpw_test_structure](examples/showcase/03_idc_cpw_test_structure/) (FasterCap, scope `embedded_idc_region_only`). Each has a convergence criterion recorded in its canonical evidence. Claim validation enforces each scope.
<!-- END GENERATED: verified-list -->

## Legacy analytical benchmarks

> **Warning:** These are older analytical benchmark packets and should not be confused with the current research-grade showcase under [`examples/showcase/`](examples/showcase/).

Geometry Status | Simulation Status | Evidence Status | Fabrication Status

Each benchmark shows honest status across geometry, simulation, evidence, and fabrication.

| # | Target                                                                  | Prompt                                                                              | Output                                                                                                                            | Geometry Status                                                                                             | Simulation Status                                                                         | Evidence Status                                                                                                                | Fabrication Status       |
| - | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| 1 | [IDC capacitor](examples/benchmarks/01_idc_0p6pf/)                       | Create a 0.6 pF IDC with 22 finger pairs, 4 um width, 2 um gap, and 250 um overlap. | [![IDC](examples/benchmarks/01_idc_0p6pf/output.png)](examples/benchmarks/01_idc_0p6pf/output.svg)                                 | **GEOMETRY PASS** (parameters, width, gap, layer, bbox, ports, gdsfactory lowering, KLayout readback) | **SIMULATION INPUT PREPARED** (FasterCap/FastCap input exists; solver not executed) | **ANALYTICAL ONLY** (Bahl/Alley estimate = 0.6983 pF; target error = 16.4%)                                              | **NOT READY**      |
| 2 | [50 ohm CPW](examples/benchmarks/02_cpw_50ohm/)                          | Create a 50 ohm CPW on silicon.                                                     | [![CPW](examples/benchmarks/02_cpw_50ohm/output.png)](examples/benchmarks/02_cpw_50ohm/output.svg)                                 | **GEOMETRY PASS** (dimensions, GSG ports, layers, bbox, gdsfactory lowering)                          | **SIMULATION INPUT PREPARED** (openEMS manifest exists; solver not executed)        | **ANALYTICAL ONLY** (Simons conformal mapping estimate = 50.04 ohm; EM correlation pending)                              | **NOT READY**      |
| 3 | [Spiral inductor](examples/benchmarks/03_spiral_inductor/)               | Create a compact planar spiral with target inductance.                              | [![Spiral](examples/benchmarks/03_spiral_inductor/output.png)](examples/benchmarks/03_spiral_inductor/output.svg)                  | **GEOMETRY PASS** (typed parameters, width, spacing, ports, bbox, gdsfactory lowering)                | **SIMULATION INPUT PREPARED** (FastHenry input exists; solver not executed)         | **ANALYTICAL ONLY** (Mohan/Wheeler estimate; no solver result)                                                           | **NOT READY**      |
| 4 | [Quarter-wave resonator](examples/benchmarks/04_quarter_wave_resonator/) | Create a 6 GHz quarter-wave CPW resonator.                                          | [![Resonator](examples/benchmarks/04_quarter_wave_resonator/output.png)](examples/benchmarks/04_quarter_wave_resonator/output.svg) | **GEOMETRY PASS** (open/short topology, coupling gap, GSG ports, bbox)                                | **SIMULATION INPUT PREPARED** (openEMS input exists; solver not executed)           | **ANALYTICAL ONLY** (L = vp/(4f) gives 4918.5 um; EM result pending)                                                     | **NOT READY**      |
| 5 | [SQUID loop](examples/benchmarks/05_squid_loop/)                         | Create a symmetric two-junction SQUID test structure.                               | [![SQUID](examples/benchmarks/05_squid_loop/output.png)](examples/benchmarks/05_squid_loop/output.svg)                             | **GEOMETRY PASS** (candidate; symmetry, two JJ placeholders, loop area, ports, layers)                | **NOT READY** (no foundry JJ-stack solver possible)                                 | **ANALYTICAL ONLY** (flux quantization model; generic JJ placeholders not foundry-qualified)                             | **NOT READY**      |
| 6 | [5 MHz LC resonator](examples/benchmarks/06_lc_5mhz_resonator/)          | Design a lumped LC resonator layout that targets 5 MHz resonance frequency.         | **NOT GENERATED** (infeasible target)                                                                                       | **NOT GENERATED** (no layout created)                                                                 | **NOT APPLICABLE** (no simulation possible)                                         | **INFEASIBLE** (required LC = 1.013×10⁻¹⁵ s² exceeds on-chip limits by 100-1000×; 159 MHz is the minimum feasible) | **NOT APPLICABLE** |

### Benchmark artifacts

Each benchmark folder contains:

```text
prompt.md             original request
layout.json           Layout DSL and provenance
output.svg/.png       human previews
output.gds            primary layout artifact
output.json           geometry IR and metadata
verification.json     measured checks and limits
analytical_estimate.md equations and calculated starting values
simulation_plan.md    readiness level, prepared inputs, expected extraction
evidence.md           equations, assumptions, references, limitations
report.md             target comparison and simulation status
```

### IDC benchmark details

- **Target:** 0.6 pF
- **Bahl/Alley estimate with 22 finger pairs:** 0.6983 pF
- **Error from target:** 16.4%
- **Proposed finger pairs for closer target:** 20
- **Proposed estimate:** 0.6319 pF
- **Current layout uses 22 finger pairs** because that was the user prompt
- **This is not yet EM verified**
- **For this legacy packet, FasterCap/FastCap input exists and no solver was executed**
- **Q3D/HFSS/Sonnet cross-check is still required** before fabrication

### 5 MHz LC resonator benchmark (INFEASIBLE)

- **Target:** 5 MHz resonance frequency
- **Required LC product:** 1.013×10⁻¹⁵ s²
- **Best achievable on-chip:** L = 10 nH, C = 100 pF → f0 = 159 MHz (31× higher)
- **Status:** INFEASIBLE for on-chip layout
- **Reason:** Required component values exceed practical limits by 100-1000×
- **Parasitic effects:** Wirebond/stray LC shifts resonance by >50%
- **Q-factor:** On-chip spiral Q ~ 2-10 at 5 MHz (too low)
- **Area penalty:** ~0.13 mm² minimum (vs. ~0.001 mm² for GHz circuits)
- **Alternative:** Discrete components, crystal, or active LC simulation

**This benchmark tests whether Text-to-Layout can reason about physical feasibility, not just draw layouts.**

### Simulation readiness

| Level      | Meaning                                    | Status                                          |
| ---------- | ------------------------------------------ | ----------------------------------------------- |
| 0          | Analytical estimate only                   | All benchmarks start here                       |
| 1          | Geometry generated and verified            | IDC, CPW, Spiral, Resonator, SQUID achieve this |
| 2          | Solver input prepared                      | IDC, CPW, Spiral, Resonator achieve this        |
| 3          | Solver executed and result artifact exists | Showcase examples 01 and 03 ([examples/showcase/](examples/showcase/)) |
| 4          | Result compared against target             | Showcase examples 01 and 03                     |
| 5          | Optimization loop implemented              | Showcase examples 01 and 03 (bounded solver-in-the-loop retune) |
| INFEASIBLE | Target not achievable                      | **5 MHz LC resonator**                    |

**No `examples/benchmarks/` default artifact is Level 3 or higher**; the solver-executed levels are reached only by the committed showcase examples. SQUID is Level 1 because a foundry-qualified junction stack is absent.

## What Text-to-CAD taught this project

[earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) makes
its value obvious through a visual README, one prompt per benchmark, linked
benchmark test cases, one-line skill installation, local preview tooling, and
self-contained skill runtimes.

Text-to-Layout adopts the same reader-facing clarity and reproducibility. It
does not copy mechanical B-rep logic: IC layout needs named process layers,
minimum features, electrical ports, substrate assumptions, parasitic
analysis, EM extraction, and evidence status that distinguishes analytical,
planned, and executed work. See the
[full study](docs/lessons_from_text_to_cad.md).

## Supported generation

| Component              | Status                          | Notes                                                                                                |
| ---------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| IDC                    | Geometry ready, analytical only | Typed DSL, analytical starting model, ports, GDS/SVG/PNG/JSON, verification and evidence reports     |
| CPW                    | Conditional solver closed loop  | Typed DSL, GSG ports, scikit-rf correlation, runnable openEMS model, parsed S-parameters             |
| Spiral                 | Conditional solver closed loop  | Typed square spiral, Mohan estimate, FastHenry input, parsed`Zc.mat`                               |
| Quarter-wave resonator | Conditional solver closed loop  | Explicit open/short topology, runnable openEMS model, parsed resonance                               |
| SQUID                  | Option B experimental           | Symmetric loop, analytical L/Josephson estimates, conditional JoSIM RCSJ deck; not foundry-qualified |
| Test structure         | Conditional solver closed loop  | IDC + CPW launches; FasterCap extracts the documented IDC region only                                |
| Test chip tile         | Geometry + readback only        | IDC + CPW + spiral + alignment marks + stroke-font title; per-sub-device analytical estimates        |

## Generate the IDC example

```bash
textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/idc
```

The command writes the requested geometry plus `*.layout.json`, `*.verification.json`, `*.evidence.md`, and `*.report.md` sidecars. A failed pre-export check returns exit code 2 and writes no final geometry artifact.

## Regenerate benchmarks

```bash
py -3 -m uv run python scripts/generate_benchmarks.py
py -3 -m uv run python scripts/check_benchmarks.py
```

Use `--strict` in CI when every benchmark must be complete. Without it, explicit TODO rows are skipped and cannot acquire fake output files.

## Run verification

```bash
textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json
```

Checks cover typed required parameters, positive dimensions, minimum width and gap, layer mapping, bounding box, ports, geometry spacing, research/equation/reference presence, simulation-plan presence, gdsfactory component sanity, and final file existence.

## Run the API/plugin server

```bash
textlayout serve --host 127.0.0.1 --port 8000
# or
py -3 -m uv run uvicorn textlayout.backend.app:create_app --factory
```

Interactive OpenAPI docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

| Method | Endpoint                      | Purpose                                                                    |
| ------ | ----------------------------- | -------------------------------------------------------------------------- |
| GET    | `/health`                   | Discover generators, technologies, and formats                             |
| POST   | `/layout/research`          | Produce equations, assumptions, references, estimates, and simulation plan |
| POST   | `/layout/generate`          | Research, build, verify, and export requested artifacts                    |
| POST   | `/layout/verify`            | Run geometry/process checks without export                                 |
| POST   | `/layout/export?format=gds` | Export one verified artifact                                               |
| POST   | `/layout/simulate`          | Prepare or explicitly execute a supported open-source simulation           |
| POST   | `/layout/benchmark`         | Generate a complete benchmark packet                                       |
| POST   | `/layout/report`            | Return evidence, verification, files, and simulation steps                 |

```bash
curl -s -X POST http://127.0.0.1:8000/layout/generate \
  -H "Content-Type: application/json" \
  --data-binary @examples/benchmarks/01_idc_0p6pf/layout.json
```

See [tool API](docs/tool_api.md), [OpenAPI usage](docs/openapi_usage.md), and [plugin manifest](plugin_manifest.example.json).

## Layout DSL

```json
{
  "component": "IDC",
  "technology": "generic_2metal",
  "target": {"capacitance_pf": 0.6, "frequency_ghz": 6.0},
  "parameters": {
    "finger_pairs": 22,
    "finger_width_um": 4,
    "gap_um": 2,
    "overlap_um": 250,
    "bus_width_um": 25,
    "metal_layer": "M1"
  },
  "rules": {"min_width_um": 2, "min_gap_um": 2},
  "outputs": {"gds": true, "svg": true, "png": true, "json": true, "report": true},
  "evidence": {
    "analytical_model": "Bahl/Alley IDC estimate",
    "simulation_required": true
  }
}
```

## Skills

| Skill                                                                       | Enforces                                                |
| --------------------------------------------------------------------------- | ------------------------------------------------------- |
| [`layout-research`](skills/layout-research/SKILL.md)                       | Research and first-principles reasoning before geometry |
| [`gdsfactory-layout`](skills/gdsfactory-layout/SKILL.md)                   | DSL-first deterministic gdsfactory generation           |
| [`layout-verification`](skills/layout-verification/SKILL.md)               | Pre-export and post-export gates                        |
| [`layout-simulation-evidence`](skills/layout-simulation-evidence/SKILL.md) | Honest simulation planning and solver provenance        |
| [`jpa-design-simulation`](skills/jpa-design-simulation/SKILL.md)           | Official JPA design-to-simulation workflow guide        |

## Open-source simulation workflow

Open-source tools are the default base workflow. Commercial tools remain optional correlation/signoff connectors.

| Target                         | Open-source path                                 | Current status                                                                  |
| ------------------------------ | ------------------------------------------------ | ------------------------------------------------------------------------------- |
| IDC capacitance                | FasterCap/FastCap; Elmer as a future cross-check | Input preparation implemented; execution and physics verification are conditional |
| CPW and resonator S-parameters | openEMS + scikit-rf                              | Runnable Octave/CSXCAD model, guarded execution, Touchstone parsing             |
| Spiral L/R/Q                   | FastHenry/FastHenry2                             | Input generation, guarded execution,`Zc.mat` parsing                          |
| SQUID circuit response         | JoSIM                                            | Conditional RCSJ deck, guarded execution, CSV parsing; explicit Ic/R/C required |
| 3D FEM eigenmode / reference   | Palace + Gmsh                                    | Pinned Palace 0.17.0 WSL/Spack install, AMR quarter-wave benchmark, honest gates |

Prepare IDC input without claiming a result:

```bash
py -3 -m uv run python simulation/idc_fastercap/generate_fastercap_input.py \
  examples/benchmarks/01_idc_0p6pf/layout.json \
  --out examples/benchmarks/01_idc_0p6pf/simulation
```

Attempt execution; this returns `status=skipped` and exit code 2 when the solver is absent:

```bash
py -3 -m uv run python simulation/idc_fastercap/run_fastercap.py \
  examples/benchmarks/01_idc_0p6pf/layout.json
```

### FasterCap/FastCap on Windows via WSL (Ubuntu)

FasterCap is built and executed as a Linux ELF binary. On Windows, run it from Ubuntu/WSL (the binary under `.tools/FasterCap/bin/FasterCap` is not a Windows `.exe`).

Build and verify (Windows):

```bash
python scripts/bootstrap_simulators.py --tools-dir .tools
python scripts/check_simulators.py --tools-dir .tools
```

If WSL `sudo` requires a password, follow the manual steps printed by the bootstrap. The essential WSL flow is:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake pkg-config libwxgtk3.2-dev git file
cd /path/to/text-to-gds/.tools/FasterCap
rm -rf build
cmake -S . -B build -DFASTFIELDSOLVERS_HEADLESS=ON -DCMAKE_BUILD_TYPE=Release -DwxWidgets_CONFIG_EXECUTABLE="$(which wx-config)" -DCMAKE_CXX_FLAGS="$(wx-config --cxxflags)"
cmake --build build -j"$(nproc)"
cp -f build/FasterCap bin/FasterCap
chmod +x bin/FasterCap
file bin/FasterCap
./bin/FasterCap -bv
```

Notes:

- `file bin/FasterCap` must report an ELF executable (not `relocatable`).
- FasterCap does not accept `--help`; use `-bv` (version) or `-b?` (console usage).
- This repository applies a local-only CMake patch in `.tools/FasterCap/CMakeLists.txt` with markers `# TEXTLAYOUT LOCAL PATCH BEGIN/END` and keeps a backup at `.tools/FasterCap/CMakeLists.txt.textlayout.bak`.

Run the IDC capacitance extraction from WSL (Ubuntu):

```bash
cd /path/to/text-to-gds
sudo apt-get install -y python3-venv python3.12-venv python3-pip
python3 -m venv .wsl-venv
source .wsl-venv/bin/activate
python -m pip install -U pip
pip install pydantic numpy pyyaml pillow matplotlib trimesh
PYTHONPATH=src python simulation/idc_fastercap/run_fastercap.py examples/benchmarks/01_idc_0p6pf/layout.json --out workspace/fastercap_work --executable .tools/FasterCap/bin/FasterCap
```

Success is reported as `status="executed"` and `evidence_level="CAPACITANCE_EXTRACTED"` with a real `simulation_result.json` written under the `--out` directory.

- [HFSS](simulation/hfss_workflow.md)
- [Q3D](simulation/q3d_workflow.md)
- [ADS](simulation/ads_workflow.md)
- [Sonnet](simulation/sonnet_workflow.md)

## Simulator Setup

Fresh clone → working simulators in three commands:

```bash
make setup-simulators    # install/detect JoSIM; detect PSCAN2/WRspice (never blocks on them)
make check-simulators    # availability table; exit 0 even when optional simulators are absent
make demo-jpa            # JPA prompt -> layout -> verification -> extraction prep -> circuit sims
```

Windows without `make`: `python scripts/bootstrap_simulators.py`,
`python scripts/check_simulators.py`, then the `textlayout prompt` command from
the Makefile (or `./scripts/install_simulators.ps1`).

What to expect:

- **JoSIM is the first-priority backend.** The bootstrap installs it
  automatically from the official MIT-licensed releases (or builds from
  source, or prints exact manual steps). Everything lands in the git-ignored
  `.tools/` directory — no binaries are ever committed.
- **PSCAN2 and WRspice are optional.** They are detected if present
  (`TEXTLAYOUT_PSCAN2` / `TEXTLAYOUT_WRSPICE`, `.tools/`, PATH, or Python
  import for PSCAN2) and reported as `manual_install_required` if not.
  Missing PSCAN2/WRspice never blocks setup or the demo.
- **Honesty is unchanged by installation.** JoSIM/PSCAN2/WRspice are circuit
  simulators, not EM capacitance solvers — FasterCap/FastCap is still needed
  for geometry-level capacitance extraction. An installed simulator does not
  make anything `PHYSICS_VERIFIED`: that label requires a real extraction
  *and* a real simulation, both within declared tolerances. A real JoSIM LC
  run yields at most `JOSIM_RESONANCE_CHECKED`.
- Strict mode: `TEXTLAYOUT_STRICT_SIMULATORS=1`, the scripts' `--strict`
  flag, or `make demo-jpa-strict` turn missing simulators into nonzero exits.
- Details: [docs/simulators/install.md](docs/simulators/install.md) ·
  [troubleshooting](docs/simulators/troubleshooting.md) ·
  [licenses](docs/simulators/licenses.md) ·
  `make docker-simulators` for the reproducible Docker route.

## Circuit-level superconducting simulators (JoSIM / PSCAN2 / WRspice)

Two different physics questions, two different tool families — never mixed:

| Tool | Role | Boundary |
| --- | --- | --- |
| **FasterCap/FastCap** | Geometry-level electrostatic capacitance extraction from the drawn IDC polygons | The only acceptable evidence that the physical geometry has its target capacitance |
| **JoSIM** | Superconducting circuit transient simulation (RCSJ junctions, LC, SQUID) | Validates circuit behaviour from already-known L/C/JJ parameters; never a field solver |
| **PSCAN2** | Superconducting circuit transient simulation / margins / optimization (own HDL, normalised units, Python-driven) | Same boundary as JoSIM; not a SPICE dialect — templates are generated separately |
| **WRspice** | SPICE-family transient simulation with native Josephson-junction support | Same boundary as JoSIM; JJ syntax follows the published SNAIL-TWPA deck (see below) |
| **JosephsonCircuits.jl** | Future optional frequency-domain / harmonic-balance backend | Not required now; not wired into `textlayout` |

Background: the adapter design clean-rooms ideas from
[Levochkina et al., arXiv:2402.12037](https://arxiv.org/abs/2402.12037) and its
companion repository — reviewed in
[docs/references/jtwpa_numerical_simulations_review.md](docs/references/jtwpa_numerical_simulations_review.md).

### Install and detection

Each backend is found via an environment variable first, then common
executable names on `PATH` (PSCAN2 also via `import pscan2`):

| Backend | Environment variable | Fallback detection | Install |
| --- | --- | --- | --- |
| JoSIM | `TEXTLAYOUT_JOSIM` | `josim-cli`, `josim` | https://github.com/JoeyDelp/JoSIM |
| PSCAN2 | `TEXTLAYOUT_PSCAN2` | `pip install pscan2` (import check) | http://pscan2sim.org/ |
| WRspice | `TEXTLAYOUT_WRSPICE` | `wrspice`, `wrspice64` | http://wrcad.com/xictools/ |

### Usage modes

```bash
# Prepare-only: generate decks/runners for all three backends, execute nothing
py -3 -m uv run textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap, extract capacitance if possible, then prepare JoSIM, PSCAN2, and WRspice LC resonance checks with 0.3 nH inductance" --out out/idc_multi_sim_demo --no-solver

# Execute-if-available (default): run whichever simulators are installed,
# honestly report SKIPPED_*_ABSENT for the rest
py -3 -m uv run textlayout prompt "..." --out out/idc_multi_sim_demo

# Strict: exit non-zero (3) when a requested simulator is not installed
py -3 -m uv run textlayout prompt "..." --out out/idc_multi_sim_demo --strict-simulation
```

Outputs land under `out/<dir>/simulation/{josim,pscan2,wrspice}/` with a
`manifest.json` each, plus the aggregated `simulation.json` and `report.md`.

### Evidence labels

Fixed vocabulary, enforced in `textlayout.simulation.evidence` (monotone: a
record may advance or fail, never silently demote):

- `*_INPUT_PREPARED` — files were generated; nothing executed.
- `SKIPPED_SOLVER_ABSENT` — the requested simulator is not installed; inputs
  still exist. (The per-backend constants `SKIPPED_JOSIM_ABSENT`,
  `SKIPPED_PSCAN2_ABSENT`, `SKIPPED_WRSPICE_ABSENT` all map to this shared
  value so the whole project reports absence with one word.)
- `*_EXECUTED` — a real subprocess/module execution happened.
- `*_TRANSIENT_PARSED` — the execution produced a parseable waveform.
- `*_RESONANCE_CHECKED` — a resonance was extracted and compared with `f0 = 1/(2π√(LC))`.
- `*_GAIN_CHECKED` — pump/signal transient data plus FFT-based gain extraction (not yet claimable in production — see limitations).
- `FAILED` — execution or parsing failed, with the reason recorded.
- `PHYSICS_VERIFIED` is reserved for a complete benchmark where geometry
  extraction **and** circuit-level checks both meet declared tolerances.

### Honest limitations

- Circuit simulators are never accepted as proof that the drawn IDC geometry
  has the target capacitance — that claim needs FasterCap/FastCap (or another
  field solver).
- The PSCAN2 generated runner refuses to fake execution: without a wired
  PSCAN2 driver API it exits with a distinct code and the evidence stays at
  `PSCAN2_INPUT_PREPARED`.
- The pump/signal gain extractor (`textlayout.simulation.postprocess`) is
  tested on synthetic data only; `*_GAIN_CHECKED` is not produced by any
  production path yet.
- WRspice JJ decks use the `B`-element + `jj(level=1)` model syntax confirmed
  from the published SNAIL-TWPA deck; they are readiness templates with
  placeholder junction parameters, not calibrated devices.

## Tests

```bash
py -3 -m uv run pytest tests/textlayout_suite
py -3 -m uv run ruff check src/textlayout scripts simulation tests/textlayout_suite
py -3 scripts/check_benchmarks.py
```

## Limitations and next work

- The generic technology is not a foundry PDK. A richer, still-illustrative PDK schema and example (`textlayout pdk list` / `textlayout pdk info`) is documented in [docs/pdk_abstraction.md](docs/pdk_abstraction.md) — real fabrication still requires a foundry-qualified PDK.
- Legacy `examples/benchmarks/` IDC capacitance is an analytical starting estimate; showcase examples 01 and 03 have the solver evidence stated above.
- The FasterCap model uses zero-thickness panels and an effective dielectric — a correlation model, not signoff; it requires mesh convergence and finite-thickness/full-wave cross-checks.
- Full-chip density, antenna, slot, enclosure, LVS, and process-specific DRC are outside the clean plugin package today.
- The next component should be promoted only after typed ports, extraction, literature comparison, and a reproducible benchmark are complete.
<!-- BEGIN GENERATED: verified-bullet -->

- **PHYSICS_VERIFIED currently exists for `01_idc_0p6pf`, `02_cpw_50ohm`, `03_idc_cpw_test_structure`.** Other scopes remain analytical, executed-without-convergence, invalid, prepared, or honestly skipped unless their canonical evidence says otherwise.
<!-- END GENERATED: verified-bullet -->
- **Nothing in this repository is FABRICATION READY** — every layout requires process-specific DRC, EM cross-check, measurement planning, and expert review.

## Development SOP

From a fresh clone: install (`pip install -e ".[dev]"` or `py -3 -m uv sync`),
run `textlayout doctor`, run one prompt
(`textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/demo`),
then gate with `uv run ruff check .`, `uv run pytest`,
`uv run python scripts/validate_readme_claims.py`, and `uv build`. The full
procedure, including showcase regeneration and the commit workflow, is in
[SOP.md](SOP.md).

## References

Analytical models and open-source solvers are documented in
[REFERENCES.md](REFERENCES.md), with full per-benchmark citations inline in each
`examples/benchmarks/*/evidence.md`.

> A paper citation supports the **analytical method** (the equation used). It does
> **not** prove that a generated geometry meets its target. Only a real solver
> result or a measurement can establish that, which is why every analytical result
> is labelled `ANALYTICAL ONLY` until a solver-owned artifact exists.

Key sources: Bahl (2003) and Alley (MTT-18, 1970) for the IDC; Simons (2001) and
Hilberg (MTT-17, 1969) for the CPW; Mohan et al. (JSSC, 1999) and Wheeler (1928)
for the spiral; Pozar (2012) for λ/4 and LCR resonance; Clarke & Braginski (2004)
and Tinkham (2004) for SQUID/Josephson physics.

## License

MIT; see [LICENSE](LICENSE).
