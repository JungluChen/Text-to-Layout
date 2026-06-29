# Plugin Design

## Safety boundary

```text
natural language
  -> research report
  -> typed Layout DSL
  -> deterministic generator
  -> geometry verification
  -> gdsfactory Component sanity
  -> GDS/SVG/PNG/JSON export
  -> artifact verification
  -> evidence-backed report
```

The AI may propose the DSL. It does not write polygons or GDS directly. Geometry generation, verification, and export are deterministic Python operations.

## Package layers

| Layer | Package | Responsibility |
| - | - | - |
| Domain | `models/`, `schemas/dsl/` | Immutable geometry, technology, and typed request entities |
| Evidence | `research/` | Equations, assumptions, references, analytical starting values, simulation plans |
| Application | `geometry/`, `verification/`, `workflows/` | Build, pre-export gate, export orchestration, post-export audit |
| Adapters | `generators/`, `exporters/`, `knowledge/` | Deterministic devices, gdsfactory/GDS lowering, previews, process data |
| Drivers | `backend/`, `cli.py` | FastAPI/OpenAPI and command-line interfaces |

`textlayout.build_default_workflow()` is the composition root. The CLI and API call the same workflow, so benchmarks cannot bypass verification.

## Artifact contract

Successful generation returns:

- primary GDS;
- SVG/PNG previews and geometry JSON as requested;
- input Layout DSL provenance;
- structured verification JSON;
- evidence Markdown;
- report Markdown with target comparison and simulation status.

Failed pre-export verification returns diagnostics and no final geometry artifacts. An analytical value is not a simulated value. An EM result may be called executed only when a solver-owned output artifact exists.

## Extending components

A new component needs all of these before it can become benchmark-ready:

1. Pydantic v2 parameter schema with explicit units.
2. Deterministic generator with process layers and ports.
3. Registered research model with equations and references.
4. Geometry and process checks.
5. GDS/SVG/PNG/JSON golden tests.
6. Simulation/extraction workflow and honest status handling.
7. Reproducible benchmark folder and README row.

Third-party generators use the `textlayout.generators` entry-point group. A generator without a registered research model is blocked by the evidence gate.
