<div align="center">

# Text-to-Layout

**AI-assisted, research-first, evidence-backed layout generation for IC, RF, and superconducting designs.**

Natural-language intent becomes a researched Layout DSL, deterministic geometry, verification results, and reproducible GDS / SVG / PNG / JSON artifacts.

[![CI](https://github.com/JungluChen/Text-to-Layout/actions/workflows/ci.yml/badge.svg)](https://github.com/JungluChen/Text-to-Layout/actions/workflows/ci.yml)

[Clean-room verification](CLEAN_ROOM_VERIFICATION.md) · [Artifact policy](docs/artifact_policy.md) · [Plugin design](docs/plugin_design.md) · [GPT Action deployment](docs/public_gpt_action_deployment.md)

</div>

---

## 30-second IDC demo

```bash
uv run textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/idc_demo
```

The command deterministically parses the prompt, tunes the Bahl/Alley estimate,
generates geometry, verifies it, and prepares FasterCap/FastCap input. It writes:

```text
out/idc_demo/
  intent.json       inferred prompt values
  layout.json       final structured Layout DSL
  output.gds        deterministic layout
  output.svg        layout preview
  verification.json geometry and analytical checks
  simulation.json   solver command/artifact/evidence status
  report.md         target comparison and limitations
```

[![IDC layout preview](examples/benchmarks/01_idc_0p6pf/output.png)](examples/benchmarks/01_idc_0p6pf/output.svg)

For the command above, the deterministic analytical loop targets `0.6 pF` and
converges to approximately `0.600001 pF`. If FasterCap/FastCap is absent,
`simulation.json` reports `SIMULATION_INPUT_PREPARED` with
`SKIPPED_SOLVER_ABSENT`; extracted capacitance remains unavailable and physics
verification remains false. If a solver is present, its output is parsed and
compared against the configured tolerance. This is not fabrication readiness.

---

## What it does

Text-to-Layout is **not** "AI randomly draws a layout." The AI researches the
target and proposes a typed Layout DSL. Deterministic code owns geometry, layer
mapping, ports, verification, simulation preparation, and export.

```text
Research
  → first-principles model
  → initial parameter calculation
  → Layout DSL (Pydantic v2)
  → deterministic geometry
  → gdsfactory Component
  → verification gate
  → SVG / PNG / GDS / JSON
  → open-source simulation preparation or execution
  → evidence-backed report
```

If required verification fails, **final geometry artifacts are not exported**.

> **⚠️ Generated layouts are design candidates, not fabrication-ready masks.**
> Final fabrication requires process-specific DRC, EM simulation, expert review,
> and foundry or lab rule validation.

The project's value is not that it draws many layouts. It is that it can prove
**whether a layout meets — or cannot meet — a physical specification**, and
labels every claim with the evidence behind it.

---

## Status vocabulary

Explicit labels are used everywhere to avoid misleading claims:

| Label | Meaning |
| --- | --- |
| **GEOMETRY PASS** | Files exist, parameters verified, geometry is valid |
| **ANALYTICAL ONLY** | Closed-form equations computed; no solver executed |
| **SIMULATION INPUT PREPARED** | Solver input files exist; solver not executed |
| **SIMULATION EXECUTED** | Solver ran and produced a non-empty output file |
| **PHYSICS VERIFIED** | Extracted value compared against target within tolerance |
| **FAILED** | Verification or attempted solver execution failed |
| **SKIPPED SOLVER ABSENT** | Solver was requested but no executable was found |
| **FABRICATION READY** | Process DRC, EM simulation, and expert review complete |
| **INFEASIBLE** | Target not achievable under realistic constraints |

**No benchmark in this repository is currently PHYSICS VERIFIED or FABRICATION READY.**

---

## Layout benchmarks

Each benchmark is a self-contained packet under
[`examples/benchmarks/`](examples/benchmarks/). The first table shows the prompt
and preview; the second shows the honest engineering status.

### 1. Visual

| # | Target | Prompt | Preview |
| --- | --- | --- | --- |
| 1 | IDC capacitor | Create a 0.6 pF IDC with 22 finger pairs, 4 µm width, 2 µm gap, 250 µm overlap. | [![IDC](examples/benchmarks/01_idc_0p6pf/output.png)](examples/benchmarks/01_idc_0p6pf/output.svg) |
| 2 | 50 Ω CPW | Create a 50 Ω CPW on silicon. | [![CPW](examples/benchmarks/02_cpw_50ohm/output.png)](examples/benchmarks/02_cpw_50ohm/output.svg) |
| 3 | Spiral inductor | Create a compact planar spiral with target inductance. | [![Spiral](examples/benchmarks/03_spiral_inductor/output.png)](examples/benchmarks/03_spiral_inductor/output.svg) |
| 4 | λ/4 resonator | Create a 6 GHz quarter-wave CPW resonator. | [![Resonator](examples/benchmarks/04_quarter_wave_resonator/output.png)](examples/benchmarks/04_quarter_wave_resonator/output.svg) |
| 5 | SQUID loop | Create a symmetric two-junction SQUID test structure. | [![SQUID](examples/benchmarks/05_squid_loop/output.png)](examples/benchmarks/05_squid_loop/output.svg) |
| 6 | 5 MHz LC | Design a lumped LC resonator targeting 5 MHz. | _no layout (infeasible)_ |

### 2. Engineering status

| # | Benchmark | Geometry | Simulation | Evidence | Fabrication |
| --- | --- | --- | --- | --- | --- |
| 1 | [IDC](examples/benchmarks/01_idc_0p6pf/) | GEOMETRY PASS | SIMULATION INPUT PREPARED (FasterCap) | ANALYTICAL ONLY · est. 0.6983 pF · 16.4% error | NOT READY |
| 2 | [CPW](examples/benchmarks/02_cpw_50ohm/) | GEOMETRY PASS | SIMULATION INPUT PREPARED (openEMS) | ANALYTICAL ONLY · est. 50.04 Ω | NOT READY |
| 3 | [Spiral](examples/benchmarks/03_spiral_inductor/) | GEOMETRY PASS | SIMULATION INPUT PREPARED (FastHenry) | ANALYTICAL ONLY · Mohan/Wheeler | NOT READY |
| 4 | [Resonator](examples/benchmarks/04_quarter_wave_resonator/) | GEOMETRY PASS | SIMULATION INPUT PREPARED (openEMS) | ANALYTICAL ONLY · L = 4918.5 µm | NOT READY |
| 5 | [SQUID](examples/benchmarks/05_squid_loop/) | GEOMETRY PASS (candidate) | NOT READY (no foundry JJ stack) | ANALYTICAL ONLY · flux quantization | NOT READY |
| 6 | [5 MHz LC](examples/benchmarks/06_lc_5mhz_resonator/) | NOT GENERATED | NOT APPLICABLE | INFEASIBLE · required LC = 1.013×10⁻¹⁵ s²; 159 MHz is the on-chip minimum | NOT APPLICABLE |

Each `ready` benchmark folder contains:

```text
prompt.md               original request
layout.json             Layout DSL + provenance (the source of truth)
output.gds              primary layout artifact
output.svg / .png       human previews
output.json             geometry IR and metadata
verification.json       separated geometry/artifact/analytical/simulation/physics/fab status
analytical_estimate.md  equations and calculated starting values
simulation_plan.md      readiness level, prepared inputs, expected extraction
evidence.md             equations, assumptions, references, limitations
report.md               target comparison and simulation status
```

---

## Physics-fit acceptance tests

A benchmark asks "does it draw?". An **acceptance test**
([`examples/acceptance/`](examples/acceptance/)) asks the harder question:
does the layout meet the physical requirement, or does the system correctly
refuse an infeasible one?

| # | Prompt | Verdict | What it proves |
| --- | --- | --- | --- |
| A | Fully on-chip passive LC resonator at 5 MHz | `INFEASIBLE` | Refuses to fake a layout; required `LC = 1.013×10⁻¹⁵ s²`, unreachable on-chip |
| B | 6 GHz quarter-wave CPW resonator | `GEOMETRY PASS` | Length derived from `v_p/(4f)` ≈ 4918 µm; openEMS input prepared; **not** physics-verified without a solver run |
| C | IDC targeting 0.6 pF, auto-size fingers | `GEOMETRY PASS` | Auto-sizes to 19 finger pairs (≈0.2% error) vs the prompt's 22 (≈16.4%); analytical only |

`PHYSICS_VERIFIED` is only reachable when a real solver runs, a value is
extracted, and it matches the target within tolerance. Pass rules are enforced in
[`tests/textlayout_suite/test_acceptance_physics.py`](tests/textlayout_suite/test_acceptance_physics.py).

---

## Simulation readiness levels

| Level | Meaning | Status |
| --- | --- | --- |
| 0 | Analytical estimate only | all benchmarks start here |
| 1 | Geometry generated and verified | IDC, CPW, Spiral, Resonator, SQUID |
| 2 | Solver input prepared | IDC, CPW, Spiral, Resonator |
| 3 | Solver executed and result artifact exists | **no benchmark** |
| 4 | Result compared against target | **no benchmark** |
| 5 | Optimization loop implemented | IDC prompt flow (analytical closed loop) |
| — | Target not achievable | **5 MHz LC resonator (INFEASIBLE)** |

SQUID stays at Level 1 because a foundry-qualified junction stack is absent.

---

## Install

Python 3.11+ is required.

```bash
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
pip install -e .
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync
```

### Optional dependency groups

```bash
pip install -e ".[dev]"      # pytest, ruff, mypy
pip install -e ".[api]"      # FastAPI + uvicorn server (included by default)
pip install -e ".[solvers]"  # scikit-rf for Touchstone post-processing
```

Native solvers (FasterCap, FastHenry, openEMS) are **not** Python packages —
install them separately; the workflow detects them and degrades gracefully when
they are absent.

---

## Command line

```bash
# Natural language to a complete IDC evidence packet (no API key required)
textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/idc_demo

# Generate verified artifacts from a DSL file
textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/idc

# Verify a DSL file without exporting (exit code 2 on failure)
textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json

# Compile natural language to an inspectable DSL without writing artifacts
textlayout compile "Create a 50 ohm CPW on silicon"

# Compile, verify, export, and prepare/attempt solver execution
textlayout prompt "Create a 0.6 pF IDC" --out out/idc-from-text

# Run the plugin API server
textlayout serve --host 127.0.0.1 --port 8000
```

`generate` writes the geometry plus `*.layout.json`, `*.verification.json`,
`*.evidence.md`, `*.analytical_estimate.md`, `*.simulation_plan.md`, and
`*.report.md` sidecars. A failed pre-export check returns exit code 2 and writes
no final geometry artifact.

Regenerate and audit the benchmarks (see [artifact policy](docs/artifact_policy.md)):

```bash
python scripts/generate_benchmarks.py          # reproducible; skips unchanged
python scripts/check_benchmarks.py --strict     # audit links + honesty contract
python scripts/generate_acceptance.py           # physics-fit acceptance packets
```

---

## HTTP API

```bash
textlayout serve --host 127.0.0.1 --port 8000
# interactive docs at http://127.0.0.1:8000/docs
```

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Discover generators, technologies, and formats |
| POST | `/layout/compile` | Compile an IDC/CPW prompt to typed DSL without writing files |
| POST | `/layout/from-text` | Compile, verify, export, and prepare or execute simulation |
| POST | `/layout/research` | Equations, assumptions, references, estimates, simulation plan |
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

Endpoints always return JSON (including structured error bodies), never HTML
error pages. See [tool API](docs/tool_api.md) and [OpenAPI usage](docs/openapi_usage.md).

---

## Plugin / GPT Action

The same server backs a local plugin manifest
([`plugin_manifest.example.json`](plugin_manifest.example.json)) and an OpenAPI
schema importable into a custom GPT Action.

> **Local plugin-style ready.** The manifest and `/openapi.json` work against
> `http://127.0.0.1:8000`, which is enough for local tools and MCP-style use.
>
> **Public GPT Actions require a public HTTPS endpoint.** ChatGPT cannot reach
> `localhost`. The repository is **not** claimed to be "public ChatGPT plugin
> ready" — no public HTTPS endpoint has been deployed or tested here. The path to
> deploy one (Docker, Fly.io, Render, Railway, a VPS + reverse proxy, or a
> tunnel for development) is documented in
> [docs/public_gpt_action_deployment.md](docs/public_gpt_action_deployment.md).

---

## Open-source simulation

Open-source tools are the default base workflow; commercial tools remain optional
correlation/signoff connectors.

| Target | Open-source path | Status |
| --- | --- | --- |
| IDC capacitance | FasterCap / FastCap | input prepared; execution + parse + compare implemented |
| Spiral L / R / Q | FastHenry / FastHenry2 | input prepared; execution + parse + compare implemented |
| CPW / resonator S-parameters | openEMS + scikit-rf | input prepared; Touchstone post-processing implemented |
| General FDTD / FEM | Meep / Elmer | planned connectors |

Execution is **graceful**: a missing solver yields `status="skipped"`
(evidence stage `solver_missing`), never an exception, and the prepared input
files remain on disk. The evidence ladder is
`solver_missing → input_prepared → executed → parsed → compared`, and
`physics_verified` is only set when a real run is parsed and compared within
tolerance.

```python
from textlayout.simulation import simulate_layout
# execute=True runs the solver if installed, else returns a graceful skip
result = simulate_layout(spec, geometry, tech, "out/sim", solver="auto", execute=True)
print(result.evidence_stage, result.physics_verified)
```

---

## Reproducibility

Benchmark artifacts are **reproducible for a pinned toolchain**, and regenerating
them twice in a row produces no git diff:

- `generated_at` is normalized; the real time is kept out of version control.
- GDS top-cell names are stabilized and the GDSII timestamp is zeroed.
- Unchanged benchmarks are skipped, never rewritten.

Provenance (`layout_json_sha256`) detects stale artifacts, and
`check_benchmarks.py` enforces that `output.json` and `verification.json`
provenance agree. Full details and known limitations are in
[docs/artifact_policy.md](docs/artifact_policy.md). The clean-room install/test
run is recorded in [CLEAN_ROOM_VERIFICATION.md](CLEAN_ROOM_VERIFICATION.md):
**local CLI / API / plugin-style verification PASS.**

---

## Tests and quality gates

```bash
pytest
ruff check .
python scripts/check_benchmarks.py --strict
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the test suite on
Linux and Windows (Python 3.11 / 3.12), the strict benchmark audit, the CLI
smoke checks, benchmark determinism, and an API smoke test. Optional native
solvers are absent in CI, so simulation stays in the input-prepared /
solver-missing states and nothing is over-claimed.

---

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
  "evidence": {"analytical_model": "Bahl/Alley IDC estimate", "simulation_required": true}
}
```

Supported components: `IDC`, `CPW`, `SpiralInductor`, `QuarterWaveResonator`,
`SQUID` (geometry candidate only).

---

## Packages and naming

| Name | What it is |
| --- | --- |
| **Text-to-Layout** | Product / repository name |
| `textlayout` | Primary CLI and clean-architecture Python package (`src/textlayout`) |
| `text-to-gds` | Distribution name on PyPI metadata + legacy MCP entry point |
| `text_to_gds` | Legacy import namespace (`src/text_to_gds`), migrated module-by-module |

The legacy `text_to_gds` MCP server still ships for backward compatibility; new
work targets `textlayout`. See [AGENTS.md](AGENTS.md) and
[ARCHITECTURE.md](ARCHITECTURE.md).

---

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

---

## License

MIT; see [LICENSE](LICENSE).
