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
  -> open-source simulation preparation or guarded execution
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
- analytical-estimate and simulation-plan Markdown;
- report Markdown with target comparison and simulation status.

Failed pre-export verification returns diagnostics and no final geometry artifacts. An analytical value is not a simulated value. An EM result may be called executed only when a solver-owned output artifact exists.

The base simulation boundary is open-source-first. `textlayout.simulation` prepares FastCap/FasterCap IDC panels, openEMS CPW/resonator manifests, and FastHenry spiral input while exposing explicit readiness/status records. SQUID remains Level 1 until process-specific JJ data exist. Every adapter preserves the prepared/executed distinction.

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

## Integration modes

There are three distinct ways to use this project. They are not interchangeable.

1. **Local CLI** — `textlayout generate ...` / `textlayout verify ...`. Runs
   entirely on your machine; no server.
2. **Local API server** — `textlayout serve` (or `python -m textlayout.backend`).
   Serves JSON + OpenAPI at `http://127.0.0.1:8000`. Suitable for local agents
   and development.
3. **GPT Action / plugin-style tool** — an AI tool-caller consumes the OpenAPI
   schema at `/openapi.json`.

> **Important — local URLs are not reachable by a hosted GPT Action.**
> `docs/plugin_manifest.example.json` points at `http://127.0.0.1:8000/openapi.json`
> for **local development only**. A ChatGPT custom GPT Action runs on OpenAI's
> servers and **cannot reach `127.0.0.1` / `localhost` on your machine**. To use
> it as a real GPT Action you must expose the server at a **public HTTPS URL**
> (a reverse proxy, a cloud deployment, or an approved development tunnel) and set
> the manifest `api.url` to that URL. The example manifest is a template, not a
> deployable public endpoint.

## Naming: `textlayout` vs `text-to-gds`

This repository contains two packages, intentionally:

| Name | Package | Role |
| - | - | - |
| **`textlayout`** | `src/textlayout/` | The clean Text-to-Layout plugin (DSL → gdsfactory → verify → export). Console command: `textlayout`. This document describes it. |
| **`text-to-gds`** | `src/text_to_gds/` | The older superconducting-quantum EDA platform and its MCP server. `.mcp.json` launches `text-to-gds` (the MCP stdio server), not the `textlayout` HTTP API. |

Both import cleanly (`import textlayout`, `import text_to_gds`) and are built
from the same repository (a strangler-fig migration). The Text-to-Layout plugin
work lives entirely under `textlayout`; `text-to-gds` is retained for the legacy
platform and its Claude Desktop MCP integration. If you only want the plugin, use
the `textlayout` CLI/API and ignore `.mcp.json`.
