# Architecture — Text-to-Layout

**This file describes the supported product path, `src/textlayout`.**
The full architecture document — including the dependency rules, invariants,
and the "How to add a new generator" walkthrough — is
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The frozen legacy
`src/text_to_gds` MCP pipeline is documented in
[docs/legacy/ARCHITECTURE_text_to_gds.md](docs/legacy/ARCHITECTURE_text_to_gds.md).

## Naming

Three names, one project: the repository is **Text-to-Layout**, the Python
distribution on PyPI-style installs is **`text-to-gds`** (historical), and the
supported product package is **`textlayout`**. `text_to_gds` is the frozen
legacy package kept only as the MCP-server surface.

## The one-minute map

```
prompt (natural language)
  │  prompt.py — deterministic parser, no LLM, no API key
  ▼
DesignIntent (typed, pydantic v2)
  │  schemas/dsl/ — the Layout DSL firewall (extra="forbid", gt=0 bounds)
  ▼
LayoutSpec
  │  generators/ + geometry/engine.py — deterministic polygons, AI-free
  ▼
Geometry IR (frozen dataclasses, µm floats)
  │  exporters/ — GDS (gdsfactory + canonicalize), SVG, PNG, JSON
  ▼
output.gds
  │  verification/ — exact polygon-clearance DRC, drawn min-width check,
  │                  independent KLayout readback of the file on disk
  ▼
verification.json + klayout_readback.json
  │  simulation/ — FasterCap / FastHenry / openEMS / JoSIM adapters;
  │               honest status vocabulary, retained solver stdout/stderr
  ▼
simulation.json
  │  evidence.py — THE evidence contract: a false full-physics-signoff record
  │               is structurally unconstructible
  ▼
report.md
```

Orchestration: `workflow/` wires these stages into a LangGraph graph
(ParsePrompt → … → GenerateReport) with a bounded solver-in-the-loop retune
cycle (`MAX_SOLVER_ITERATIONS`, no-progress detection in `should_retune`).
LangGraph owns sequencing only; deterministic Python owns all geometry and
evidence.

## Three invariants

1. **The DSL is the AI firewall.** Anything above `schemas/dsl` may be driven
   by an agent; everything below is deterministic.
2. **`evidence.py` is the only place a physics claim can be minted.**
3. **Failed verification never exports.**

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the module-by-module map,
dependency rule, and contributor walkthrough.
