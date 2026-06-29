# Plugin Design

How the Text-to-Layout plugin is structured and why.

## Core principle: the AI never writes geometry

```
Natural language
      │  (Planner / Layout agent — the only AI step)
      ▼
  Layout DSL  ◄── the firewall: a typed, validated JSON object
      │
      ▼
 gdsfactory Geometry Engine   (deterministic, no AI)
      │
      ▼
   Verification   (design-rule + geometry checks)
      │
      ▼
  GDS / SVG / JSON   →   Simulation workflow   →   Report
```

IC layout is more dangerous than mechanical CAD: a geometry that violates a
design rule is a scrapped mask set. So we **never trust raw AI-generated
geometry**. The AI's only job is to emit a valid `LayoutSpec` (the DSL); a
deterministic, unit-tested engine turns that into geometry, and verification
gates it before export.

## Clean-architecture layers (`src/textlayout/`)

Dependencies point inward only; inner layers never import outer ones.

| Layer | Package | Responsibility |
|---|---|---|
| Domain | `models/`, `schemas/dsl/`, `geometry/` | Pure entities, the DSL, the deterministic engine. No FastAPI, no gdsfactory. |
| Application | `workflows/`, `verification/` | Orchestration (build → verify → export). Depends only on ports + domain. |
| Adapters | `generators/`, `exporters/`, `knowledge/` | Concrete devices, output formats, PDK data. Implement the `ports/`. |
| Drivers | `backend/` (FastAPI), `cli.py`, `text_to_gds` MCP | Transport. Wire the workflow via dependency injection. |

The composition root is `textlayout.build_default_workflow()` — the single place
that wires concrete adapters to abstract ports. Everything else receives its
collaborators through constructors (no global state).

## Extensibility (Open/Closed)

A new device is added **without editing existing code**:

1. Add a parameter schema in `schemas/dsl/<device>.py` (pydantic v2).
2. Add a generator in `generators/<device>.py` implementing `Generator`.
3. Register it — either in `default_registry()` (built-in) or via the
   `textlayout.generators` entry-point group (third-party `pip install`).

```toml
[project.entry-points."textlayout.generators"]
SpiralInductor = "my_pkg.spiral:SpiralInductorGenerator"
```

The registry discovers entry points at startup; the engine, verifier, exporters,
and API are untouched.

## Three entry points, one core

The same `GenerateWorkflow` backs all of:

- **CLI** — `textlayout generate spec.json` / `verify` / `serve`.
- **Local API server** — `python -m textlayout.backend` (FastAPI + uvicorn).
- **MCP / custom GPT action** — the API's OpenAPI schema is the tool manifest.

## Verification model

Borrowed from Text-to-CAD's "validate before you trust the artifact" and
specialised for design rules. Each `Check` carries its measured value and the
limit it was tested against; checks that do not apply are omitted (never faked).
See [`tool_api.md`](tool_api.md) for the report schema.
