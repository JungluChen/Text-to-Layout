<div align="center">

# Text-to-Layout

**Natural-language IC layout — the Text-to-CAD for chips.**

Turn a plain-language request into a **verified GDSII layout** through a safe,
deterministic pipeline. The AI proposes a structured *Layout DSL*; a gdsfactory
engine draws the geometry; design-rule verification gates it before export.

[Plugin design](docs/plugin_design.md) · [API reference](docs/tool_api.md) ·
[Lessons from Text-to-CAD](docs/lessons_from_text_to_cad.md) ·
[Simulation workflow](simulation/README.md)

</div>

---

## Why this exists

[Text-to-CAD](https://github.com/earthtojake/text-to-cad) turns language into
**mechanical** CAD (STEP solids). **Text-to-Layout** turns language into **IC
layout** (GDSII on process layers).

But IC layout is more dangerous than mechanical CAD: a geometry that violates a
design rule is a scrapped mask set. So we follow one principle:

> **Never trust raw AI-generated geometry.**
> `AI → structured Layout DSL → deterministic gdsfactory generator → verification → export`

The AI never writes GDS. Its only job is to emit a typed `LayoutSpec`; everything
downstream is deterministic, unit-tested, and design-rule-checked.

### Comparison to Text-to-CAD

| | Text-to-CAD | **Text-to-Layout** |
|---|---|---|
| Domain | Mechanical CAD (3-D solids) | IC layout (2.5-D planar layers) |
| Primary artifact | STEP | **GDSII** |
| Geometry kernel | build123d / OpenCascade | **gdsfactory** |
| Preview | Three.js mesh viewer | 2-D SVG |
| Safety gate | inspect + mandatory snapshot | **design-rule verification** (min width/gap, layer legality) |
| AI writes | build123d Python source | **only the Layout DSL** (never geometry code) |
| Interface | Claude/Codex *skill* | **FastAPI** server + CLI + skill/MCP |

See [`docs/lessons_from_text_to_cad.md`](docs/lessons_from_text_to_cad.md) for the
full study.

## System architecture

```
User Prompt
    ↓
AI Tool Call (Planner / Layout agent)        ← the only AI step
    ↓
FastAPI Plugin Server  (POST /layout/*)
    ↓
Layout DSL Validation  (pydantic v2, extra="forbid")
    ↓
gdsfactory Generator   (deterministic geometry engine)
    ↓
Verification           (design-rule + geometry checks)
    ↓
GDS / SVG / JSON
    ↓
Simulation Workflow    (HFSS / Q3D / ADS — documented)
    ↓
Report
```

Clean-architecture package `src/textlayout/`; dependencies point inward only.
Details in [`docs/plugin_design.md`](docs/plugin_design.md).

## Supported components

| Component | Status | Schema |
|---|---|---|
| **IDC** — interdigital capacitor | ✅ implemented (gdsfactory + ports + GDS) | `IDCSpec` |
| **CPW** — coplanar waveguide | ✅ implemented | `CPWSpec` |
| Spiral inductor, resonator, SQUID, JJ, transmission line, ground plane, test structures | 🔜 roadmap (each is an additive plugin) | — |

New devices register via the `textlayout.generators` entry-point group — no core
code is touched (Open/Closed).

## Installation

Python 3.11+ (3.12 recommended). Using [uv](https://docs.astral.sh/uv/):

```bash
uv sync                 # install the project + deps
# or, with pip:
pip install -e .
```

## Quick start

### 1. Command line

```bash
# Verify a Layout DSL file (design-rule checks only)
textlayout verify examples/idc_0p6pf.json

# Generate verified GDS/SVG/JSON into ./out
textlayout generate examples/idc_0p6pf.json --out out
```

### 2. Run the plugin API server

```bash
textlayout serve --port 8000
# or:  python -m textlayout.backend
```

Interactive docs at <http://127.0.0.1:8000/docs>; OpenAPI at `/openapi.json`.

### 3. Call the API

```bash
curl -s localhost:8000/health | jq

curl -s -X POST localhost:8000/layout/generate \
  -H 'Content-Type: application/json' \
  -d @examples/idc_0p6pf.json | jq '.status, .summary, .files'

curl -s -X POST localhost:8000/layout/verify \
  -H 'Content-Type: application/json' \
  -d @examples/idc_0p6pf.json | jq
```

## Layout DSL

```json
{
  "component": "IDC",
  "technology": "generic_2metal",
  "parameters": {
    "finger_pairs": 24, "finger_width_um": 4, "gap_um": 2,
    "overlap_um": 250, "bus_width_um": 25, "metal_layer": "M1"
  },
  "rules":   { "min_width_um": 2, "min_gap_um": 2 },
  "outputs": { "gds": true, "svg": true, "json": true }
}
```

Field constraints (`gt=0`, `extra="forbid"`) mean an LLM cannot push a
non-physical value past the firewall — it is rejected with HTTP 400 before any
geometry is built. Full schema: [`docs/tool_api.md`](docs/tool_api.md).

## Verification example

`POST /layout/verify` (or any generate call) returns a structured report:

```json
{
  "status": "pass",
  "component": "IDC",
  "checks": [
    { "name": "minimum_gap",   "status": "pass", "value_um": 2, "limit_um": 2 },
    { "name": "minimum_width", "status": "pass", "value_um": 4, "limit_um": 2 },
    { "name": "ports_exist",   "status": "pass", "value_count": 2, "limit_count": 2 }
  ],
  "warnings": [],
  "errors": []
}
```

Checks: component generated, positive dimensions, minimum width, minimum gap,
finger-count sanity, layer exists, bounding box, ports exist, geometry spacing.
Each check reports the measured value and the limit it was tested against; checks
that do not apply are omitted (never faked).

## Generated outputs

| Format | What | How |
|---|---|---|
| `*.gds` | GDSII — the primary fabrication artifact (real gdsfactory Component with ports) | `outputs.gds` / `POST /layout/export?format=gds` |
| `*.svg` | 2-D preview | `outputs.svg` / `POST /layout/preview` |
| `*.json` | Lossless Geometry IR (layers, polygons, bbox, metadata) | `outputs.json` |

## Simulation workflow

Documented hand-off into EM extraction (no solver is auto-driven yet, and no
simulated value is reported unless a solver actually produced it):

```
Generated GDS → HFSS/Q3D/ADS → materials, ports, boundaries → EM extraction
→ C, L, Q, S-params, resonance → compare with target → AI DSL-tuning loop → report
```

Guides: [HFSS](simulation/hfss_workflow.md) ·
[Q3D](simulation/q3d_workflow.md) · [ADS](simulation/ads_workflow.md) ·
[overview](simulation/README.md).

## Project layout

```
src/textlayout/
  schemas/dsl/   Layout DSL (LayoutSpec, IDCSpec, CPWSpec)   ← the firewall
  models/        pure geometry + technology entities
  geometry/      deterministic engine (DSL → geometry)
  generators/    IDC, CPW + entry-point plugin registry
  exporters/     GDS (gdsfactory), SVG, JSON
  verification/  design-rule + geometry checks
  workflows/     build → verify → export orchestration
  backend/       FastAPI plugin server
  cli.py         command-line interface
examples/        DSL + request/response examples
docs/            plugin design, tool API, OpenAPI, manifest, lessons
simulation/      HFSS / Q3D / ADS workflow docs
tests/textlayout_suite/   unit, geometry, golden, verification, API tests
```

## Testing

```bash
uv run pytest tests/textlayout_suite      # plugin tests
uv run ruff check src/textlayout          # lint
uv run --with mypy mypy src/textlayout    # strict type-check
```

## Roadmap

- [x] Layout DSL + deterministic geometry engine + plugin registry
- [x] IDC + CPW generators; GDS/SVG/JSON export; design-rule verification
- [x] FastAPI plugin server + OpenAPI + CLI
- [ ] Natural-language → DSL agent (Planner/Layout) behind an LLM port
- [ ] More devices: spiral inductor, resonator, SQUID, JJ, test structures
- [ ] Automated EM extraction + closed-loop DSL optimization
- [ ] PDK support beyond the built-in generic stack

## Relationship to the quantum-EDA platform

This repository also contains a deep **superconducting-quantum EDA platform**
(`src/text_to_gds/`, the MCP server, solver integrations) whose documentation is
preserved at
[`docs/legacy/QUANTUM_PLATFORM_README.md`](docs/legacy/QUANTUM_PLATFORM_README.md).
The `textlayout` package is a clean, plugin-focused front end built alongside it
(strangler-fig); the two share the same repo and the quantum physics/solver
assets are being wrapped behind the new architecture over time.

## Contributing

1. Add a device: new `schemas/dsl/<device>.py` + `generators/<device>.py`
   implementing `Generator`, register via the `textlayout.generators`
   entry-point group. No core file changes.
2. Keep it green: `ruff`, `mypy --strict` (on `src/textlayout`), and
   `pytest` must pass; add a golden test for every new generator.
3. Honesty contract: never report a value as simulated/measured unless a solver
   produced it.

## License

MIT — see [LICENSE](LICENSE).
