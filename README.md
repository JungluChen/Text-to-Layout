<div align="center">

# Text-to-Layout

**AI-assisted, research-first, first-principles-guided, evidence-backed, verified layout generation.**

Natural-language intent becomes a researched Layout DSL, deterministic gdsfactory geometry, verification results, and reproducible GDS/SVG/PNG/JSON artifacts.

[Plugin design](docs/plugin_design.md) | [Tool API](docs/tool_api.md) | [Text-to-CAD study](docs/lessons_from_text_to_cad.md) | [Simulation workflows](simulation/README.md)

</div>

## What it does

Text-to-Layout is not "AI randomly draws layout." The AI may research the target and propose a typed Layout DSL. Deterministic code owns geometry, layer mapping, ports, verification, simulation preparation, and export.

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

## 🧪 Layout Benchmarks

The benchmark table follows Text-to-CAD's prompt-to-output presentation, but adds verification and evidence. Only rows with real generated artifacts show an image or claim PASS.

| # | Target | Prompt | Output | Verification | Evidence |
| - | - | - | - | - | - |
| 1 | [IDC capacitor](examples/benchmarks/01_idc_0p6pf/) | Create a 0.6 pF IDC with 22 finger pairs, 4 um width, 2 um gap, and 250 um overlap. | [![IDC layout](examples/benchmarks/01_idc_0p6pf/output.png)](examples/benchmarks/01_idc_0p6pf/output.svg) | PASS: parameters, width, gap, layer, bbox, ports, gdsfactory lowering, files | Bahl/Alley estimate; FasterCap/FastCap input prepared (Level 2); Q3D/HFSS or Sonnet cross-check |
| 2 | [50 ohm CPW](examples/benchmarks/02_cpw_50ohm/) | Create a 50 ohm CPW on silicon. | **TODO** | TODO: explicit RF and ground-reference ports | Simons conformal mapping; EM correlation pending |
| 3 | [Spiral inductor](examples/benchmarks/03_spiral_inductor/) | Create a compact planar spiral with target inductance. | **TODO** | No generator registered | Mohan/Wheeler model planned |
| 4 | [Quarter-wave resonator](examples/benchmarks/04_quarter_wave_resonator/) | Create a 6 GHz quarter-wave CPW resonator. | **TODO** | No benchmark-ready topology | `L = vp/(4f)` is only an initial model; EM pending |
| 5 | [SQUID loop](examples/benchmarks/05_squid_loop/) | Create a symmetric two-junction SQUID test structure. | **TODO** | Foundry-specific JJ stack required | Flux quantization model; overlap and process evidence pending |

Every ready benchmark contains:

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

The IDC report labels capacitance as analytical. Its FastCap-compatible input reaches simulation readiness Level 2, but it does not claim a simulated or fabricated value.

### Simulation readiness

| Level | Meaning |
| - | - |
| 0 | Analytical estimate only |
| 1 | Geometry generated and verified |
| 2 | Open-source simulation input/script exists |
| 3 | Real solver result generated |
| 4 | Result compared against target |
| 5 | Optimization loop implemented |

The IDC benchmark is Level 2. No benchmark is Level 3 or higher yet.

## What Text-to-CAD taught this project

[earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) makes its value obvious through a visual README, one prompt per benchmark, linked benchmark test cases, one-line skill installation, local preview tooling, and self-contained skill runtimes.

Text-to-Layout adopts the same reader-facing clarity and reproducibility. It does not copy mechanical B-rep logic: IC layout needs named process layers, minimum features, electrical ports, substrate assumptions, parasitic analysis, EM extraction, and evidence status that distinguishes analytical, planned, and executed work. See the [full study](docs/lessons_from_text_to_cad.md).

## Supported generation

| Component | Status | Notes |
| - | - | - |
| IDC | Benchmark-ready | Typed DSL, analytical starting model, ports, GDS/SVG/PNG/JSON, verification and evidence reports |
| CPW | Geometry implementation | Research model exists; benchmark signoff is withheld until explicit signal/ground port semantics are added |
| Spiral, resonator, SQUID | Research/TODO | No final output is claimed |

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
| CPW and resonator S-parameters | openEMS + scikit-rf | Blocked on benchmark-ready ports/topology |
| Spiral L/R/Q | FastHenry/FastHenry2 | Blocked on deterministic spiral generator |
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

## License

MIT; see [LICENSE](LICENSE).
