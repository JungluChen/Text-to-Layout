# Simulation Plan - TestChip

- Status: **planned**
- Simulation readiness: **Level 1 - geometry/research workflow defined**
- No solver result is claimed by this file.

## Recommended extraction

- **IDC_sub_block:** FasterCap/FastCap on the standalone IDC geometry (identical parameters).
- **full_tile:** Full-wave EM of the assembled tile — future work, not performed here.

## Comparison method

1. Execute the named solver and retain its input, version, log, and output artifact.
2. Extract the requested physical quantity from the solver-owned output.
3. Compare it with the Layout DSL target and state the error and tolerance.
4. Change Layout DSL parameters, regenerate, and rerun verification.

## Limitations

- This tile is a geometry-level comparison candidate; no sub-block on the tile has been simulated in place, and inter-device coupling is not modeled.
- All electrical numbers are per-sub-device analytical estimates, valid only in isolation.
- Alignment marks and the title label are lithographic aids with no electrical model.
- The tile is not fabrication-ready: process DRC, density rules, and dicing margins are not checked.
