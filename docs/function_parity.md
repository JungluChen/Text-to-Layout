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
| Validation loop | KLayout Python min-width scan and `.drc.json` reports |
| Simulation handoff | ideal JJ `.simulation.json` report from sidecar metadata |
| Example outputs | `examples/example_output.md` |
| Benchmark prompts | `benchmarks/01-manhattan-josephson-junction.md` |
| CI and local checks | `.github/workflows/test.yml`, pytest, ruff, compileall |

## Intentional Differences

- Text-to-GDS does not implement STEP, STL, 3MF, G-code, URDF, SRDF, or SDF
  workflows because those are mechanical CAD and robotics outputs.
- Text-to-GDS does not claim foundry signoff until a real process DRC deck is
  provided.
- Text-to-GDS uses GDS, sidecars, DRC reports, and superconducting simulation
  reports as the domain-specific equivalents of text-to-cad artifacts.
