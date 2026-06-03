# Function Parity With text-to-cad

Text-to-GDS follows the same open-source shape as `earthtojake/text-to-cad`,
but replaces mechanical CAD operations with local EDA layout operations.

| text-to-cad pattern | Text-to-GDS implementation |
| --- | --- |
| Installable skill library | `skills/text-to-gds` plus `npx skills install JungluChen/Text-to-Layout` |
| Provider plugin bundle | `plugins/text-to-gds` with Codex and Claude metadata |
| Local deterministic toolchain | `py -3 -m uv run ...` commands and MCP server |
| Source-controlled generators | gdsfactory PCells under `src/text_to_gds/pcells` |
| Primary generated artifact | `.gds` instead of `.step` |
| Visual review artifact | `.layout.png` screenshot generated from the GDS |
| Inspection sidecar | `.sidecar.json` with ports, bbox, layers, and PCell metadata |
| 3D/stack review aid | `.stack3d.html` and `.stack3d.json` 2.5D process-stack preview |
| Validation loop | KLayout Python min-width scan and `.drc.json` reports |
| Simulation handoff | ideal JJ `.simulation.json`, extraction summaries, JoSIM deck scaffold, and JosephsonCircuits.jl command plan |
| Prompt planning | `plan_ljpa` turns short LJPA prompts into clarification questions, assumptions, registered PCells, and simulator choices |
| Example outputs | `examples/example_output.md` |
| Benchmark prompts | six prompt/layout screenshot benchmark rows under `benchmarks/` and `assets/` |
| CI and local checks | `.github/workflows/test.yml`, pytest, ruff, compileall |

## Intentional Differences

- Text-to-GDS does not implement STEP, STL, 3MF, G-code, URDF, SRDF, or SDF
  workflows because those are mechanical CAD and robotics outputs.
- Text-to-GDS does not claim foundry signoff until a real process DRC deck is
  provided.
- Text-to-GDS uses GDS, sidecars, DRC reports, and superconducting simulation
  reports as the domain-specific equivalents of text-to-cad artifacts.
- Text-to-GDS now has the same high-level agent loop shape as text-to-cad:
  prompt, generated source artifact, visual review artifact, sidecar/metadata,
  validation report, examples, benchmarks, skill, plugin bundle, and local
  tests. Its remaining gaps are domain-specific signoff depth: real process DRC,
  external simulator execution, EM extraction, and closed-loop optimization.
