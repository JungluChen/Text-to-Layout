<div align="center">

# Text-to-Layout

**AI-assisted, research-first, evidence-backed layout generation for IC, RF, and superconducting designs.**

Natural-language intent becomes a researched Layout DSL, deterministic geometry, verification results, and reproducible GDS/SVG/PNG/JSON artifacts.

[Plugin design](docs/plugin_design.md) | [Tool API](docs/tool_api.md) | [Text-to-CAD study](docs/lessons_from_text_to_cad.md) | [Simulation workflows](simulation/README.md)

</div>

## 30-second demo

One command runs the full closed loop — natural language → intent → tuned Layout DSL → verified geometry → solver preparation (execution if a solver is installed) → honest evidence report:

```bash
textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/idc_demo
```

Generated files in `out/idc_demo/`:

```text
intent.json          parsed design intent (deterministic parser, no LLM/API key)
layout.json          tuned Layout DSL
output.gds           layout artifact
output.svg           preview
verification.json    geometry + design-rule check results
simulation.json      typed simulation evidence (status vocabulary below)
optimization.json    closed-loop analytical tuning record
report.md            target-vs-result report with explicit evidence status
```

Result on a machine **without** FasterCap installed (the honest default):

| Quantity | Target | Analytical estimate | Solver-extracted | Error | Evidence status |
| - | - | - | - | - | - |
| capacitance | 0.6 pF | 0.6 pF (Bahl/Alley, optimizer converged, 0.0% analytical error) | — (solver not installed) | — | `SKIPPED_SOLVER_ABSENT` |

With FasterCap/FastCap on `PATH` (or `--executable`), the solver is executed, its output is parsed, and the status becomes `SIMULATION_EXECUTED` — or `PHYSICS_VERIFIED` only when the extracted value is within tolerance of the target.

> This project is not fabrication-ready by default. Geometry generation and analytical estimation are supported. Physics verification is only claimed when an external solver is executed and its output is parsed successfully.

## Component support matrix

Validated in CI by `scripts/validate_readme_claims.py` — every "yes" below must be backed by committed code, tests, and artifacts, or the build fails.

| Component | Geometry | Analytical estimate | Solver input | Solver executed | Physics verified | Status |
| - | - | - | - | - | - | - |
| IDC | yes | yes (Bahl/Alley) | yes (FasterCap/FastCap) | environment-dependent (runs when installed; honest skip otherwise) | environment-dependent (never claimed without solver output) | Supported — full closed loop |
| CPW | yes | yes (Simons/Hilberg) | yes (openEMS manifest) | no | no | Supported — geometry + analytical |
| SpiralInductor | yes | yes (Mohan/Wheeler) | yes (FastHenry) | no | no | Supported — geometry + analytical |
| QuarterWaveResonator | yes | yes (λ/4 line theory) | yes (openEMS manifest) | no | no | Supported — geometry + analytical |
| SQUID | yes | yes (flux quantization) | yes (plan only) | no | no | Experimental — generic JJ placeholders, not foundry-qualified |

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

| Label | Meaning |
| - | - |
| **GEOMETRY PASS** | Files exist, parameters verified, geometry is valid |
| **ANALYTICAL ONLY** | Equations computed; no solver executed |
| **SIMULATION INPUT PREPARED** | Solver input files exist; solver not executed |
| **SIMULATION EXECUTED** | Solver ran and produced non-empty output file |
| **PHYSICS VERIFIED** | Extracted values compared against target with tolerance |
| **FABRICATION READY** | Process-specific DRC, EM simulation, and expert review complete |
| **INFEASIBLE** | Target not achievable under realistic constraints |

**No benchmark in this repository is currently PHYSICS VERIFIED or FABRICATION READY.**

## Layout Benchmarks

Each benchmark shows honest status across geometry, simulation, evidence, and fabrication.

| # | Target | Prompt | Output | Geometry Status | Simulation Status | Evidence Status | Fabrication Status |
| - | ------ | ------ | ------ | --------------- | ----------------- | --------------- | ------------------ |
| 1 | [IDC capacitor](examples/benchmarks/01_idc_0p6pf/) | Create a 0.6 pF IDC with 22 finger pairs, 4 um width, 2 um gap, and 250 um overlap. | [![IDC](examples/benchmarks/01_idc_0p6pf/output.png)](examples/benchmarks/01_idc_0p6pf/output.svg) | **GEOMETRY PASS** (parameters, width, gap, layer, bbox, ports, gdsfactory lowering, KLayout readback) | **SIMULATION INPUT PREPARED** (FasterCap/FastCap input exists; solver not executed) | **ANALYTICAL ONLY** (Bahl/Alley estimate = 0.6983 pF; target error = 16.4%) | **NOT READY** |
| 2 | [50 ohm CPW](examples/benchmarks/02_cpw_50ohm/) | Create a 50 ohm CPW on silicon. | [![CPW](examples/benchmarks/02_cpw_50ohm/output.png)](examples/benchmarks/02_cpw_50ohm/output.svg) | **GEOMETRY PASS** (dimensions, GSG ports, layers, bbox, gdsfactory lowering) | **SIMULATION INPUT PREPARED** (openEMS manifest exists; solver not executed) | **ANALYTICAL ONLY** (Simons conformal mapping estimate = 50.04 ohm; EM correlation pending) | **NOT READY** |
| 3 | [Spiral inductor](examples/benchmarks/03_spiral_inductor/) | Create a compact planar spiral with target inductance. | [![Spiral](examples/benchmarks/03_spiral_inductor/output.png)](examples/benchmarks/03_spiral_inductor/output.svg) | **GEOMETRY PASS** (typed parameters, width, spacing, ports, bbox, gdsfactory lowering) | **SIMULATION INPUT PREPARED** (FastHenry input exists; solver not executed) | **ANALYTICAL ONLY** (Mohan/Wheeler estimate; no solver result) | **NOT READY** |
| 4 | [Quarter-wave resonator](examples/benchmarks/04_quarter_wave_resonator/) | Create a 6 GHz quarter-wave CPW resonator. | [![Resonator](examples/benchmarks/04_quarter_wave_resonator/output.png)](examples/benchmarks/04_quarter_wave_resonator/output.svg) | **GEOMETRY PASS** (open/short topology, coupling gap, GSG ports, bbox) | **SIMULATION INPUT PREPARED** (openEMS input exists; solver not executed) | **ANALYTICAL ONLY** (L = vp/(4f) gives 4918.5 um; EM result pending) | **NOT READY** |
| 5 | [SQUID loop](examples/benchmarks/05_squid_loop/) | Create a symmetric two-junction SQUID test structure. | [![SQUID](examples/benchmarks/05_squid_loop/output.png)](examples/benchmarks/05_squid_loop/output.svg) | **GEOMETRY PASS** (candidate; symmetry, two JJ placeholders, loop area, ports, layers) | **NOT READY** (no foundry JJ-stack solver possible) | **ANALYTICAL ONLY** (flux quantization model; generic JJ placeholders not foundry-qualified) | **NOT READY** |
| 6 | [5 MHz LC resonator](examples/benchmarks/06_lc_5mhz_resonator/) | Design a lumped LC resonator layout that targets 5 MHz resonance frequency. | **NOT GENERATED** (infeasible target) | **NOT GENERATED** (no layout created) | **NOT APPLICABLE** (no simulation possible) | **INFEASIBLE** (required LC = 1.013×10⁻¹⁵ s² exceeds on-chip limits by 100-1000×; 159 MHz is the minimum feasible) | **NOT APPLICABLE** |

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
- **FasterCap/FastCap input is prepared**, but not executed
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

| Level | Meaning | Status |
| - | - | - |
| 0 | Analytical estimate only | All benchmarks start here |
| 1 | Geometry generated and verified | IDC, CPW, Spiral, Resonator, SQUID achieve this |
| 2 | Solver input prepared | IDC, CPW, Spiral, Resonator achieve this |
| 3 | Solver executed and result artifact exists | **No benchmark achieves this** |
| 4 | Result compared against target | **No benchmark achieves this** |
| 5 | Optimization loop implemented | **No benchmark achieves this** |
| INFEASIBLE | Target not achievable | **5 MHz LC resonator** |

**No benchmark is Level 3 or higher.** SQUID is Level 1 because a foundry-qualified junction stack is absent.

## What Text-to-CAD taught this project

[earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) makes its value obvious through a visual README, one prompt per benchmark, linked benchmark test cases, one-line skill installation, local preview tooling, and self-contained skill runtimes.

Text-to-Layout adopts the same reader-facing clarity and reproducibility. It does not copy mechanical B-rep logic: IC layout needs named process layers, minimum features, electrical ports, substrate assumptions, parasitic analysis, EM extraction, and evidence status that distinguishes analytical, planned, and executed work. See the [full study](docs/lessons_from_text_to_cad.md).

## Supported generation

| Component | Status | Notes |
| - | - | - |
| IDC | Geometry ready, analytical only | Typed DSL, analytical starting model, ports, GDS/SVG/PNG/JSON, verification and evidence reports |
| CPW | Geometry ready, analytical only | Typed DSL, six signal/ground-reference ports, analytical Z0, verified artifacts |
| Spiral | Geometry ready, analytical only | Typed square spiral, two ports, Mohan estimate, FastHenry input |
| Quarter-wave resonator | Geometry ready, analytical only | Explicit coupled open end, grounded short, feedline ports, openEMS manifest |
| SQUID | Geometry candidate only | Symmetric loop and two JJ placeholders; not valid for fabrication without a foundry stack |

## Install

Python 3.11+ is required.

```bash
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
py -3 -m pip install -e .
```

With `uv`:

```bash
py -3 -m uv sync
```

Install the repository's agent skills:

```bash
npx skills install JungluChen/Text-to-Layout
```

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

Interactive OpenAPI docs: <http://127.0.0.1:8000/docs>

| Method | Endpoint | Purpose |
| - | - | - |
| GET | `/health` | Discover generators, technologies, and formats |
| POST | `/layout/research` | Produce equations, assumptions, references, estimates, and simulation plan |
| POST | `/layout/generate` | Research, build, verify, and export requested artifacts |
| POST | `/layout/verify` | Run geometry/process checks without export |
| POST | `/layout/export?format=gds` | Export one verified artifact |
| POST | `/layout/simulate` | Prepare or explicitly execute a supported open-source simulation |
| POST | `/layout/benchmark` | Generate a complete benchmark packet |
| POST | `/layout/report` | Return evidence, verification, files, and simulation steps |

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

| Skill | Enforces |
| - | - |
| [`layout-research`](skills/layout-research/SKILL.md) | Research and first-principles reasoning before geometry |
| [`gdsfactory-layout`](skills/gdsfactory-layout/SKILL.md) | DSL-first deterministic gdsfactory generation |
| [`layout-verification`](skills/layout-verification/SKILL.md) | Pre-export and post-export gates |
| [`layout-simulation-evidence`](skills/layout-simulation-evidence/SKILL.md) | Honest simulation planning and solver provenance |

## Open-source simulation workflow

Open-source tools are the default base workflow. Commercial tools remain optional correlation/signoff connectors.

| Target | Open-source path | Current status |
| - | - | - |
| IDC capacitance | FasterCap/FastCap; Elmer as a future cross-check | Input preparation implemented |
| CPW and resonator S-parameters | openEMS + scikit-rf | Input preparation implemented |
| Spiral L/R/Q | FastHenry/FastHenry2 | Input preparation implemented |
| General FDTD/FEM | Meep / Elmer | Planned connectors |

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

- [HFSS](simulation/hfss_workflow.md)
- [Q3D](simulation/q3d_workflow.md)
- [ADS](simulation/ads_workflow.md)
- [Sonnet](simulation/sonnet_workflow.md)

## Tests

```bash
py -3 -m uv run pytest tests/textlayout_suite
py -3 -m uv run ruff check src/textlayout scripts simulation tests/textlayout_suite
py -3 scripts/check_benchmarks.py
```

## Limitations and next work

- The generic technology is not a foundry PDK.
- IDC capacitance is an analytical starting estimate, not solver or measurement evidence.
- The Level 2 FasterCap model uses zero-thickness panels and an effective dielectric; it requires mesh convergence and higher-fidelity correlation.
- Full-chip density, antenna, slot, enclosure, LVS, and process-specific DRC are outside the clean plugin package today.
- The next component should be promoted only after typed ports, extraction, literature comparison, and a reproducible benchmark are complete.
- **No benchmark is PHYSICS VERIFIED** - all analytical estimates require solver execution and comparison.
- **No benchmark is FABRICATION READY** - all require process-specific DRC and expert review.

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
