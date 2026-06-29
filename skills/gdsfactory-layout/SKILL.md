---
name: gdsfactory-layout
description: Generate deterministic IC layout artifacts from a validated Layout DSL with the repository's gdsfactory-backed workflow. Use for GDS, SVG, PNG, geometry JSON, ports, layer mapping, or reproducible benchmark generation.
---

# gdsfactory layout generation

Never translate natural language directly into polygons. Use this pipeline:

`prompt -> research -> Layout DSL -> Pydantic validation -> deterministic generator -> verification -> gdsfactory Component -> export`

## Required workflow

1. Require a research report and a typed Layout DSL.
2. Validate component parameters and units before creating geometry.
3. Resolve named layers through the selected technology; never silently map an unknown layer to `(0, 0)`.
4. Use the registered deterministic generator. Do not add prompt-specific polygon code.
5. Build the gdsfactory `Component`, including named electrical ports.
6. Run all pre-export checks. If any required check fails, write no final geometry artifact.
7. Export GDS, SVG, PNG, geometry JSON, DSL provenance, verification JSON, evidence Markdown, and report Markdown.
8. Confirm every requested file exists and is non-empty.

## Commands

```bash
textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out
python scripts/generate_benchmarks.py
```

Treat GDS as the primary layout artifact. Treat SVG/PNG as previews and JSON as machine-readable provenance. A visually correct preview is not electrical evidence.
