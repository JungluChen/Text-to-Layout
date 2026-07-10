---
name: text-to-layout
description: >
  Turn a natural-language chip design request into a typed Layout DSL,
  deterministic GDS geometry, KLayout readback verification, guarded FasterCap
  capacitance extraction, and an honest evidence report. Use when the user asks
  to create/generate a chip layout (IDC, CPW, spiral inductor, quarter-wave
  resonator, SQUID, IDC+CPW test structure, or a multi-device test-chip tile),
  to verify a layout DSL file, or to check the layout toolchain environment.
---

# Text-to-Layout

## What this skill does

`textlayout` converts a prompt into committed, inspectable artifacts through a
LangGraph pipeline: ParsePrompt → ValidateIntent → BuildLayoutDSL →
OptimizeParameters → GenerateGeometry → ExportArtifacts → KLayoutReadback →
GeometryVerification → PrepareFasterCap → RunFasterCapIfAvailable →
ParseSolverResult → CompareTarget → GenerateReport → UpdateShowcaseMetadata.

Deterministic Python owns all geometry and verification; the parser is
rule-based (no LLM call, no API key).

## Commands

```bash
# Environment health check — run this first on a new machine
textlayout doctor

# Natural language → full artifact chain
textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" --out out/idc_demo

# Existing Layout DSL file → verified artifacts
textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/idc

# Verify a DSL file without exporting
textlayout verify path/to/layout.json

# Regenerate the six committed showcase examples
python scripts/generate_showcase_examples.py --force

# Validate that README claims match committed artifacts
python scripts/validate_readme_claims.py
```

## Output contract (per run)

```text
intent.json            parsed design intent
layout.json            typed Layout DSL
output.gds/.svg/.png   geometry artifacts
klayout_readback.json  independent KLayout verification of the GDS on disk
verification.json      design-rule + readback results
simulation.json        typed solver evidence (see status vocabulary)
optimization.json      analytical sizing + solver-in-the-loop iterations
workflow_trace.json    per-node LangGraph execution trace
report.md              target-vs-result report
```

## Honesty rules (non-negotiable)

- Evidence statuses: `ANALYTICAL_ONLY`, `SIMULATION_INPUT_PREPARED`,
  `SKIPPED_SOLVER_ABSENT`, `SIMULATION_EXECUTED`, `PHYSICS_VERIFIED`, `FAILED`.
- `PHYSICS_VERIFIED` is only possible when a real solver executed, its output
  was parsed, and the extracted value is within tolerance — this is enforced
  structurally in `src/textlayout/evidence.py`, do not work around it.
- A missing solver is `SKIPPED_SOLVER_ABSENT`, never a failure and never faked.
- Analytical estimates are design starting points, never "verification".
- Every generated layout is a research candidate: **not fabrication-ready**
  until process-specific DRC, expert review, and measurement planning are done.

## Solver notes

- FasterCap/FastCap: discovered from `--executable`, `TEXTLAYOUT_FASTERCAP`,
  PATH, or `.tools/FasterCap`; a Linux/WSL build is auto-run through `wsl` on
  Windows. Extraction on a TestStructure covers only the documented IDC region.
- openEMS / FastHenry / JoSIM: input preparation always works; execution only
  when installed. JoSIM validates circuit dynamics and is never capacitance
  extraction evidence.
